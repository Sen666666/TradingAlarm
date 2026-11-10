"""Saved original CP/input/account annotations only; no candidate or account run."""
from pathlib import Path
import json, gzip, hashlib, math, csv
import pandas as pd
import numpy as np

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parents[1]
PAIR = ENTRY / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CM = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')
SID = '300085.SZ'
START, END = '2024-09-01', '2024-11-30'
SOURCES = {}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if x is None or x is pd.NA: return None
    if isinstance(x, np.generic): x = x.item()
    if isinstance(x, pd.Timestamp): return str(x.date())
    return None if isinstance(x, float) and not math.isfinite(x) else x
def read(p):
    p = Path(p); SOURCES[str(p)] = sha(p)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f: return json.load(f)
def parquet(p, expected=None):
    p = Path(p); SOURCES[str(p)] = sha(p)
    if expected: assert SOURCES[str(p)] == expected
    return pd.read_parquet(p)
def save(name, x): (HERE / name).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def in_scope(day): return START <= day <= END


def main():
    meta = next(r for r in read(SM) if r['symbol'] == SID)
    q = parquet(meta['refs']['CP1_input'], meta['output_sha256'][meta['refs']['CP1_input']]).loc[:END]
    cp = parquet(meta['refs']['CP1'], meta['output_sha256'][meta['refs']['CP1']]).loc[:END]
    native = parquet(meta['refs']['facts'], meta['output_sha256'][meta['refs']['facts']]).loc[:END]
    price_path = next(p for p in meta['source_sha256'] if p.endswith('/signal.parquet'))
    event_path = next(p for p in meta['source_sha256'] if p.endswith('/events.parquet'))
    price = parquet(price_path, meta['source_sha256'][price_path]).loc[:END]
    events = parquet(event_path, meta['source_sha256'][event_path]).loc[:END]
    canonical_entry = next(r for r in read(CM) if r['sid'] == SID)
    assert sha(canonical_entry['output_path']) == canonical_entry['output_sha256']
    canonical = {r['confirmed_day']: r for r in read(canonical_entry['output_path'])}
    assert q.index.isin(cp.index).all() and q.index.isin(native.index).all() and q.index.isin(price.index).all()
    assert np.array_equal(q.close, price.reindex(q.index).close)
    assert np.array_equal(q.amount, price.reindex(q.index).amount)
    full = q.add_prefix('q__').join(cp.reindex(q.index).add_prefix('oldCP__')).join(native.reindex(q.index).add_prefix('native__'))
    full = full.join(price.reindex(q.index)[['raw_close', 'adjustment_factor', 'observed_bar', 'source_invalid', 'synthetic_event_bar']].add_prefix('price__'))
    full = full.join(events.reindex(q.index)[['event', 'confirmed_pivot_price', 'confirmed_pivot_date']].add_prefix('originalE0__'))
    full.to_parquet(HERE / 'ORIGINAL_FULL_PREFIX_CP_FACTS.parquet')
    book = read(PAIR / 'B.json.gz')
    daily = {}; funding = []
    for name in ('daily.jsonl.gz', 'funding.jsonl.gz'):
        p = PAIR / name; SOURCES[str(p)] = sha(p)
        with gzip.open(p, 'rt') as f:
            for i, line in enumerate(f):
                r = json.loads(line)
                if r.get('account') != 'B' or not in_scope(r.get('at', '')[:10]): continue
                if name.startswith('daily'):
                    daily[r['at'][:10]] = {'source_line_index': i, 'original_CLOSE_at': r['at'],
                        'layers': [{k: x.get(k) for k in ('id', 'kind', 'role', 'pool', 'qty', 'floor', 'stock_structure', 'opened', 'signal_at')} for x in r['layers'] if x['sid'] == SID],
                        'own_pending_sell': SID in r['pending_sells'], 'ACT_on': r['on']}
                elif r.get('sid') == SID:
                    funding.append({'source_line_index': i, 'original': r})
    requests = {}
    for di, d in enumerate(book['decisions']):
        day = d['at'][:10]
        if not in_scope(day): continue
        requests[day] = [{'decision_index': di, 'intent_index': ii,
                         'original': {k: x.get(k) for k in ('sid', 'kind', 'role', 'floor', 'CP1_id', 'epoch', 'reason')}}
                        for ii, x in enumerate(d['intents']) if x.get('sid') == SID]
    buys = [{'trade_index': i, 'original': t} for i, t in enumerate(book['trades'])
            if t.get('security_id') == SID and t['side'] == 'buy' and in_scope(t.get('signal_at', '')[:10])]
    ids = {r['original']['layer'] for r in buys}
    sells = [{'trade_index': i, 'original': t} for i, t in enumerate(book['trades'])
             if t.get('security_id') == SID and t['side'] == 'sell' and any(p['layer'] in ids for p in t['parts'])]
    rows = []; receipt_table = []
    for stamp, row in full.loc[START:END].iterrows():
        day = str(stamp.date()); r = clean(cp.loc[stamp].to_dict()); proof = canonical.get(day)
        assert bool(r['receipt']) == (proof is not None)
        if proof:
            assert proof['original_candidate'] == r['candidate'] and proof['original_scale'] == r['scale']
        for req in requests.get(day, []):
            if req['original']['CP1_id']:
                assert proof and req['original']['CP1_id'] == proof['receipt_id']
        item = {'sid': SID, 'day': day, 'raw_C': native.loc[stamp, 'raw_close'], 'C': q.loc[stamp, 'close'],
            'original_CP_input': q.loc[stamp].to_dict(), 'original_CP_cache': r, 'original_canonical_receipt': proof,
            'original_E0_event': events.loc[stamp, 'event'],
            'original_native_I_G1': native.loc[stamp, ['i_target', 'i_floor', 'i_buy', 'g_grade', 'g_ready', 'g_fresh_up', 'g_acute_down']].to_dict(),
            'recorded_original_intents_only': requests.get(day, []), 'original_position_annotations_only': daily.get(day),
            'original_actual_buys_from_this_signal': [b for b in buys if b['original']['signal_at'][:10] == day],
            'eligibility_scope': 'Recorded original intent/fill only; absence is not a recomputed ADD eligibility decision. Old kind=add is not a new candidate mature identity.'}
        rows.append(item)
        if proof:
            receipt_table.append({'day': day, 'C': item['C'], 'raw_C': item['raw_C'],
                'receipt_id': proof['receipt_id'], 'candidate': r['candidate'], 'r': r['r'], 'm': r['m'],
                'delta_frontier': r['delta_frontier'], 'displacement': r['displacement'], 'credit': r['credit'],
                'used_scale': r['scale'], 'next_scale': r['next_scale'], 'scale_frozen_at': proof['scale_frozen_at'],
                'original_intent_roles': [a['original']['role'] for a in item['recorded_original_intents_only']],
                'original_actual_layer_ids': [a['original']['layer'] for a in item['original_actual_buys_from_this_signal']]})
    assert len(rows) == 58 and len(receipt_table) == 16
    save('ORIGINAL_DAILY_FACTS.json', rows); save('ORIGINAL_CP_RECEIPT_TABLE.json', receipt_table)
    save('ORIGINAL_REAL_ACCOUNT_ANNOTATIONS.json', {'original_buys': buys, 'original_sells': sells, 'original_funding': funding,
        'scope': 'Authoritative No60 B simulated account only; no candidate quantity, grant, account path or new returns.'})
    with (HERE / 'ORIGINAL_CP_RECEIPT_TABLE.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(receipt_table[0])); writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()} for row in receipt_table)
    save('ORIGINAL_RESET_ROWS.json', [r for r in rows if r['original_CP_cache']['reset_reason'] not in (None, 'receipt_consumed')])
    save('PREPARATION_RECEIPT.json', {'status': 'ORIGINAL_FACTS_READY_CANDIDATE_NOT_RUN',
        'full_original_CP_prefix_first_day': str(full.index[0].date()), 'full_original_CP_prefix_last_day': str(full.index[-1].date()),
        'full_original_CP_prefix_rows': len(full), 'display_rows': len(rows), 'all_original_receipt_rows': len(receipt_table),
        'original_buy_layer_ids': sorted(ids), 'original_canonical_dates_candidate_used_scale_exact': True,
        'old_CP_I_input_scope': 'Original e0_valid is old native I context; no candidate input/state changes yet.',
        'price_CP_recomputations': 0, 'candidate_runs': 0, 'new_accounts': 0, 'new_quantities': 0, 'new_returns': 0,
        'source_sha256': SOURCES, 'script_sha256': sha(__file__)})
    save('OUTPUT_SHA256.json', {str(p): sha(p) for p in HERE.iterdir() if p.is_file() and p.name != 'OUTPUT_SHA256.json'})
    print(json.dumps({'prefix_rows': len(full), 'days': len(rows), 'receipts': len(receipt_table), 'actual_layers': sorted(ids)}, ensure_ascii=False))


if __name__ == '__main__': main()
