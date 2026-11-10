"""Run frozen history plans sequentially. Import/--validate-only never connect.

Example: python history_queue.py --plan-index ../audit-a/batch-plans-v1/index.json
  --group 01-tail-and-new --output ../downloads/a-tail-queue-01
Existing halted queues require an explicit --resume-after-stop. No automatic retry.
"""
from contextlib import ExitStack
from pathlib import Path
import argparse
import collections
import fcntl
import json
import subprocess
import sys

import history_batch as hb


def prepare(index_path, groups, research_root):
    raw = index_path.read_bytes()
    index = json.loads(raw)
    entries = index['batches']
    if groups:
        entries = [x for x in entries if x.get('group') in groups]
    if not entries:
        raise ValueError('no matching batches')
    collector = Path(__file__).with_name('history_batch.py').resolve()
    collector_hash = hb.digest(collector.read_bytes())
    if index.get('collector_sha256') != collector_hash:
        raise ValueError('plan index collector hash mismatch')
    rows, used_names = [], set()
    for entry in entries:
        path = Path(entry['path']).resolve()
        plan_bytes = path.read_bytes()
        if hb.digest(plan_bytes) != entry['sha256']:
            raise ValueError('indexed plan hash mismatch: ' + path.name)
        plan = hb.validate_plan(json.loads(plan_bytes))
        name = path.stem
        if name in used_names:
            raise ValueError('duplicate batch output name')
        used_names.add(name)
        rows.append({'name': name, 'plan': str(path), 'sha256': hb.digest(plan_bytes),
                     'nodes': sorted({str(x['node']) for x in plan['items']}),
                     'items': len(plan['items']), 'max_requests': plan['max_requests']})
    deps = [collector, research_root / 'ths_readonly.py', research_root / 'ths_readonly_fu.py',
            research_root.parent / 'market.py', research_root.parent / 'sessions.py']
    child_code = {str(p): hb.digest(p.read_bytes()) for p in deps}
    return {'schema_version': 1, 'index_path': str(index_path.resolve()),
            'index_sha256': hb.digest(raw), 'groups': sorted(groups), 'batches': rows,
            'max_requests_total': sum(x['max_requests'] for x in rows),
            'security_lines_total': sum(x['items'] for x in rows),
            'runner': str(Path(__file__).resolve()), 'runner_sha256': hb.digest(Path(__file__).read_bytes()),
            'collector_code': child_code, 'sequential': True, 'retry_automatically': False}


def inspect_batch(batch, out, code):
    """A successful process is insufficient: check persisted per-security state."""
    if (out / 'protocol.json').read_bytes() != Path(batch['plan']).read_bytes():
        raise ValueError('child protocol mismatch')
    if hb.read_json(out / 'code-manifest.json') != code:
        raise ValueError('child code manifest mismatch')
    summary = hb.read_json(out / 'run-summary.json')
    if not summary or summary['protocol_sha256'] != batch['sha256']:
        raise ValueError('missing or wrong child summary')
    if summary.get('stopped_nodes_this_run'):
        return {'status': 'halted', 'reason': 'node_error', 'summary': summary}
    plan = json.loads(Path(batch['plan']).read_bytes())
    history, rights, pending = collections.Counter(), collections.Counter(), []
    for item in plan['items']:
        cp = hb.read_json(out / 'checkpoints' / (item['symbol'] + '.json'))
        if not cp:
            pending.append(item['symbol']); continue
        if cp['protocol_sha256'] != batch['sha256'] or cp['symbol'] != item['symbol'] or cp['node'] != str(item['node']):
            raise ValueError('child checkpoint identity mismatch')
        history[cp['history_status']] += 1
        rights[cp['rights_status']] += 1
        if cp['history_status'] not in {'complete', 'quarantined', 'page_budget_exhausted'}:
            pending.append(item['symbol'])
        elif item.get('rights') and cp['rights_status'] not in {'received', 'decode_or_integrity_error'}:
            pending.append(item['symbol'])
    info = {'history_statuses': dict(history), 'rights_statuses': dict(rights), 'pending_symbols': pending,
            'requests_reserved_total': summary['requests_reserved_total']}
    if pending:
        return dict(info, status='halted', reason='incomplete_batch_requires_review')
    return dict(info, status='finished', reason='terminal_states_recorded',
                data_complete=history.get('complete', 0) == len(plan['items']) and not rights.get('decode_or_integrity_error', 0))


