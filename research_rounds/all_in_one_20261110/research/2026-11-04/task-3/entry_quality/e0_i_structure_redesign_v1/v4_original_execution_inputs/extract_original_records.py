"""Read original saved account records only. No model/account/candidate execution."""
from pathlib import Path
import json, gzip, hashlib, csv

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
BOOK = BASE.parent / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
TARGETS = {'000620.SZ': ['2022-01-10', '2022-01-20', '2022-01-24'],
           '002583.SZ': ['2024-09-20', '2024-10-14', '2024-10-18', '2024-10-21', '2024-11-20']}
SOURCES = {}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    SOURCES[str(p)] = sha(p)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f: return json.load(f)
def save(n, x): (HERE / n).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
def subset(x, keys): return {k: x[k] for k in keys if k in x}
def ref(section, i): return {'path': str(BOOK / 'B.json.gz'), 'index': f'{section}[{i}]', 'index_base': 0}


def main():
    book = read(BOOK / 'B.json.gz')
    facts = {(r['sid'], r['day']): r for r in read(BASE / 'cp_authorization_v4_inputs/DAILY_ORIGINAL_CP_INPUTS.json')}
    cpstar = {(r['sid'], r['day']): r for r in read(BASE / 'signal_traces_v4/v4_two_stock/ALL_DAILY.json')}
    days = [d['at'][:10] for d in book['decisions']]
    original_daily = {}; funding = []
    for name in ['daily.jsonl.gz', 'funding.jsonl.gz']:
        p = BOOK / name; SOURCES[str(p)] = sha(p)
        with gzip.open(p, 'rt') as f:
            for i, line in enumerate(f):
                r = json.loads(line)
                if r.get('account') != 'B': continue
                if name.startswith('daily'):
                    if any(r.get('at', '')[:10] in d for d in TARGETS.values()): original_daily[r['at'][:10]] = (i, r)
                elif r.get('sid') in TARGETS: funding.append((i, r))
    out = []; core = []
    for sid, targets in TARGETS.items():
        for day in targets:
            di, decision = next((i, r) for i, r in enumerate(book['decisions']) if r['at'][:10] == day)
            nextday = days[di + 1] if di + 1 < len(days) else None
            intents = [{'source': {'path': str(BOOK / 'B.json.gz'), 'index': f'decisions[{di}].intents[{i}]', 'index_base': 0},
                        'original': subset(x, ['sid', 'role', 'kind', 'floor', 'CP1_id', 'epoch', 'reason'])}
                       for i, x in enumerate(decision['intents']) if x.get('sid') == sid]
            fills = []
            for i, t in enumerate(book['trades']):
                if t.get('security_id') != sid or t.get('side') != 'buy' or t.get('signal_at', '')[:10] != day: continue
                keep = subset(t, ['receipt_id', 'security_id', 'side', 'shares', 'at', 'layer', 'kind', 'signal_at', 'raw_open', 'price', 'floor', 'reason', 'epoch', 'execution_basis'])
                fi = next((j for j in intents if j['original']['role'] == t['kind']), None)
                item = {'original': keep, 'source': ref('trades', i)}; fills.append(item)
                if t['layer'] in (68, 1994):
                    canonical = facts[(sid, day)]['canonical_receipt']
                    core.append({'layer': t['layer'], 'sid': sid, 'original_role': t['kind'],
                        'signal_at': t['signal_at'], 'actual_proxy_fill_at': t['at'], 'original_shares': t['shares'],
                        'original_fill_price': t['price'], 'original_raw_OPEN': t['raw_open'],
                        'original_adjusted_protection': t['floor'],
                        'original_intent_CP_id': None if fi is None else fi['original'].get('CP1_id'),
                        'old_market_CP_same_CLOSE': canonical is not None,
                        'old_market_CP_id': None if canonical is None else canonical['receipt_id'],
                        'CP_star_same_CLOSE': cpstar[(sid, day)]['CP_star_receipt'],
                        'trade_source': ref('trades', i), 'intent_source': None if fi is None else fi['source']})
            relevant_order_ids = set()
            for x in fills:
                layer = x['original']['layer']
                relevant_order_ids.update(j['budget_order'] for j in book['journal'] if j.get('kind') == 'real_buy_fill' and j.get('layer') == layer)
            journals = [{'source': ref('journal', i), 'original': subset(x, ['kind', 'at', 'sid', 'order', 'budget_order', 'receipt', 'pool', 'role', 'shares', 'price', 'layer', 'signal_at', 'CP1_id'])}
                        for i, x in enumerate(book['journal']) if x.get('sid') == sid and
                        (x.get('budget_order') in relevant_order_ids or x.get('at', '')[:10] in (day, nextday))]
            audits = [{'source': ref('audit', i), 'original': subset(x, ['kind', 'at', 'decision_at', 'sid', 'order_id', 'target_shares', 'purpose', 'candidate_id', 'layer_kind', 'signal_at', 'shares', 'floor'])}
                      for i, x in enumerate(book['audit']) if x.get('sid') == sid and
                      (x.get('decision_at', '')[:10] == day or x.get('signal_at', '')[:10] == day or x.get('at', '')[:10] == nextday)]
            fr = [{'source': {'path': str(BOOK / 'funding.jsonl.gz'), 'line_index': i, 'index_base': 0},
                   'original': subset(x, ['account', 'at', 'sid', 'role', 'result', 'pool', 'shares', 'CP1_id'])}
                  for i, x in funding if x.get('sid') == sid and x.get('at', '')[:10] == nextday]
            assert all(x['original']['sid'] == sid for x in fr)
            dr = original_daily.get(day)
            snapshot = None if dr is None else {'source': {'path': str(BOOK / 'daily.jsonl.gz'), 'line_index': dr[0], 'index_base': 0},
                        'original_at': dr[1]['at'], 'original_pending_sells': dr[1].get('pending_sells'),
                        'original_same_stock_layer_ids': [x['id'] for x in dr[1].get('layers', []) if x.get('sid') == sid]}
            final_orders = [{'order_key': k, 'fields': subset(v, ['oid', 'stock', 'status', 'role', 'created_bar', 'expiry_bar', 'attempt']),
                             'warning': 'Final dump fields, not an at-signal/reserve/ACK snapshot.'}
                            for k, v in book['budget']['orders'].items() if sid in k and day in k]
            out.append({'sid': sid, 'original_signal_day': day, 'original_signal_at': decision['at'],
                'next_original_market_day_from_saved_calendar': nextday, 'original_intents': intents,
                'original_actual_buys_tied_to_signal': fills,
                'original_same_day_or_next_OPEN_journal_annotations': journals,
                'original_related_audit_annotations': audits, 'original_next_OPEN_funding_results': fr,
                'original_CLOSE_snapshot': snapshot, 'final_budget_order_dump_not_at_time': final_orders,
                'old_CP_same_CLOSE': facts[(sid, day)]['original_CP']['receipt'],
                'CP_star_same_CLOSE_fact_only': cpstar[(sid, day)]['CP_star_receipt'],
                'exchange_submit_cancel_fill_ACK': 'NOT_RECORDED: simulated ledger receipts, timestamps and release_buy are not exchange/broker ACKs.',
                'fixed_target_remaining_partial_semantics': 'Original reserve target and actual fills can be read; no new candidate target/remaining or retry path inferred.'})
    assert sorted(x['layer'] for x in core) == [68, 1994]
    save('ORIGINAL_CORE_TWO_RECORDS.json', core)
    save('EIGHT_FIXED_ORIGINAL_SIGNAL_EXECUTION_RECORDS.json', out)
    with (HERE / 'ORIGINAL_CORE_TWO_RECORDS.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(core[0])); writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for k, v in row.items()} for row in core)
    save('READONLY_RECEIPT.json', {'status': 'ORIGINAL_RECORDS_ONLY', 'source_sha256': SOURCES,
         'script_sha256': sha(__file__), 'original_signal_records': len(out), 'original_CORE_records': len(core),
         'new_models': 0, 'new_accounts': 0, 'new_candidate_quantities': 0, 'new_money_or_returns': 0,
         'V4_authorization_status': 'SUPERSEDED_USER_REJECTED; no additional authorization/statistics run.'})
    print(json.dumps({'CORE': core, 'FIXED_DAYS': [{'sid': x['sid'], 'day': x['original_signal_day'],
          'roles': [i['original']['role'] for i in x['original_intents']],
          'actual_fills': [f['original'] for f in x['original_actual_buys_tied_to_signal']],
          'funding': [f['original'] for f in x['original_next_OPEN_funding_results']]} for x in out]}, ensure_ascii=False))


if __name__ == '__main__': main()
