"""Read saved original events only; no Account, marks, routing or PnL."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import gzip, hashlib, json, time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
EVENTS = ROOT / 'industry_capital_v1/events'
META = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')

def load(p):
    return json.loads(p.read_text())

def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def h1semi(e, meta):
    return e['window'] == 'strong' and '2026-01-01' <= e['OPEN'] <= '2026-06-30' and meta[e['sid']]['industry'] == '半导体'

started = time.monotonic()
groups = load(EVENTS / 'FIRST_SOURCE_I_EPOCH_REJECT_WITH_LATER_BUYS.json')
commits = load(EVENTS / 'ACTUAL_SAMEOPEN_RESERVE_COMMITMENTS.json')
meta = load(META)
selected = {}
for g in groups:
    fills = [x for x in g['later_actual_CORE_MOBILE_same_epoch'] if x['role'] == 'mobile' and x['same_OPEN_after_rejection_funding']]
    if fills:
        assert len({x['budget_order'] for x in fills}) == 1
        selected[g['first_event_key']] = (g, fills)
assert len(selected) == 315
first_keys = {g['first_event_key'] for g in groups}
first_stats = Counter()
rows = []
h1_dual_first_rows = []
for line in gzip.open(EVENTS / 'CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz', 'rt'):
    e = json.loads(line)
    if e['key'] not in first_keys:
        continue
    op = e['original_opportunity']
    dual = bool(op['CP1_id']) and op['core_Q'] is True and 'mobile' in op['roles']
    first_stats['all_first'] += 1
    first_stats['all_first_dual_CP'] += int(dual)
    if h1semi(e, meta):
        first_stats['H1_semis_first'] += 1
        first_stats['H1_semis_first_dual_CP'] += int(dual)
        if dual:
            h1_dual_first_rows.append(dict(key=e['key'], sid=e['sid'], name=meta[e['sid']]['name'],
                window=e['window'], signal_day=e['signal_day'], OPEN=e['OPEN'],
                original_CORE_failure_set=e['failure_tags'], original_CORE_intent=e['original_intent'],
                original_opportunity=op, original_OPEN_contract_preview=e['original_OPEN_contract_preview'],
                actual_sameOPEN_MOBILE_fill_witness=e['key'] in selected,
                first_unique_failure='NOT_INFERRED_FROM_MERGED_TAGS',
                candidate_net_label_join_key=e['key']))
    if e['key'] not in selected:
        continue
    g, fills = selected[e['key']]
    c = commits[e['window'] + '|' + fills[0]['budget_order']]
    assert dual and op['held'] is False and op['barriers'] == []
    assert c['CP1_id'] == op['CP1_id'] and c['role'] == 'mobile' and c['pool'] == 'confirmed'
    assert c['OPEN'] == e['OPEN'] and c['funding_stream_index'] > e['funding_stream_index']
    assert all(x['role'] == 'mobile' and x['CP1_id'] == c['CP1_id'] for x in c['actual_fills_after_all_funding'])
    assert sum(int(x['shares']) for x in c['actual_fills_after_all_funding']) == int(c['later_filled_shares']) > 0
    x = e['original_OPEN_contract_preview']
    p = D(x['execution_price_with_original_5bps'])
    core_floor = D(x['protection_raw'])
    mobile_floor = D(str(c['final_native_budget_order']['floor']))
    q = int(c['later_filled_shares'])
    minimum = int(x['dated_minimum_shares'])
    rows.append(dict(
        key=e['key'], window=e['window'], sid=e['sid'], name=meta[e['sid']]['name'],
        industry=meta[e['sid']]['industry'], signal_day=e['signal_day'], OPEN=e['OPEN'],
        source_I_epoch=g['source_I_epoch'], original_core_intent=e['original_intent'],
        original_opportunity=op, CP1_id=c['CP1_id'], original_CORE_failure_set=e['failure_tags'],
        first_unique_failure='NOT_INFERRED_FROM_MERGED_TAGS',
        original_CORE_funding_stream_index=e['funding_stream_index'],
        original_MOBILE_funding_stream_index=c['funding_stream_index'],
        original_CORE_OPEN_preview=x,
        actual_MOBILE=dict(budget_order=c['budget_order'], pool=c['pool'], shares_reserved=c['shares'],
            shares_filled=q, fills=c['actual_fills_after_all_funding'],
            gross_reserved=c['actual_reserved_gross'], buy_fee_reserved=c['actual_reserved_buy_fee'],
            native_order=c['final_native_budget_order']),
        saved_scalar_floor_diagnostic=dict(
            CORE_raw_floor=str(core_floor), MOBILE_raw_order_floor_float=str(mobile_floor),
            MOBILE_floor_strictly_higher_by_1e_9=mobile_floor > core_floor + D('1e-9'),
            at_original_minimum_CORE_nominal_risk=str(minimum * (p - core_floor)),
            at_original_minimum_MOBILE_nominal_risk=str(minimum * max(D(0), p - mobile_floor)),
            at_actual_MOBILE_qty_CORE_nominal_risk=str(q * (p - core_floor)),
            at_actual_MOBILE_qty_MOBILE_nominal_risk=str(q * max(D(0), p - mobile_floor)),
            scope='Saved scalar illustration, excludes fees; native order floor is float serialization. Not a new route/quantity, executed CORE, or risk-neutral swap.'),
        H1_semiconductor=h1semi(e, meta),
        scope='Retrospective original fallback witness; actual MOBILE fill must not become a forward eligibility condition.'
    ))
assert len(rows) == 315
rows.sort(key=lambda r: r['key'])
summary = dict(
    scope='Original first-source-I CORE sector rejects with same-OPEN original MOBILE actual fill, saved data only',
    rows=len(rows), by_window=dict(Counter(r['window'] for r in rows)),
    actual_MOBILE_pools=dict(Counter(r['actual_MOBILE']['pool'] for r in rows)),
    original_CORE_failure_sets=dict(Counter(','.join(r['original_CORE_failure_set']) for r in rows)),
    Mobile_floor_higher_than_Core_1e_9=sum(r['saved_scalar_floor_diagnostic']['MOBILE_floor_strictly_higher_by_1e_9'] for r in rows),
    retained_sector_risk_failure_keys=[r['key'] for r in rows if 'sector_risk' in r['original_CORE_failure_set']],
    H1_semiconductor_keys=[r['key'] for r in rows if r['H1_semiconductor']],
    H1_semiconductor_all_first_dual_keys=[r['key'] for r in h1_dual_first_rows],
    H1_semiconductor_all_first_dual_failure_sets=dict(Counter(','.join(r['original_CORE_failure_set']) for r in h1_dual_first_rows)),
    first_mother_counts=dict(first_stats),
    no_new_Account=True, no_new_marks=True, no_route_projection=True,
    elapsed_seconds=time.monotonic() - started,
    known_limits=['315 is post-outcome diagnostic selection, not a legal live cohort.',
        'Merged original failure tags are sets, not a unique first-cause sequence.',
        'Original rejected CORE quantity was not submitted/logged; min/max are saved preview bounds.',
        'Actual Mobile confirmed fill does not prove CORE quantity/risk/execution admissible.']
)
save('ORIGINAL_315_SAMEOPEN_DUAL_PROOF.json', rows)
save('H1_SEMICONDUCTOR_DUAL_PROOF.json', [r for r in rows if r['H1_semiconductor']])
save('H1_SEMICONDUCTOR_ALL62_FIRST_DUAL_PROOF.json', h1_dual_first_rows)
save('SAVED_JOIN_SUMMARY.json', summary)
sources = [Path(__file__), EVENTS / 'FIRST_SOURCE_I_EPOCH_REJECT_WITH_LATER_BUYS.json',
    EVENTS / 'ACTUAL_SAMEOPEN_RESERVE_COMMITMENTS.json', EVENTS / 'CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz', META]
save('SAVED_JOIN_SOURCE_SHA256.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
print(json.dumps(summary, ensure_ascii=False, indent=2))
