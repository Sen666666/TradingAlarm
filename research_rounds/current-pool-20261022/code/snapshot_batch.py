"""Raw current cap/name snapshots, grouped by native THS market, 50 codes/query.

No market-cap calculations or historical backfill. Import/validation is offline.
Plan has source_master {path, sha256}, items [{symbol, node, market, code}],
as_of_date (research label only), max_requests and connection bounds.
"""
from contextlib import ExitStack
from pathlib import Path
import argparse
import collections
import csv
import fcntl
import io
import json
import math
import re
import sys

import history_batch as hb

FIELDS = {202: '2942,1771976,3475914,3541450', 200: '10,55'}
MARKETS = {'USHA': '9602', 'USZA': '9602', 'USHT': '9602', 'USTM': '9602', 'UHKM': '9603', 'UHKG': '9603'}


def validate_plan(plan):
    if plan.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    items = plan.get('items', [])
    if not 1 <= len(items) <= 10000 or len({x['symbol'] for x in items}) != len(items):
        raise ValueError('requires 1..10000 unique security lines')
    hb.date8(plan['as_of_date'])
    # Reuse finite connection/budget validation without a network import.
    probe = dict(plan, items=[dict(symbol=items[0]['symbol'], node=items[0]['node'], mode='tail', earliest='19000101', end='20990101')])
    hb.validate_plan(probe)
    master = plan['source_master']
    source = Path(master['path']).read_bytes()
    if hb.digest(source) != master['sha256']:
        raise ValueError('source master hash mismatch')
    rows = list(csv.DictReader(io.StringIO(source.decode('utf-8-sig'))))
    native = {}
    for row in rows:
        symbol = row.get('ths_symbol')
        if not symbol:
            continue
        if symbol in native:
            raise ValueError('duplicate native ID in source master')
        native[symbol] = row
    for item in items:
        symbol, market, code = item['symbol'], item['market'], item['code']
        if market not in MARKETS or str(item['node']) != MARKETS[market]:
            raise ValueError('native market/node mismatch')
        if not re.fullmatch(r'[A-Za-z0-9]+', code) or symbol != market + code:
            raise ValueError('native symbol/market/code mismatch')
        if symbol not in native:
            raise ValueError('symbol absent from source master')
        row = native[symbol]
        # HKEX display codes (00001) differ from the client's native HK0001.
        if row.get('ths_market') != market or (row.get('ths_code') or row.get('code')) != code:
            raise ValueError('plan disagrees with source master native IDs')
    return plan, source


def groups_for(plan):
    grouped = collections.defaultdict(list)
    for item in plan['items']:
        grouped[(str(item['node']), item['market'])].append(item)
    groups = []
    for (node, market), items in sorted(grouped.items()):
        for start in range(0, len(items), 50):
            groups.append({'name': f'{len(groups)+1:04d}-{market}', 'node': node, 'market': market, 'items': items[start:start+50]})
    return groups


def match_records(records, expected):
    """Never join by response position or silently use an unrequested symbol."""
    matched, unexpected, duplicate, malformed = {}, [], [], []
    allowed = set(expected)
    for i, row in enumerate(records):
        if not isinstance(row, dict) or not isinstance(row.get('5'), str):
            malformed.append(i); continue
        symbol = row['5']
        if symbol not in allowed:
            unexpected.append(symbol); continue
        if symbol in matched:
            duplicate.append(symbol); continue
        matched[symbol] = row
    invalid = set(duplicate)
    for symbol in invalid:
        matched.pop(symbol, None)
    return matched, {'requested': len(expected), 'returned_rows': len(records),
                     'matched_symbols': len(matched), 'missing_symbols': sorted(allowed-set(matched)),
                     'unexpected_symbols': unexpected, 'duplicate_symbols': sorted(invalid),
                     'malformed_row_positions': malformed}


def field_state(value, field):
    if value is None or value == '' or value == '--':
        return 'missing'
    if field == '55':
        return 'present' if isinstance(value, str) and value.strip() else 'invalid_name'
    if type(value) not in (int, float) or not math.isfinite(value):
        return 'invalid_numeric'
    if field in {'10', '3475914', '3541450'} and value <= 0:
        return 'nonpositive'
    return 'present'


def export_rows(plan, evidence, out, protocol_hash):
    rows = []
    for item in plan['items']:
        symbol = item['symbol']
        row = dict(item, as_of_date_label=plan['as_of_date'], market_timestamp=None,
                   raw_fields={}, field_statuses={}, observations={}, status='pending',
                   derived_market_cap=None, market_cap_currency='not_certified_by_collector', historical_point_in_time=False)
        for kind in (202, 200):
            source = evidence.get((symbol, kind))
            for field in FIELDS[kind].split(','):
                value = source['record'].get(field) if source and source['record'] else None
                row['raw_fields'][field] = value
                row['field_statuses'][field] = field_state(value, field)
            if source:
                row['observations'][str(kind)] = {k: v for k, v in source.items() if k != 'record'}
        if len(row['observations']) == 2:
            row['status'] = 'received' if all(v == 'present' for v in row['field_statuses'].values()) else 'received_with_missing_or_invalid_fields'
        elif row['observations']:
            row['status'] = 'partial'
        rows.append(row)
    hb.atomic(out / 'snapshot.json', {'protocol_sha256': protocol_hash, 'updated_at': hb.now(),
              'as_of_date_label': plan['as_of_date'], 'label_is_not_observed_timestamp': True,
              'note': 'Raw THS field 3541450/3475914 values retained; no 2479 multiplication, FX conversion, capital-chain inference or account admission.',
              'rows': rows})
    return dict(collections.Counter(x['status'] for x in rows))


