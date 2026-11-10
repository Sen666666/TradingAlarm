"""Bounded, resumable raw THS history collection. Importing this file is offline.

CLI: python history_batch.py --plan plan.json --output batch-directory
Plan: schema_version=1, items=[{symbol,node,end,earliest,mode,rights,max_pages}],
      max_requests, request_interval_seconds, session_preference(optional).
Only the two already authorized quote nodes are reachable. Never sends orders.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
import urllib.parse

DEFAULT_RESEARCH = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')
PAGE = 750
FIELDS = '1,7,8,9,11,13,19,74'
ENDPOINTS = {'9602': ('119.3.43.91', 9602), '9603': ('119.3.4.152', 9603)}


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('immutable evidence conflict: ' + str(path))
        return
    with tempfile.NamedTemporaryFile(prefix=path.name + '.pending-', dir=path.parent, delete=False) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
        pending = Path(f.name)
    try:
        os.link(pending, path)  # Atomic exclusive publication; never replaces a final evidence file.
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError('immutable evidence conflict: ' + str(path))
    pending.unlink()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as f:
        f.write(encoded(value)); f.flush(); os.fsync(f.fileno())
    temp.replace(path)


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def date8(value):
    text = str(value).replace('-', '')
    if not re.fullmatch(r'\d{8}', text):
        raise ValueError('invalid daily date')
    datetime.strptime(text, '%Y%m%d')
    return text


def validate_plan(plan):
    if plan.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    items = plan.get('items', [])
    if not 1 <= len(items) <= 100:
        raise ValueError('plan requires 1..100 security lines')
    if len({x['symbol'] for x in items}) != len(items):
        raise ValueError('duplicate symbol')
    if type(plan.get('max_requests')) is not int or not 1 <= plan['max_requests'] <= 10000:
        raise ValueError('explicit finite max_requests 1..10000 required')
    interval = plan.get('request_interval_seconds', .3)
    if type(interval) not in (int, float) or not math.isfinite(interval) or not .1 <= interval <= 60:
        raise ValueError('request_interval_seconds must be 0.1..60')
    timeout = plan.get('read_timeout_seconds', 20)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError('read_timeout_seconds must be a finite number in (0,60]')
    if plan.get('session_preference', 'snapshot') not in ('snapshot', 'client', 'auto'):
        raise ValueError('invalid session preference')
    for x in items:
        if not re.fullmatch(r'[A-Z][A-Z0-9]{3}[A-Za-z0-9]+', x['symbol']):
            raise ValueError('invalid symbol')
        if str(x['node']) not in ENDPOINTS or x.get('mode') not in ('tail', 'full'):
            raise ValueError('invalid node or mode')
        if date8(x['earliest']) > date8(x['end']):
            raise ValueError('earliest after end')
        if type(x.get('max_pages', 40)) is not int or not 1 <= x.get('max_pages', 40) <= 100:
            raise ValueError('max_pages must be 1..100')
        if 'rights' in x and not isinstance(x['rights'], bool):
            raise ValueError('rights must be boolean')
    return plan


def raw_date_records(records):
    """Validate raw dates before any market.bars filtering; compare full raw records."""
    out = {}
    for row in records:
        if not isinstance(row, dict) or row.get('1') is None:
            raise ValueError('raw history record missing date')
        key = date8(row['1'])
        if key in out and out[key] != row:
            raise ValueError('same-page raw date conflict')
        out[key] = row
    return out


def classify_page(records, previous, end, earliest):
    dated = raw_date_records(records)
    conflicts = sorted(k for k, row in dated.items() if k in previous and previous[k] != row)
    added = len(set(dated) - set(previous))
    if conflicts:
        return {'stop': 'raw_overlap_conflict', 'complete': False, 'conflicts': conflicts, 'added': added}
    if not records:
        return {'stop': 'empty_raw_page', 'complete': bool(previous), 'conflicts': [], 'added': 0}
    if any(k > date8(end) for k in dated):
        return {'stop': 'row_after_requested_end', 'complete': False, 'conflicts': [], 'added': added}
    first = min(dated)
    if not added:
        return {'stop': 'no_new_raw_dates', 'complete': False, 'conflicts': [], 'added': 0}
    if first <= date8(earliest):
        return {'stop': 'requested_earliest_reached', 'complete': True, 'conflicts': [], 'added': added}
    if len(records) < PAGE:
        return {'stop': 'short_raw_page_source_boundary', 'complete': True, 'conflicts': [], 'added': added}
    if first >= date8(end):
        return {'stop': 'end_not_advancing', 'complete': False, 'conflicts': [], 'added': added}
    return {'stop': None, 'complete': False, 'conflicts': [], 'added': added, 'next_end': first}


class Collector:
    def __init__(self, plan, output, ths, fu, protocol_hash):
        self.plan, self.out, self.ths, self.fu = plan, output, ths, fu
        self.protocol_hash = protocol_hash
        self.state_path = output / 'batch-state.json'
        self.state = read_json(self.state_path, {'protocol_sha256': protocol_hash, 'requests_reserved': 0, 'node_last_errors': {}})
        if self.state['protocol_sha256'] != protocol_hash:
            raise ValueError('batch-state protocol mismatch')
        self.connections = {}
        self.stopped_nodes = set()

    def save_state(self):
        self.state['updated_at'] = now()
        atomic(self.state_path, self.state)

    def connection(self, node):
        if node in self.stopped_nodes:
            raise RuntimeError('node_stopped_this_run')
        if node in self.connections:
            return self.connections[node]
        candidates = self.fu.session_candidates if node == '9603' else self.ths.session_candidates
        available = candidates(self.plan.get('session_preference', 'snapshot'))
        if not available:
            raise self.ths.SessionUnavailable('no unlatched session candidate')
        # No fallback after a handshake rejection: the inherited class latches it.
        _, manager = available[0]
        kw = dict(interval=self.plan.get('request_interval_seconds', .3), max_requests=self.plan['max_requests'],
                  connect_timeout=8, read_timeout=self.plan.get('read_timeout_seconds', 20))
        conn = self.fu.FuConnection(manager, **kw) if node == '9603' else self.ths.Connection(ENDPOINTS[node], manager, **kw)
        if tuple(conn.endpoint) != ENDPOINTS[node]:
            raise ValueError('unexpected endpoint')
        conn.open()
        self.connections[node] = conn
        return conn

    def fetch_evidence(self, node, base, kind, params):
        """Recover a completed raw response before spending another bounded request."""
        base.mkdir(parents=True, exist_ok=True)
        attempts = sorted(p for p in base.glob('attempt-*') if p.is_dir())
        for attempt in attempts:
            if (attempt / 'response.bin').exists():
                return self.decode_evidence(attempt, kind, node, params)
        if self.state['requests_reserved'] >= self.plan['max_requests']:
            raise self.ths.BudgetExhausted('batch request budget exhausted')
        conn = self.connection(node)
        attempt = base / f'attempt-{len(attempts) + 1:03d}'
        attempt.mkdir()
        conn.instance += 1
        query = dict(id=kind, instance=conn.instance, zipversion=3, **params)
        immutable(attempt / 'request.json', encoded({'query': query, 'node': node, 'endpoint': '%s:%s' % ENDPOINTS[node], 'prepared_at': now()}))
        self.state['requests_reserved'] += 1
        self.save_state()
        # Save raw body BEFORE decoding; inherited quote() decodes too early to preserve a decode failure.
        conn._send(urllib.parse.urlencode(query, safe=',').encode())
        def match(body):
            return len(body) >= 10 and struct.unpack_from('<HII', body) == (17, conn.instance, kind)
        body = conn._receive_matching(match)
        immutable(attempt / 'response.bin', body)
        immutable(attempt / 'receipt.json', encoded({'received_at': now(), 'sha256': digest(body), 'bytes': len(body)}))
        return self.decode_evidence(attempt, kind, node, params)

    def decode_evidence(self, attempt, kind, node, params):
        body = (attempt / 'response.bin').read_bytes()
        request_meta = read_json(attempt / 'request.json')
        request = request_meta['query']
        expected = dict(id=kind, zipversion=3, **params)
        if request_meta['node'] != node or request_meta['endpoint'] != '%s:%s' % ENDPOINTS[node] or {k: v for k, v in request.items() if k != 'instance'} != expected:
            raise ValueError('saved response request identity mismatch')
        receipt = read_json(attempt / 'receipt.json')
        if receipt and (receipt['sha256'] != digest(body) or receipt['bytes'] != len(body)):
            raise ValueError('raw response hash mismatch')
        if not receipt:
            immutable(attempt / 'receipt.json', encoded({'received_at': None, 'recovered_at': now(), 'sha256': digest(body), 'bytes': len(body)}))
        decoded = self.ths.decode(body, allowed_kinds=(kind,))
        if not decoded or decoded[0] != kind or decoded[1] != request['instance'] or not isinstance(decoded[2], list):
            raise ValueError('unsupported raw response')
        records = decoded[2]
        immutable(attempt / 'decoded.json', encoded(records))
        return records, {'attempt': str(attempt.relative_to(self.out)), 'raw_sha256': digest(body),
                         'decoded_sha256': digest(encoded(records)), 'query': request, 'decoded_records': len(records)}

    def checkpoint(self, symbol, cp):
        cp['updated_at'] = now()
        atomic(self.out / 'checkpoints' / f'{symbol}.json', cp)

    def load_merged(self, cp, item):
        merged = {}
        expected_end = date8(item['end'])
        for p in cp['pages']:
            attempt = self.out / p['attempt']
            saved_request = read_json(attempt / 'request.json')
            expected_query = dict(id=210, zipversion=3, market=item['symbol'][:4], code=item['symbol'][4:], start=-(PAGE - 1), end=expected_end, datatype=FIELDS, period=16384)
            if saved_request['query'] != p['query'] or saved_request['node'] != str(item['node']) or {k: v for k, v in p['query'].items() if k != 'instance'} != expected_query:
                raise ValueError('checkpoint page query identity mismatch')
            if digest((attempt / 'response.bin').read_bytes()) != p['raw_sha256']:
                raise ValueError('checkpoint raw hash mismatch')
            raw = (attempt / 'decoded.json').read_bytes()
            if digest(raw) != p['decoded_sha256']:
                raise ValueError('checkpoint decoded hash mismatch')
            dated = raw_date_records(json.loads(raw))
            for key, row in dated.items():
                if key in merged and merged[key] != row:
                    raise ValueError('checkpoint raw overlap conflict')
                merged[key] = row
            if dated:
                expected_end = min(dated)
        return merged

    def export_history(self, item, cp, merged):
        records = [merged[k] for k in sorted(merged)]
        bars = self.ths.daily_bars(records)
        path = self.out / 'history' / f"{item['symbol']}.json"
        atomic(path, {'symbol': item['symbol'], 'node': str(item['node']), 'source': 'THS id210 raw; fuquan omitted',
                      'protocol_sha256': self.protocol_hash, 'mode': item['mode'], 'requested_end': date8(item['end']),
                      'requested_earliest': date8(item['earliest']), 'history_status': cp['history_status'],
                      'stop_reason': cp.get('stop_reason'), 'raw_unique_dates': len(records), 'bars': bars,
                      'rows_dropped_by_parser': len(records) - len(bars), 'pages': cp['pages'],
                      'volume_unit': 'source wire units; do not infer a market-wide conversion from parser',
                      'adjustment': 'unadjusted source query; corporate actions separate', 'account_ready': False})

    def collect_one(self, item):
        symbol, node = item['symbol'], str(item['node'])
        path = self.out / 'checkpoints' / f'{symbol}.json'
        cp = read_json(path, {'symbol': symbol, 'node': node, 'protocol_sha256': self.protocol_hash,
                              'history_status': 'pending', 'pages': [], 'next_end': date8(item['end']), 'rights_status': 'pending' if item.get('rights') else 'not_requested'})
        if cp['protocol_sha256'] != self.protocol_hash or cp['node'] != node or cp['symbol'] != symbol:
            raise ValueError('symbol checkpoint protocol/node mismatch')
        merged = self.load_merged(cp, item)
        terminal = {'complete', 'quarantined', 'page_budget_exhausted'}
        stage = 'history'
        try:
            if cp['history_status'] not in terminal:
                while len(cp['pages']) < item.get('max_pages', 40):
                    n = len(cp['pages']) + 1
                    records, evidence = self.fetch_evidence(node, self.out / 'pages' / symbol / f'page-{n:03d}', 210,
                        dict(market=symbol[:4], code=symbol[4:], start=-(PAGE - 1), end=cp['next_end'], datatype=FIELDS, period=16384))
                    result = classify_page(records, merged, cp['next_end'], item['earliest'])
                    if result['conflicts'] or result['stop'] == 'row_after_requested_end':
                        cp.update(history_status='quarantined', stop_reason=result['stop'], failed_page=dict(evidence, **result))
                        self.checkpoint(symbol, cp); break
                    dated = raw_date_records(records)
                    merged.update(dated)
                    cp['pages'].append(dict(evidence, page=n, added_raw_dates=result['added'], first_raw=min(dated) if dated else None,
                                            last_raw=max(dated) if dated else None, stop=result['stop']))
                    cp['stop_reason'] = result['stop']
                    if result['stop']:
                        cp['history_status'] = 'complete' if result['complete'] else 'quarantined'
                    else:
                        cp['history_status'] = 'in_progress'; cp['next_end'] = result['next_end']
                    self.checkpoint(symbol, cp)
                    if result['stop']:
                        break
                if cp['history_status'] == 'in_progress':
                    cp.update(history_status='page_budget_exhausted', stop_reason='max_pages')
            self.export_history(item, cp, merged)
            if item.get('rights') and cp['rights_status'] not in {'received', 'decode_or_integrity_error'}:
                stage = 'rights'
                records, evidence = self.fetch_evidence(node, self.out / 'rights' / symbol, 211,
                    dict(market=symbol[:4], code=symbol[4:], start=0, end=0, datatype='1,471', period=16384))
                cp['rights_status'] = 'received'
                cp['rights'] = dict(evidence, records=len(records), complete_actions_certified=False,
                                    empty_does_not_prove_no_events=True, ledger_ready=False)
        except self.ths.BudgetExhausted:
            cp['last_error'] = {'type': 'request_budget_exhausted', 'at': now()}
        except (self.ths.HandshakeRejected, self.ths.SessionUnavailable, self.ths.NetworkFailure) as exc:
            self.stopped_nodes.add(node)
            error = type(exc).__name__
            cp['last_error'] = {'type': error, 'at': now()}
            self.state['node_last_errors'][node] = cp['last_error']; self.save_state()
        except ValueError as exc:
            if stage == 'rights':
                cp['rights_status'] = 'decode_or_integrity_error'
            else:
                cp['history_status'] = 'quarantined'
            cp['last_error'] = {'type': 'decode_or_integrity_error', 'stage': stage, 'detail': str(exc), 'at': now()}
        self.checkpoint(symbol, cp)
        self.export_history(item, cp, merged)
        return cp

    def run(self):
        counts = {}
        try:
            for i, item in enumerate(self.plan['items'], 1):
                if str(item['node']) in self.stopped_nodes:
                    counts['skipped_node_stopped'] = counts.get('skipped_node_stopped', 0) + 1
                    continue
                cp = self.collect_one(item)
                status = cp['history_status']
                counts[status] = counts.get(status, 0) + 1
                if i % 10 == 0 or i == len(self.plan['items']):
                    print(json.dumps({'processed': i, 'planned': len(self.plan['items']), 'requests_reserved': self.state['requests_reserved'], 'statuses': counts}, ensure_ascii=False), flush=True)
                if self.state['requests_reserved'] >= self.plan['max_requests']:
                    break
        finally:
            for conn in self.connections.values():
                conn.close()
            self.save_state()
            atomic(self.out / 'run-summary.json', {'updated_at': now(), 'protocol_sha256': self.protocol_hash,
                   'requests_reserved_total': self.state['requests_reserved'], 'statuses_this_run': counts,
                   'stopped_nodes_this_run': sorted(self.stopped_nodes), 'account_runs': 0, 'algorithm_changes': 0})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--research-root', type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    raw_plan = args.plan.read_bytes()
    plan = validate_plan(json.loads(raw_plan))
    if args.validate_only:
        print(json.dumps({'valid': True, 'items': len(plan['items']), 'protocol_sha256': digest(raw_plan), 'network': False})); return
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / '.run.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        immutable(args.output / 'protocol.json', raw_plan)
        imports = args.research_root.resolve()
        sys.path.insert(0, str(imports))
        import ths_readonly as ths
        import ths_readonly_fu as fu
        assert tuple(ths.QUOTE) == ENDPOINTS['9602'] and tuple(fu.FU_QUOTE) == ENDPOINTS['9603']
        code_hashes = {str(p): digest(p.read_bytes()) for p in [Path(__file__).resolve(), imports / 'ths_readonly.py', imports / 'ths_readonly_fu.py', imports.parent / 'market.py', imports.parent / 'sessions.py']}
        immutable(args.output / 'code-manifest.json', encoded(code_hashes))
        Collector(plan, args.output.resolve(), ths, fu, digest(raw_plan)).run()


if __name__ == '__main__':
    main()
