"""Saved original CORE admission census. No account, marks or route evaluation."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal as D
from datetime import date, datetime
import bisect, gzip, hashlib, json, sys, time
import pandas as pd

O = Path(__file__).resolve().parent; ROOT = O.parent.parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
sys.path.insert(0, str(ROOT / 'new_price_trend_v1/funding'))
import entry_adapter as E
LR = E.J.LR
START = time.monotonic(); LIMIT = 100; SHA = {}; STAGES = []
ALLOWED = {'probe_risk', 'sector_capital'}
NUMERIC = ALLOWED | {'cash_or_original_reserve', 'sector_risk', 'pool_capital', 'stock_capital'}
PREVIEW = {'missing_open', 'open_minimum_exceeds_frozen_contract', 'open_at_or_below_protection'}

def bind(p):
    p = Path(p)
    if str(p) not in SHA: SHA[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p
def read(p): return json.loads(bind(p).read_text())
def lines(p):
    with gzip.open(bind(p), 'rt') as f:
        for line in f: yield json.loads(line)
def save(n, v): (O / n).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n')
def write(n, rs):
    with gzip.open(O / n, 'wt') as f:
        for r in rs: f.write(json.dumps(r, ensure_ascii=False, default=str, allow_nan=False) + '\n')
def checkpoint(stage):
    STAGES.append(dict(stage=stage, seconds=time.monotonic() - START)); save('PROGRESS.json', STAGES)
    if time.monotonic() - START > LIMIT: raise TimeoutError(stage)
def effective(xs, day): return next(x for x in reversed(xs) if x['from'] <= day and (x.get('to') is None or day < x['to']))
def period(day):
    if day[:4] in ('2022', '2023'): return day[:4]
    if day[:4] == '2024': return '2024_924_after' if day >= '2024-09-24' else '2024_pre924'
    return '2025H2' if day[:4] == '2025' else '2026H1'
def group(r): return r['window'] + '|' + r['sid'] + '|' + json.dumps(r['original_intent']['epoch'], separators=(',', ':'))

def main():
    bind(__file__); bind(O / 'PROTOCOL.txt'); bind(ROOT / 'industry_capital_v1/NEXT_MECHANISM_CARD.txt')
    sm = {r['symbol']: r for r in read(W / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    im = read(W / 'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
    meta = read(RR / 'a-share-selection-e0-20261024/inputs-v2/metadata.json')
    rules = read(RR / 'pvr-act-comparison-20261027/execution-rules-v2.json')
    liquidity = {(r['window'], r['OPEN']): r for r in read(ROOT / 'cash_release_v1/ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json')}
    assert read(ROOT / 'cash_release_v1/LEDGER_RECONSTRUCTION_AUDIT.json')['no_existing_reserved_settlement_payable_sale_AR_at_any_original_CLOSE']
    canonical = [{r['sid']: r for r in read(p)} for p in [W / '2022-normal-reference-20261031/inputs/MANIFEST.json', W / 'recovery-2023-readiness-20261101/inputs/MANIFEST.json', Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]]
    initial = {}
    for r in im:
        p = bind(r['refs']['state']); assert SHA[str(p)] == r['output_sha256'][str(p)]
        f = pd.read_parquet(p)
        for window, start in [('long', '2022-01-01'), ('strong', '2025-07-01')]:
            past = f[f.day < start]; last = past.iloc[-1]
            ep = last.E0_episode
            if pd.isna(ep):
                nonnull = past.E0_episode.dropna(); ep = nonnull.iloc[-1] if len(nonnull) else None
            attempt = None; level = 0
            if pd.notna(last.attempt_id):
                ar = past[past.attempt_id == last.attempt_id]; first = ar[ar.action == 'probe'].iloc[0]
                attempt = str(ep) + ':' + str(first.receipt_id); level = int(last.stage) - 1
            initial[window, r['series']] = dict(day='INITIAL_BEFORE_WINDOW', episode=ep, attempt=attempt, financial_level=level, result='initial_native_warm_state')
    checkpoint('manifests_and_native_initial_industry')
    mother = []; reservations = {}; prefixes = {}; all_funding = {}; books = {}
    receipt_cache = {}
    def receipt(window, sid, day):
        key = window, sid
        if key not in receipt_cache:
            out = {}
            sources = [(sm[sid]['refs']['receipts'], None)] if window == 'strong' else [(m[sid]['output_path'], m[sid]['output_sha256']) for m in canonical]
            for p, expected in sources:
                records = read(p)
                if expected is not None: assert SHA[str(Path(p))] == expected
                else: assert SHA[str(Path(p))] == sm[sid]['output_sha256'][str(p)]
                for z in records:
                    d = z['confirmed_day']
                    if ('2022-01-01' <= d <= '2024-12-31') if window == 'long' else ('2025-07-01' <= d <= '2026-06-30'):
                        assert d not in out; out[d] = z
            receipt_cache[key] = out
        return receipt_cache[key].get(day)
    for window in ['long', 'strong']:
        pair = ROOT / 'new_price_trend_v1/funding/runs' / (window + '_OFF') / 'pair'
        p = bind(pair / 'B.json.gz'); b = json.load(gzip.open(p, 'rt')); books[window] = b
        ds = {r['at'][:10]: r for r in b['decisions']}
        intents = {(day, i['sid']): i for day, d in ds.items() for i in d['intents'] if i['role'] == 'core'}
        fills = defaultdict(list)
        for t in b['trades']:
            if t['side'] == 'buy' and t['kind'] == 'core': fills[t['security_id']].append(t)
        ff = list(lines(pair / 'funding.jsonl.gz')); all_funding[window] = ff
        wanted = {(liquidity[window, r['at'][:10]]['signal_day'], r['sid']) for r in ff if r['role'] == 'core' and '09:30:00' in r['at']}
        ops = {}
        for n, r in enumerate(lines(pair / 'opportunities.jsonl.gz')):
            if (r['day'], r['sid']) in wanted: ops[r['day'], r['sid']] = r
            if n % 50000 == 0 and time.monotonic() - START > LIMIT: raise TimeoutError('opportunities')
        assert len(ops) == len(wanted)
        byday = defaultdict(list)
        for z in lines(pair / 'industry.jsonl.gz'): byday[z['day']].append(z)
        states = {}; current = {sid: initial[window, sid] for sid in [r['series'] for r in im]}
        for day in ds:
            for z in byday[day]: current[z['sector']] = z
            states[day] = current.copy()
        real = {(j['at'][:10], j['sid'], j['role']): j for j in b['journal'] if j['kind'] == 'real_reserve'}
        audits = {a['order_id']: a for a in b['audit'] if a['kind'] == 'reserve'}
        buys = defaultdict(list)
        for j in b['journal']:
            if j['kind'] == 'real_buy_fill': buys[j['budget_order']].append(j)
        prefix = []; open_day = None; consumed = set()
        for index, r in enumerate(ff):
            if '09:30:00' not in r['at']: continue
            od, sid = r['at'][:10], r['sid']
            if od != open_day: prefix = []; open_day = od
            if r['role'] == 'core':
                day = liquidity[window, od]['signal_day']; i = intents[day, sid]; op = ops[day, sid]
                assert op['core_Q'] is True and op['held'] is False and not op['barriers'] and 'core' in op['roles']
                assert i['epoch'] is not None and not i.get('size_reject') and i['cap'] > 0
                prior = [t for t in fills[sid] if t['at'] < day + ' 23:59:59']
                assert not any(t['epoch'] == i['epoch'] for t in prior)
                tags = set(r['result'].split(',')); route_numeric = bool(tags) and tags <= NUMERIC
                s = states[day][op['sector']]; level = int(s['financial_level'])
                cp = receipt(window, sid, day) if op['CP1_id'] else None
                if cp:
                    assert cp['receipt_id'] == op['CP1_id'] and cp['canonical_series'] == sid and cp['confirmed_day'] == day
                    assert int(cp['source_segment']) == i['epoch'][0] and cp['formation_start_exclusive'] <= cp['formation_end_inclusive'] == day
                fresh = bool(cp and not cp['trace_unknown'] and cp['receipt_id'] not in consumed)
                rule = effective(rules['quantity_versions'][sid], od)['rule']
                front = [reservations[k] for k in prefix if reservations[k]['sector'] == op['sector']]
                blocked = [x['key'] for x in front if x['pool'] == 'probe' and x['attempt'] == s['attempt']]
                pre = route_numeric and fresh and level >= 1
                candidate = pre and tags <= ALLOWED and not blocked
                row = dict(key='|'.join([window, day, sid, 'core']), window=window, sid=sid, name=meta[sid]['name'], industry=meta[sid]['industry'], signal_day=day, OPEN=od,
                    period=period(day), year=day[:4], funding_stream_index=index, original_result=r['result'], original_failure_set=sorted(tags),
                    stage='reserved_unchanged' if r['result'] == 'reserved' else 'OPEN_preview_failed' if r['result'] in PREVIEW else 'probe_route_rejected',
                    original_intent=i, original_opportunity=op, decision_NAV=ds[day]['nav'], original_full_CORE_qualification_source='native op.core_Q+flat/barriers+actual frozen CORE intent+actual fill epoch check',
                    original_i_buy_source='Original native Facts.packet(I) full CORE_Q upstream proof; not a newly recomputed signal',
                    industry_financial_at_signal=s, active_at_OPEN_source='native CORE route passed active guard' if route_numeric or r['result'] == 'reserved' else 'native industry_invalidated' if r['result'] == 'industry_invalidated' else 'unknown_before_route',
                    same_day_canonical_CP=cp, CP_unconsumed_at_candidate=fresh, frozen_CORE_epoch_unconsumed=True,
                    dated_OPEN_minimum=rule['buy_minimum'], dated_OPEN_quantity_rule=rule,
                    raw_reject_set_eligible=route_numeric and tags <= ALLOWED, dual_proof_mature_before_reject_gate=pre,
                    preexisting_S0_buy_reserve=liquidity[window, od]['prior_existing_submitted_order_reserve'],
                    same_OPEN_prior_same_attempt_probe_order_keys=blocked,
                    native_same_attempt_migration_necessary_pass=not blocked,
                    narrow_fallback_necessary_candidate=candidate,
                    prior_OPEN_reservations_ref='ORIGINAL_RESERVED_ORDERS.json with same window/OPEN and funding_stream_index < candidate',
                    prior_original_reserve_count=len(prefix), prior_original_same_sector_reserve_count=len(front),
                    prior_original_reserved_gross=str(sum((D(reservations[k]['gross']) for k in prefix), D(0))),
                    prior_original_reserved_buy_fees=str(sum((D(reservations[k]['buy_fee']) for k in prefix), D(0))),
                    prior_original_same_sector_reserved_gross=str(sum((D(x['gross']) for x in front), D(0))),
                    original_S0_cash=liquidity[window, od]['S0_available'], original_decision_cash10=liquidity[window, od]['original_extra10_buffer'],
                    exact_pre_candidate_SC_SR_NAV='UNKNOWN_NOT_RECONSTRUCTED', first_unique_failure='NOT_INFERRED_FROM_MERGED_TAGS')
                mother.append(row)
            if r['result'] == 'reserved':
                j = real[od, sid, r['role']]; a = audits[j['order']]; order = b['budget']['orders'][j['budget_order']]
                key = window + '|' + j['budget_order']; assert key not in reservations
                reservations[key] = dict(key=key, window=window, OPEN=od, funding_stream_index=index, sid=sid, role=r['role'], sector=order['sector'], episode=order['episode'], attempt=order['attempt'], pool=j['pool'], CP1_id=j['receipt'], shares=j['shares'], price=j['price'], gross=a['gross_budget_cny'], buy_fee=a['fee_reserved_cny'], native_order_id=j['order'], native_budget_order=j['budget_order'], actual_fills=buys[j['budget_order']], before_buys_fill=True, same_OPEN_Tplus1_not_sellable=True)
                prefix.append(key)
                if j['receipt']: consumed.add(j['receipt'])
        checkpoint(window + '_original_join')
    write('ALL_CORE_OPEN_ORIGINAL_MOTHER.jsonl.gz', mother); save('ORIGINAL_RESERVED_ORDERS.json', reservations)
    checkpoint('mother_saved')
    detail = []; fee_cache = {}
    for r in mother:
        if not r['narrow_fallback_necessary_candidate']: continue
        i = r['original_intent']; day = r['signal_day']; sid = r['sid']; cp = r['same_day_canonical_CP']
        venue = effective(rules['venue_versions'][sid], day)['venue']; z = effective(rules['fee_versions'][venue], day)['schedule']
        if z['schedule_id'] not in fee_cache: fee_cache[z['schedule_id']] = LR.L.FeeSchedule(z['schedule_id'], tuple(LR.L.FeeComponent(**c) for c in z['components']))
        fee = fee_cache[z['schedule_id']]; par = D(rules['security_metadata'][sid]['par_value']); ref = D(i['reference_price']); fl = D(i['frozen_floor_raw']); factor = D(i['floor']) / fl
        q = r['dated_OPEN_minimum']; mcp = max(D(i['floor']), D(str(cp['original_candidate']))) / factor
        minimum = dict(q=q, signal_reference_price=str(ref), I_floor_raw_signal=str(fl), CP_candidate_causal=str(cp['original_candidate']), Mobile_max_I_CP_raw_signal=str(mcp),
            CORE_fee_risk_at_signal_reference=str(LR.protection_risk(q, ref, fl, fee, par)), Mobile_fee_risk_at_signal_reference=str(LR.protection_risk(q, ref, mcp, fee, par)),
            frozen_CORE_risk_budget=i['risk_budget'], frozen_cap=i['cap'], frozen_gross_budget=i['budget'],
            scope='saved frozen signal reference scalar; not actual OPEN risk/quantity computation')
        mobile = [x for x in reservations.values() if x['window'] == r['window'] and x['OPEN'] == r['OPEN'] and x['sid'] == sid and x['role'] == 'mobile']
        witness = dict(proven=False, reason='no_same_OPEN_original_confirmed_MOBILE_reservation')
        if mobile:
            assert len(mobile) == 1; m = mobile[0]
            venue = effective(rules['venue_versions'][sid], r['OPEN'])['venue']; zz = effective(rules['fee_versions'][venue], r['OPEN'])['schedule']; fs = LR.L.FeeSchedule(zz['schedule_id'], tuple(LR.L.FeeComponent(**c) for c in zz['components']))
            mq = int(m['shares']); price = D(m['price']); minfee = LR.fees(q, price, fs, 'buy', par); largefee = LR.fees(mq, price, fs, 'buy', par)
            checks = dict(funding_rows_adjacent=m['funding_stream_index'] == r['funding_stream_index'] + 1, actual_confirmed=m['pool'] == 'confirmed', same_CP=m['CP1_id'] == cp['receipt_id'], qmin_no_larger=q <= mq, min_BUY_legal=(q >= r['dated_OPEN_quantity_rule']['buy_minimum'] and (q-r['dated_OPEN_quantity_rule']['buy_minimum']) % r['dated_OPEN_quantity_rule']['buy_step'] == 0), actual_fee_exact=largefee == D(m['buy_fee']), fee_non_decreasing=minfee <= largefee, original_CORE_sector_risk_pass='sector_risk' not in r['original_failure_set'], original_CORE_preview_pass=r['stage'] == 'probe_route_rejected')
            witness = dict(proven=all(checks.values()), checks=checks, original_MOBILE_order_key=m['key'], reserved_shares=mq, qmin=q, min_buy_fee=str(minfee), reserved_buy_fee=m['buy_fee'], scope='original prefix minimum-only existence, assuming audited typed role/token admission; not max, altered path execution or PnL')
        d = dict(r, minimum_frozen_signal_scalar=minimum, original_confirmed_MOBILE_minimum_existence_witness=witness)
        detail.append(d)
    write('NARROW_CANDIDATES.jsonl.gz', detail)
    checkpoint('narrow_detail_saved')
    first = {}; eligible_first = {}
    for r in mother:
        first.setdefault(group(r), r)
        if r['narrow_fallback_necessary_candidate']: eligible_first.setdefault(group(r), r)
    def agg(rs):
        rs = list(rs); return dict(Counter(dict(total=len(rs), original_probe_reserved=sum(r['stage']=='reserved_unchanged' for r in rs), original_preview_failed=sum(r['stage']=='OPEN_preview_failed' for r in rs), route_rejected=sum(r['stage']=='probe_route_rejected' for r in rs), allowed_failure_set=sum(r['raw_reject_set_eligible'] for r in rs), dual_CP_mature_numeric=sum(r['dual_proof_mature_before_reject_gate'] for r in rs), dual_CP_mature_cash_block=sum(r['dual_proof_mature_before_reject_gate'] and 'cash_or_original_reserve' in r['original_failure_set'] for r in rs), dual_CP_mature_sector_risk_block=sum(r['dual_proof_mature_before_reject_gate'] and 'sector_risk' in r['original_failure_set'] for r in rs), same_attempt_front_probe_migration_block=sum(r['raw_reject_set_eligible'] and r['dual_proof_mature_before_reject_gate'] and not r['native_same_attempt_migration_necessary_pass'] for r in rs), narrow_candidates=sum(r['narrow_fallback_necessary_candidate'] for r in rs))))
    summary = dict(complete=True, elapsed_seconds=time.monotonic()-START, hard_limit_seconds=LIMIT, raw=agg(mother), first_source_I_any_CORE_OPEN=agg(first.values()), unique_source_I_with_any_eligible=len(eligible_first),
        by_window={w:agg(r for r in mother if r['window']==w) for w in ['long','strong']}, by_period={p:agg(r for r in mother if r['period']==p) for p in sorted({r['period'] for r in mother})},
        semiconductors_by_period={p:agg(r for r in mother if r['period']==p and r['industry']=='半导体') for p in sorted({r['period'] for r in mother})},
        minimum_existence_witnesses=sum(r['original_confirmed_MOBILE_minimum_existence_witness']['proven'] for r in detail), narrow_failure_sets=dict(Counter(r['original_result'] for r in detail)), narrow_candidates=len(detail),
        candidate_source_I_first_keys=[r['key'] for r in eligible_first.values()], raw_first_definition='earliest original CORE OPEN outcome per window/sid/original source-I epoch, includes successful original probe; not industry-first8335',
        no_new_account=True, no_new_marks=True, no_route_projection=True, needed_unknowns=['Full current SC/SR/NAV numerical state, original CORE OPEN maxq and quote when not already saved, full changed-path competition and execution remain uncomputed.'])
    save('SUMMARY.json', summary); save('SOURCE_SHA256.json', SHA)
    target = read(ROOT / 'industry_capital_v1/actual25_role_entry/ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json')
    tkeys = {'strong|' + x['signal_day'] + '|' + x['sid'] + '|core': x for x in target if x['original_planning_branch']=='original_CORE_intent_but_OPEN_rejected_before_MOBILE_fill'}
    rowsby = {r['key']:r for r in mother}; detby = {r['key']:r for r in detail}
    save('ALL11_TARGET_CROSSCHECK.json', [dict(original_25_saved=t, full_mother=rowsby[k], narrow_candidate_detail=detby.get(k)) for k,t in tkeys.items()])
    assert len(tkeys)==11 and sum(rowsby[k]['narrow_fallback_necessary_candidate'] for k in tkeys)==9
    checkpoint('complete'); save('SOURCE_SHA256.json', SHA)
    print(json.dumps({k:v for k,v in summary.items() if k != 'candidate_source_I_first_keys'}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    try: main()
    except Exception as error:
        save('STOP_STATUS.json', dict(complete=False, kind=type(error).__name__, reason=str(error), seconds=time.monotonic()-START, stages=STAGES)); raise