def execute(protocol, out, research_root, resume_after_stop=False):
    out.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        lock = stack.enter_context((out / '.queue.lock').open('a'))
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Cooperates with the snapshot collector. Direct history_batch pilots must
        # still be scheduled separately by the operator.
        nodes = sorted({n for b in protocol['batches'] for n in b['nodes']})
        for node in nodes:
            lock = stack.enter_context((Path(__file__).parent / ('.node-' + node + '.run.lock')).open('a'))
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen = hb.encoded(protocol)
        hb.immutable(out / 'queue-protocol.json', frozen)
        protocol_hash = hb.digest(frozen)
        state = hb.read_json(out / 'queue-state.json', {'protocol_sha256': protocol_hash, 'status': 'pending', 'batches': {}})
        if state['protocol_sha256'] != protocol_hash:
            raise ValueError('queue protocol mismatch')
        if state['status'] == 'halted' and not resume_after_stop:
            raise ValueError('queue halted; review evidence before explicit --resume-after-stop')
        if state['status'] == 'running' and not resume_after_stop:
            raise ValueError('previous queue run interrupted; review before explicit --resume-after-stop')
        state['status'] = 'running'; state['updated_at'] = hb.now()
        hb.atomic(out / 'queue-state.json', state)
        try:
            for i, batch in enumerate(protocol['batches'], 1):
                child = out / 'batches' / batch['name']
                old = state['batches'].get(batch['name'], {})
                if old.get('status') == 'finished':
                    checked = inspect_batch(batch, child, protocol['collector_code'])
                    if checked['status'] != 'finished':
                        raise ValueError('finished batch no longer verifies')
                    continue
                # Validate plans/code again immediately before launching a child.
                if hb.digest(Path(batch['plan']).read_bytes()) != batch['sha256']:
                    raise ValueError('plan changed during queue')
                for path, expected in protocol['collector_code'].items():
                    if hb.digest(Path(path).read_bytes()) != expected:
                        raise ValueError('collector dependency changed during queue')
                logs = out / 'logs' / batch['name']; logs.mkdir(parents=True, exist_ok=True)
                attempt = len(list(logs.glob('*.stdout.log'))) + 1
                result = {'status': 'running', 'started_at': hb.now(), 'attempt': attempt, 'output': str(child)}
                state['batches'][batch['name']] = result
                hb.atomic(out / 'queue-state.json', state)
                command = [sys.executable, str(Path(__file__).with_name('history_batch.py')), '--plan', batch['plan'],
                           '--output', str(child), '--research-root', str(research_root)]
                with (logs / f'{attempt:03d}.stdout.log').open('x') as stdout, (logs / f'{attempt:03d}.stderr.log').open('x') as stderr:
                    proc = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
                if proc.returncode:
                    result.update(status='halted', reason='collector_process_error', returncode=proc.returncode)
                else:
                    result.update(inspect_batch(batch, child, protocol['collector_code']))
                result['finished_at'] = hb.now()
                state['updated_at'] = hb.now()
                state['batches'][batch['name']] = result
                print(json.dumps({'batch': i, 'batches': len(protocol['batches']), 'name': batch['name'],
                                  'status': result['status'], 'reason': result['reason'],
                                  'requests_reserved': result.get('requests_reserved_total')}, ensure_ascii=False), flush=True)
                if result['status'] == 'halted':
                    state['status'] = 'halted'; state['stop_batch'] = batch['name']
                    hb.atomic(out / 'queue-state.json', state)
                    return 2
                hb.atomic(out / 'queue-state.json', state)
            state['status'] = 'finished'; state['updated_at'] = hb.now()
            hb.atomic(out / 'queue-state.json', state)
            return 0
        except BaseException as exc:
            state.update(status='halted', updated_at=hb.now(), error_type=type(exc).__name__)
            hb.atomic(out / 'queue-state.json', state)
            raise
        finally:
            hb.atomic(out / 'queue-summary.json', {'updated_at': hb.now(), 'status': state['status'],
                      'protocol_sha256': protocol_hash, 'planned_batches': len(protocol['batches']),
                      'finished_batches': sum(x.get('status') == 'finished' for x in state['batches'].values()),
                      'incomplete_data_batches': [k for k, v in state['batches'].items() if v.get('status') == 'finished' and not v.get('data_complete')],
                      'requests_reserved_reported': sum(x.get('requests_reserved_total', x.get('summary', {}).get('requests_reserved_total', 0)) for x in state['batches'].values()),
                      'account_runs': 0, 'algorithm_changes': 0})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-index', type=Path, required=True)
    parser.add_argument('--group', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--research-root', type=Path, default=hb.DEFAULT_RESEARCH)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--resume-after-stop', action='store_true')
    args = parser.parse_args()
    protocol = prepare(args.plan_index, args.group, args.research_root.resolve())
    if args.validate_only:
        print(json.dumps({'valid': True, 'batches': len(protocol['batches']), 'security_lines': protocol['security_lines_total'],
                          'max_requests_total': protocol['max_requests_total'], 'nodes': sorted({n for b in protocol['batches'] for n in b['nodes']}),
                          'network': False})); return 0
    return execute(protocol, args.output.resolve(), args.research_root.resolve(), args.resume_after_stop)


if __name__ == '__main__':
    raise SystemExit(main())
