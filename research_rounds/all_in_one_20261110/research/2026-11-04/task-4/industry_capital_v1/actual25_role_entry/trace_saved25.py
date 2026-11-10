"""Join 25 original H1 semi fills to original admission facts. No new ledger/marks."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
from datetime import datetime
import gzip, hashlib, json, sys, time
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OLD = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
MONEY = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
sys.path.insert(0, str(ROOT / 'new_price_trend_v1/funding'))
import entry_adapter as E
LR = E.J.LR
SOURCE = {}
def read(p):
    p = Path(p); SOURCE[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())
def gz(p):
    p = Path(p); SOURCE[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with gzip.open(p, 'rt') as f:
        yield from (json.loads(line) for line in f)
def save(n, x):
    (HERE / n).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n')
def effective(xs, day):
    return next(x for x in reversed(xs) if x['from'] <= day and (x.get('to') is None or day < x['to']))
def scalar(x):
    return None if pd.isna(x) else x.item() if hasattr(x, 'item') else x

started = time.monotonic()
direct = read(ROOT / 'trend_hold_v1/funding/ALL25_ROLE_PROTECTION_DIRECT_EVIDENCE.json')
ids = {r['sid'] for r in direct}
assert len(direct) == 25 and len(ids) == 18
pair = ROOT / 'new_price_trend_v1/funding/runs/strong_OFF/pair'
p = pair / 'B.json.gz'; SOURCE[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
book = json.load(gzip.open(p, 'rt'))
decisions = {r['at'][:10]: r for r in book['decisions']}
days = list(decisions)
daily = {r['at'][:10]: r for r in gz(pair / 'daily.jsonl.gz')}
industry_events = list(gz(pair / 'industry.jsonl.gz'))
wanted = {(r['signal_at'][:10], r['sid']) for r in direct}
ops = {}
for op in gz(pair / 'opportunities.jsonl.gz'):
    if op['sid'] in ids:
        ops[op['day'], op['sid']] = op
assert wanted <= ops.keys()
funding = defaultdict(list)
for r in gz(pair / 'funding.jsonl.gz'):
    if r['sid'] in ids and r['role'] == 'core':
        funding[r['at'][:10], r['sid']].append(r)
manifest = {r['symbol']: r for r in read(OLD / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
rules = read(MONEY / 'pvr-act-comparison-20261027/execution-rules-v2.json')
facts = {}
epoch = {}
watch = {}
core_fills = defaultdict(list)
native_layers = {r['id']: r for r in book['layers']}
for t in book['trades']:
    if t['side'] == 'buy' and t['security_id'] in ids and t['kind'] == 'core':
        core_fills[t['security_id']].append(t)
for sid in ids:
    p = Path(manifest[sid]['refs']['facts']); SOURCE[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    assert SOURCE[str(p)] == manifest[sid]['output_sha256'][str(p)]
    f = pd.read_parquet(p); facts[sid] = f
    previous = None; count = 0; current_watch = None
    for day in days:
        idx = f.index.searchsorted(pd.Timestamp(day), side='right') - 1
        key = (False, -1) if idx < 0 else (bool(f.i_target.iloc[idx]), int(f.segment_id.iloc[idx]))
        if key != previous:
            count += 1; previous = key; current_watch = None
        ep = (key[1], count)
        if ops[day, sid]['core_Q'] is True:
            current_watch = ep
        epoch[day, sid] = ep; watch[day, sid] = current_watch
    for t in core_fills[sid]:
        assert tuple(t['epoch']) == epoch[t['signal_at'][:10], sid]

rows = []
for old in direct:
    lid, sid, day = old['layer'], old['sid'], old['signal_at'][:10]
    assert native_layers[lid] == old['original_end_layer']
    op = ops[day, sid]; decision = decisions[day]; z = facts[sid].loc[day]
    assert old['original_frozen_intent']['epoch'] == list(watch[day, sid])
    industry_event = next(r for r in reversed(industry_events) if r['sector'] == op['sector'] and r['day'] <= day)
    if old['role'] == 'mobile':
        assert op['CP1_id'] == old['actual_buy_journal']['CP1_id']
    actual = old['actual_buy']; assert actual in book['trades']
    at = datetime.fromisoformat(old['signal_at'])
    previous_core = [t for t in core_fills[sid] if datetime.fromisoformat(t['at']) <= at]
    locked = any(tuple(t['epoch']) == watch[day, sid] for t in previous_core)
    core_intents = [i for i in decision['intents'] if i['sid'] == sid and i['role'] == 'core']
    signal_funding = [r for r in funding[day, sid] if '15:10:00' in r['at']]
    opening_funding = [r for r in funding[old['native_open'][:10], sid] if '09:30:00' in r['at']]
    qdict = effective(rules['quantity_versions'][sid], day)['rule']
    venue = effective(rules['venue_versions'][sid], day)['venue']
    schedule = effective(rules['fee_versions'][venue], day)['schedule']
    fee = LR.L.FeeSchedule(schedule['schedule_id'], tuple(LR.L.FeeComponent(**c) for c in schedule['components']))
    par = D(rules['security_metadata'][sid]['par_value'])
    qmin = qdict['buy_minimum']; factor = D(str(z.factor)); floor = D(str(z.i_floor)) / factor
    ref = D(str(z.raw_close)) * (D(1) + LR.SLIP); nav = D(decision['nav'])
    minimum_risk = LR.protection_risk(qmin, ref, floor, fee, par)
    risk_budget = nav * D('.0025'); nominal = D(qmin) * ref
    if op['core_Q'] is not True:
        branch = 'original_CORE_Q_not_true'
    elif op['held']:
        branch = 'original_held_prevents_new_CORE'
    elif locked:
        branch = 'original_actual_CORE_epoch_consumed'
    elif not core_intents:
        assert signal_funding
        branch = 'original_CORE_qualified_but_CLOSE_size_rejected'
    elif old['role'] == 'core':
        branch = 'original_CORE_actual_fill'
    else:
        assert opening_funding
        branch = 'original_CORE_intent_but_OPEN_rejected_before_MOBILE_fill'
    gr, gg, gf = scalar(z.g_ready), scalar(z.g_grade), scalar(z.g_fresh_up)
    gcat = 'unknown' if gr is None or gg is None or gf is None else 'not_ready' if not gr else 'ready_below_warm' if gg < 2 else 'warm_fresh' if gf else 'warm_no_fresh'
    original_mobile_floor = D(old['entry_protection_continuous']) if old['role'] == 'mobile' else None
    rows.append(dict(layer=lid, sid=sid, name=old['name'], signal_day=day, OPEN=old['native_open'][:10],
        actual_role=old['role'], actual_pool=old['entry_pool'], actual_shares=actual['shares'],
        actual_buy=actual, original_opportunity=op,
        original_industry_latest_financial_event_at_signal=industry_event,
        financial_state_clock='Last original native industry event at or before this signal CLOSE; unchanged days forward the saved financial level, not a new budget snapshot.',
        actual_MOBILE_CP_same_day_identity=(old['role'] == 'mobile' and op['CP1_id'] == old['actual_buy_journal']['CP1_id']),
        original_signal_facts={k: scalar(z[k]) for k in ['i_buy','i_target','g_ready','g_grade','g_fresh_up','segment_id','close','raw_close','factor','i_floor']},
        G1_observed_category=gcat, original_native_current_epoch=epoch[day, sid],
        original_shadow_watch_epoch=watch[day, sid], original_CORE_epoch_locked=locked,
        original_prior_actual_CORE_fills=previous_core,
        original_same_stock_layers_at_signal=[x for x in daily[day]['layers'] if x['sid'] == sid],
        original_CORE_intents=core_intents, original_CORE_signal_funding_rows=signal_funding,
        original_CORE_OPEN_funding_rows=opening_funding,
        original_CORE_OPEN_failure_sets=[r['result'].split(',') for r in opening_funding if r['result'] != 'reserved'],
        first_unique_OPEN_failure='NOT_INFERRED_FROM_MERGED_TAGS',
        original_planning_branch=branch,
        same_units_floor=dict(original_I_causal=str(z.i_floor),
            actual_MOBILE_causal=None if original_mobile_floor is None else str(original_mobile_floor),
            original_I_raw_at_signal=str(floor),
            MOBILE_raw_at_signal=None if original_mobile_floor is None else str(original_mobile_floor / factor)),
        signal_minimum_CORE_necessary=dict(qmin=qmin, dated_quantity=qdict, fee_schedule_id=schedule['schedule_id'],
            original_reference_price=str(ref), original_I_raw=str(floor), decision_NAV=str(nav),
            fee_inclusive_risk_to_I=str(minimum_risk), original_quarter_percent_risk_budget=str(risk_budget),
            minimum_risk_pass=minimum_risk <= risk_budget, minimum_gross=str(nominal),
            original_10pct_nominal_max=str(nav * D('.1')), minimum_nominal_pass=nominal <= nav * D('.1'),
            scope='Original signal scalar minimum-unit necessary check only; when CORE not eligible this is not a new order or OPEN admission. No frozen absent intent/max quantity invented.'),
        actual_closed_net=old['whole_original_closed_net'],
        actual_open_cash_balance_not_profit=old['original_open_cash_balance_not_profit'],
        original_exit_decisions=old['actual_exit_decisions']))
assert len(rows) == 25 and Counter(r['actual_role'] for r in rows) == {'core': 1, 'mobile': 24}
summary = dict(rows=25, stocks=18, original_planning_branches=dict(Counter(r['original_planning_branch'] for r in rows)),
    MOBILE_planning_branches=dict(Counter(r['original_planning_branch'] for r in rows if r['actual_role'] == 'mobile')),
    MOBILE_i_buy=dict(Counter(str(r['original_signal_facts']['i_buy']) for r in rows if r['actual_role'] == 'mobile')),
    MOBILE_G1=dict(Counter(r['G1_observed_category'] for r in rows if r['actual_role'] == 'mobile')),
    MOBILE_minimum_risk_fail=sum(not r['signal_minimum_CORE_necessary']['minimum_risk_pass'] for r in rows if r['actual_role'] == 'mobile'),
    MOBILE_minimum_nominal_fail=sum(not r['signal_minimum_CORE_necessary']['minimum_nominal_pass'] for r in rows if r['actual_role'] == 'mobile'),
    MOBILE_original_CORE_OPEN_failure_sets=dict(Counter(','.join(x) for r in rows if r['actual_role'] == 'mobile' for x in r['original_CORE_OPEN_failure_sets'])),
    MOBILE_held_only_mobile_layers=sum(r['original_opportunity']['held'] and all(x['kind'] != 'core' for x in r['original_same_stock_layers_at_signal']) for r in rows if r['actual_role'] == 'mobile'),
    MOBILE_held_has_core=sum(r['original_opportunity']['held'] and any(x['kind'] == 'core' for x in r['original_same_stock_layers_at_signal']) for r in rows if r['actual_role'] == 'mobile'),
    eleven_CORE_OPEN_reject_industry_levels=dict(Counter(str(r['original_industry_latest_financial_event_at_signal']['financial_level']) for r in rows if r['original_planning_branch'] == 'original_CORE_intent_but_OPEN_rejected_before_MOBILE_fill')),
    eleven_actual_MOBILE_pools=dict(Counter(r['actual_pool'] for r in rows if r['original_planning_branch'] == 'original_CORE_intent_but_OPEN_rejected_before_MOBILE_fill')),
    no_new_Account=True, no_new_marks=True, no_route_projection=True,
    seconds=time.monotonic() - started)
save('ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json', rows)
save('SUMMARY.json', summary)
SOURCE[str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
save('SOURCE_SHA256.json', SOURCE)
print(json.dumps(summary, ensure_ascii=False, indent=2))
