from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import hashlib, json, gzip, time
import pandas as pd

O = Path(__file__).resolve().parent / 'verified_v2'
O.mkdir(exist_ok=True)
T = O.parent.parent
P = T / 'ar6_native_feasibility/principal_protection_snapshot_v1'
BOOK = T / 'pvr_pool_feasibility/continuation2023/run-2023/pair/B.json.gz'
SNAPS = T / 'pvr_pool_feasibility/continuation2023/run-2023/pair/daily.jsonl.gz'
MANIFEST = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
FAST = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py')
JOINT = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def save(n, v): (O / n).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str) + '\n')

def main():
    started = time.monotonic()
    assert not (O / 'RESULTS.json').exists(), 'do not repeat completed check'
    old = read(P / 'SOURCE_FREEZE.json')
    layers = read(P / 'ALL_1557_LAYERS.json')
    same_day_negative = [r for r in layers if r['first_hit_delay_sessions'] == 0 and r['net_sign_POSTHOC'] == 'negative']
    assert len(same_day_negative) == 19
    selected = [next(r for r in layers if r['layer'] == 113)] + same_day_negative
    assert len({r['layer'] for r in selected}) == 20
    manifests = {r['series_id']: r for r in read(MANIFEST)['series']}
    source_paths = [Path(__file__), P/'SOURCE_FREEZE.json', P/'ALL_1557_LAYERS.json', BOOK, SNAPS, MANIFEST, FAST, JOINT,
                    T/'independent_review/principal_price_protection_review_v1/SNAPSHOT_AND_FIRST_HIT_AUDIT.json']
    source_paths += [Path(old['facts'][r['sid']]) for r in selected]
    source_paths += [Path(manifests[r['sid']]['raw']['path']) for r in selected]
    source_paths = list(dict.fromkeys(source_paths))
    freeze = {str(p): sha(p) for p in source_paths}
    for p, h in freeze.items():
        if p in old['sources']: assert h == old['sources'][p], p
    for r in selected:
        meta = manifests[r['sid']]['raw']
        assert sha(meta['path']) == meta['sha256']
    save('INPUT_FREEZE.json', {'scope':'20 original fixed cases only; no new F/E witness/strategy/quote model', 'source_sha256':freeze})
    with gzip.open(BOOK, 'rt') as f: book = json.load(f)
    with gzip.open(SNAPS, 'rt') as f: calendar = [json.loads(line)['at'][:10] for line in f]
    assert len(calendar) == 484 and len(set(calendar)) == 484
    idx = {d: i for i, d in enumerate(calendar)}
    def next_open(at):
        k = idx[at[:10]] + 1
        return None if k == len(calendar) else calendar[k] + ' 09:30:00+08:00'
    records = []
    for r in selected:
        sid, layer = r['sid'], r['layer']
        h = r['first_snapshot_hit']
        facts = pd.read_parquet(old['facts'][sid], columns=['raw_close','factor','segment_id'])
        raw = pd.read_parquet(manifests[sid]['raw']['path']).set_index('trade_date')
        assert raw.index.is_unique and raw.index.is_monotonic_increasing
        q = facts.loc[pd.Timestamp(h['day'])]
        p = D(str(q.raw_close)); floor = D(h['effective_line_raw']); entry = D(r['entry_execution_price'])
        assert h['known'] and str(q.segment_id) == h['source_segment'] and str(q.factor) == h['current_factor']
        assert p == D(str(raw.loc[pd.Timestamp(h['day']), 'close']))
        requests = [x for x in book['audit'] if x.get('kind') == 'pilot_layer_exit' and layer in x.get('layers', [])]
        assert requests
        first_request = requests[0]
        fills = [{**t, 'matching_part': part} for t in book['trades'] if t['side'] == 'sell' for part in t['parts'] if part['layer'] == layer]
        assert fills and fills[-1]['at'] == r['closed']
        request_next = next_open(first_request['at'])
        wait_open_rows = []
        for day in calendar:
            at = day + ' 09:30:00+08:00'
            if first_request['at'] < at <= fills[0]['at']:
                bar = raw.loc[pd.Timestamp(day)]
                wait_open_rows.append({'day': day, 'at': at,
                    'raw_open':str(bar.open), 'raw_high':str(bar.high), 'raw_low':str(bar.low), 'raw_close':str(bar.close),
                    'volume':str(bar.volume), 'raw_high_le_low':bool(bar.high <= bar.low),
                    'actual_layer_sell_at_this_OPEN':any(t['at'] == at for t in fills),
                    'flat_bar_execution_scope':'original conservative_hl_proxy rejects flat day; not exchange-certified limit-state'})
        records.append({'layer':layer, 'sid':sid, 'role':r['role'], 'opened':r['opened'], 'original_cutoff_net':r['net'],
            'cohort':'worst_ever_hit_negative_113' if layer == 113 else 'all_19_same_entry_CLOSE_hit_negative',
            'first_original_F_ge_E_hit':h, 'current_native_mark':str(p), 'entry_execution_price':str(entry), 'effective_raw_floor':str(floor),
            'mark_source':'original prepared raw close; exact to old facts.raw_close and existing native finance mark bridge',
            'mark_gt_floor':p > floor, 'mark_le_floor':p <= floor,
            'F_ge_E_and_p_gt_F_and_no_stock_pending':bool(floor >= entry and p > floor and not h['pending_stock_exit']),
            'next_OPEN_after_firsthit':next_open(h['at']), 'first_original_layer_exit_request':first_request,
            'next_OPEN_after_exit_request':request_next,
            'sold_next_OPEN_after_exit_request':any(t['at'] == request_next for t in fills),
            'first_actual_sell':fills[0], 'all_actual_sell_parts':fills,
            'exit_request_to_firstfill_sessions':idx[fills[0]['at'][:10]] - idx[first_request['at'][:10]],
            'original_OPEN_rows_between_request_and_fill':wait_open_rows})
    save('FIXED_20_CASES.json', records)
    candidates = [
        'pvr_pool_feasibility/current_entry_protection_capacity_card_v1/ALGORITHM_CARD.txt',
        'current_entry_protection_capacity_card_v1/ALGORITHM_CARD.txt',
        'ma63_h_certificate_events_v1/READOUT.txt',
        'ma63_h_certificate_events_v1/STATISTICS.json',
        'ma63_h_certificate_events_v1/DAILY_ALL_484.csv',
        'ma63_h_certificate_events_v1/ALL_POTENTIAL_EVENTS.csv',
        'ma63_h_certificate_events_v1/ALL_22_EPISODES.json',
        'ma63_h_certificate_events_v1/SOURCE_FREEZE.json']
    save('INTERRUPTED_ARTIFACT_STATUS.json', {
        'targets':[{'path':s, 'exists':(T/s).exists(), 'sha256':sha(T/s) if (T/s).is_file() else None}for s in candidates],
        'independent_review_filenames_matching_certificate':[str(p.relative_to(T))for p in (T/'independent_review').rglob('*') if p.is_file() and ('cert' in p.name.lower() or 'h_recover' in p.name.lower())],
        'formal_H_event_audit_status':'No named certificate-event audit found; old H_C source-supplement is not the event audit; do not rerun saved table',
        'old_RG_card_status':'absent at both expected paths; new parent formula is cost/NAV alpha10/20/40, not old mark-G plus .005-risk'})
    for p, h in freeze.items(): assert sha(p) == h, p
    save('RESULTS.json', {'status':'PASS_FIXED_20_ORIGINAL_BOUNDARY_READONLY', 'seconds':time.monotonic()-started,
        'cases':len(records), 'firsthit_mark_gt_F':sum(r['mark_gt_floor']for r in records),
        'firsthit_pending_stock_exit':sum(r['first_original_F_ge_E_hit']['pending_stock_exit']for r in records),
        'firsthit_breached':sum(r['mark_le_floor']for r in records),
        'sell_next_OPEN_after_request':sum(r['sold_next_OPEN_after_exit_request']for r in records),
        'new_F_E_witness_runs':0, 'new_accounts':0, 'new_quotes':0, 'old_firsthit_statistics_unchanged':True})
    print(json.dumps(read(O/'RESULTS.json')))

if __name__ == '__main__': main()