def run(plan, out, ths, fu, protocol_hash):
    collector = hb.Collector(plan, out, ths, fu, protocol_hash)
    evidence, audits, error = {}, [], None
    status = 'running'
    try:
        for group in groups_for(plan):
            expected = [x['symbol'] for x in group['items']]
            for kind in (202, 200):
                params = dict(market=group['market'], codelist=','.join(x['code'] for x in group['items']), datatype=FIELDS[kind])
                records, meta = collector.fetch_evidence(group['node'], out / 'responses' / group['name'] / str(kind), kind, params)
                receipt = hb.read_json(out / meta['attempt'] / 'receipt.json')
                matched, audit = match_records(records, expected)
                audit.update(group=group['name'], node=group['node'], kind=kind, evidence=meta,
                             observed_at=receipt.get('received_at'), recovered_at=receipt.get('recovered_at'))
                audits.append(audit)
                for symbol in expected:
                    evidence[(symbol, kind)] = dict(record=matched.get(symbol), observed_at=receipt.get('received_at'),
                        recovered_at=receipt.get('recovered_at'), returned_symbol_matched=symbol in matched,
                        response_attempt=meta['attempt'], response_sha256=meta['raw_sha256'])
                hb.atomic(out / 'match-audit.json', {'protocol_sha256': protocol_hash, 'queries': audits})
                export_rows(plan, evidence, out, protocol_hash)
                if audit['unexpected_symbols'] or audit['duplicate_symbols'] or audit['malformed_row_positions']:
                    status = 'halted_symbol_integrity'; error = {'type': 'response_symbol_integrity', 'group': group['name'], 'kind': kind}
                    return 2
            print(json.dumps({'group': group['name'], 'securities': len(expected), 'requests_reserved': collector.state['requests_reserved']}, ensure_ascii=False), flush=True)
        status = 'finished'
        return 0
    except ths.BudgetExhausted:
        status = 'halted_budget'; error = {'type': 'request_budget_exhausted'}; return 2
    except (ths.HandshakeRejected, ths.SessionUnavailable, ths.NetworkFailure) as exc:
        status = 'halted_node_error'; error = {'type': type(exc).__name__, 'node': group['node']}
        collector.stopped_nodes.add(group['node'])
        collector.state['node_last_errors'][group['node']] = dict(error, at=hb.now())
        return 2
    except ValueError:
        status = 'halted_integrity'; error = {'type': 'decode_or_evidence_integrity'}
        raise
    finally:
        for conn in collector.connections.values():
            conn.close()
        collector.save_state()
        counts = export_rows(plan, evidence, out, protocol_hash)
        hb.atomic(out / 'run-summary.json', {'updated_at': hb.now(), 'protocol_sha256': protocol_hash, 'status': status,
                  'planned_securities': len(plan['items']), 'symbol_statuses': counts,
                  'requests_reserved_total': collector.state['requests_reserved'], 'error': error,
                  'stopped_nodes_this_run': sorted(collector.stopped_nodes), 'account_runs': 0, 'algorithm_changes': 0})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--research-root', type=Path, default=hb.DEFAULT_RESEARCH)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--resume-after-stop', action='store_true')
    args = parser.parse_args()
    raw_plan = args.plan.read_bytes()
    plan, master_bytes = validate_plan(json.loads(raw_plan))
    groups = groups_for(plan)
    if args.validate_only:
        print(json.dumps({'valid': True, 'items': len(plan['items']), 'groups': len(groups),
                          'planned_requests': len(groups)*2, 'max_requests': plan['max_requests'], 'network': False})); return 0
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for path in [out / '.run.lock'] + [Path(__file__).parent / ('.node-' + n + '.run.lock') for n in sorted({str(x['node']) for x in plan['items']})]:
            lock = stack.enter_context(path.open('a'))
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        hb.immutable(out / 'protocol.json', raw_plan)
        hb.immutable(out / 'source-master.csv', master_bytes)
        previous = hb.read_json(out / 'run-summary.json')
        if previous and previous.get('status') != 'finished' and not args.resume_after_stop:
            raise ValueError('snapshot halted; review before explicit --resume-after-stop')
        imports = args.research_root.resolve(); sys.path.insert(0, str(imports))
        import ths_readonly as ths
        import ths_readonly_fu as fu
        if tuple(ths.QUOTE) != hb.ENDPOINTS['9602'] or tuple(fu.FU_QUOTE) != hb.ENDPOINTS['9603']:
            raise ValueError('unexpected endpoint')
        deps = [Path(__file__).resolve(), Path(hb.__file__).resolve(), imports / 'ths_readonly.py', imports / 'ths_readonly_fu.py',
                imports.parent / 'market.py', imports.parent / 'sessions.py']
        hb.immutable(out / 'code-manifest.json', hb.encoded({str(p): hb.digest(p.read_bytes()) for p in deps}))
        return run(plan, out, ths, fu, hb.digest(raw_plan))


if __name__ == '__main__':
    raise SystemExit(main())
