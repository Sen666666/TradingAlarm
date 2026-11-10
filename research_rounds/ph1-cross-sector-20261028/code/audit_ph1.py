"""Read-only PH1 contract and independent cash/share accounting audit.

This module never imports the PH1 runner or phase policy, and never starts an
account simulation.  Phase expectations come from fills and frozen E0/F facts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal as D
import argparse
import math
import sys

from ph_common import O, SA, PRIOR, ROOT, PREPS, FAST, STRICT, VARIANTS, read, rows, save, pd

sys.path.insert(0, str(PRIOR / 'code'))
import experiment as P

ZERO = D(0)
EPS = D('1e-8')
U = float.fromhex('0x1.0000000000000p-53')
GAMMA = 4 * U / (1 - 4 * U)


def cmp(a, b):
    a, b = float(a), float(b)
    assert math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0, (a, b)
    return 0 if abs(a - b) <= GAMMA * max(a, b) else 1 if a > b else -1


def higher(a, b):
    return float(b) if cmp(b, a) > 0 else float(a)


def stamp(day):
    return None if day is None or pd.isna(day) else pd.Timestamp(str(day)[:10] + ' 15:00:00', tz='Asia/Shanghai').isoformat()


def exact(a, b, context):
    """NaN-aware scalar/container comparison without forgiving price errors."""
    if isinstance(b, dict):
        assert isinstance(a, dict) and set(a) == set(b), (context, a, b)
        for k in b:
            exact(a[k], b[k], (context, k))
    elif isinstance(b, (float, int)) and not isinstance(b, bool):
        if isinstance(b, float) and math.isnan(b):
            assert a is None or math.isnan(float(a)), (context, a, b)
        else:
            assert a == b, (context, a, b)
    else:
        assert a == b, (context, a, b)


def independent_step(state, obs, policy):
    """Independent state reducer; no production PH1 function is called."""
    new = dict(state)
    phase, old = state['phase'], float(state['P'])
    diag = dict(policy=policy, phase_before=phase, phase_after=phase,
                P_before=old, P_after=old, exit_required=False,
                exit_reason=None, exit_causes=[], handoff=False,
                handoff_checks=None, F_eligible=False, F_applied=False)
    if phase == 'EXIT_PENDING':
        diag.update(exit_required=True, exit_reason='locked', exit_causes=['locked'])
        return new, diag
    assert phase in ('TRIAL', 'BRIDGE', 'TREND')
    if policy == 'F':
        assert phase == 'TRIAL'
    reasons = []
    if obs['exit_pending']:
        reasons.append('locked')
    if not obs['risk_on']:
        reasons.append('ACT')
    if not obs['original_up']:
        reasons.append('E0')
    if not reasons and cmp(obs['close'], old) <= 0:
        reasons.append('protection')
    if reasons:
        new['phase'] = 'EXIT_PENDING'
        diag.update(phase_after='EXIT_PENDING', exit_required=True,
                    exit_reason=reasons[0], exit_causes=reasons)
        return new, diag
    E = float(obs['E'])
    assert cmp(E, obs['E_prev']) >= 0
    mature = False
    if policy == 'PH' and phase == 'TRIAL':
        checks = dict(original_up=True, E_up=obs['E_up'], pivot_after_entry=False,
                      pivot_above_entry_support=False, E_raised=cmp(E, obs['E_prev']) > 0)
        if obs['E_up']:
            assert pd.Timestamp(obs['pivot_at']) <= pd.Timestamp(obs['at'])
            checks['pivot_after_entry'] = pd.Timestamp(obs['pivot_at']) > pd.Timestamp(state['entry_at'])
            checks['pivot_above_entry_support'] = cmp(obs['pivot'], state['E_entry']) > 0
        diag['handoff_checks'] = checks
        mature = all(checks.values())
    if mature:
        new['L_star'] = higher(old, E)
        new['P'] = new['L_star']
        new['phase'] = 'TREND' if cmp(E, new['L_star']) >= 0 else 'BRIDGE'
        diag['handoff'] = True
    else:
        new['P'] = higher(old, E)
        if phase != 'TRIAL':
            assert cmp(old, state['L_star']) >= 0
            if phase == 'BRIDGE' and cmp(E, state['L_star']) >= 0:
                new['phase'] = 'TREND'
        elif obs['F_up']:
            assert pd.Timestamp(obs['F_pivot_at']) <= pd.Timestamp(obs['at'])
            if pd.Timestamp(obs['F_pivot_at']).date() >= pd.Timestamp(state['entry_at']).date():
                diag['F_eligible'] = True
                diag['F_applied'] = cmp(obs['F_pivot'], new['P']) > 0
                new['P'] = higher(new['P'], obs['F_pivot'])
    diag.update(phase_after=new['phase'], P_after=new['P'])
    assert cmp(new['P'], old) >= 0
    return new, diag


def contract_checker(sector, variant, run_root):
    risk_sizing = variant.startswith('R_')
    exit_policy = variant.split('_', 1)[1]
    tables = {}
    rules = read(run_root / 'execution-rules-v2.json')
    proto = read(P.A.OLD / 'inputs-v2/economic-protocol.json')
    from market_rules import market_identity_on, version_on

    def table(kind, sid):
        key = (kind, sid)
        if key not in tables:
            folder = STRICT[sector] if kind == 'strict' else FAST[sector] if kind == 'fast' else O / 'events' / sector
            f = pd.read_parquet(folder / f'{sid}.parquet')
            assert f.index.is_unique and f.index.is_monotonic_increasing, key
            tables[key] = f
        return tables[key]

    def fees(sid, day, side, gross, qty, mult):
        identity = market_identity_on(rules, sid, pd.Timestamp(day).date(), proto['approved_proxy_ids'])
        spec = version_on(rules['fee_versions'][identity['venue']], str(day)[:10], proto['approved_proxy_ids'])['schedule']
        schedule = P.A.ledger.FeeSchedule(spec['schedule_id'], tuple(P.A.ledger.FeeComponent(**v) for v in spec['components']))
        return sum(schedule.incremental(side, gross, {}, {}, mult, shares=qty,
                       par_value=rules['security_metadata'].get(sid, {}).get('par_value')).values(), ZERO)

    def check(aid, obj, ds, facts, records):
        assert aid.startswith('S__')
        mult = 2 if aid.endswith('cost2') else 1
        slip = D('.0005') * mult
        intents, classes, reserved, risk_orders = {}, {}, {}, {}
        totals = defaultdict(lambda: dict(qty=0, gross=ZERO, fees=ZERO))
        quantities = defaultdict(int)
        starts, ended, checkpoints, needed_exits = set(), set(), set(), set()
        awaiting_start, live, locked = {}, {}, set()
        risk_by_day = {r['at'][:10]: r for r in obj['audit_log'] if r['kind'] == 'risk_checkpoint'}
        exit_dates = defaultdict(list)
        expected_seq, counts = 0, Counter()
        forbidden = {'intent_create', 'intent_end', 'waiting_support_raise', 'waiting_support_inherited',
                     'fast_support_raise', 'fast_support_exit', 'rotation_started', 'rotation_buy_reserved',
                     'rotation_finished', 'risk_fill_bound'}

        def latest(sid, day):
            f = facts[sid]
            j = f.index.searchsorted(pd.Timestamp(day), side='right') - 1
            assert j >= 0, (sid, day)
            return f, j, f.iloc[j]

        def loss(sid, day, quantity, gross, buyfees, floor):
            sellprice = floor * (1 - slip)
            sf = fees(sid, day, 'sell', quantity * sellprice, quantity, mult)
            return max(ZERO, gross + buyfees - quantity * sellprice + sf)

        for r in obj['audit_log']:
            kind = r['kind']
            assert kind not in forbidden, (aid, variant, 'unexpected mechanism', kind)
            if kind == 'reserve':
                assert r['order_id'] not in reserved
                reserved[r['order_id']] = r
            elif kind == 'risk_checkpoint':
                assert r['policy'] == 'ACT20_BREAK'
                counts['act_checkpoint'] += 1
            elif kind == 'entry_contract':
                sid, day, oid = r['sid'], r['decision_at'][:10], r['order_id']
                assert r['mode'] == 'S' and oid in reserved and oid not in intents
                assert pd.Timestamp(day) in facts[sid].index and bool(facts[sid].loc[day, 'i_buy'])
                strict = table('strict', sid)
                assert pd.Timestamp(day) in strict.index and bool(strict.loc[day, 'strict_target'])
                assert D(r['floor_signal']) == D(str(facts[sid].loc[day, 'i_floor']))
                assert D(r['budget']) <= D('.15') * D(r['nav']) + D('.01')
                assert D(r['risk_budget']) == D('.01') * D(r['nav'])
                assert risk_by_day[day]['on']
                assert not quantities[sid], (aid, sid, 'unsolicited add-on buy')
                assert sid not in locked, (aid, sid, 'reentry before liquidation')
                if exit_dates[sid]:
                    assert day > max(exit_dates[sid]), (sid, 'same exit close retry')
                intents[oid] = r
                counts['original_i_and_amt_gate_original_support'] += 1
            elif kind == 'intent_entry_class':
                assert r['original'] is True and r['origin'] is None and r['window'] == 0
                assert r.get('waiting_floor') is None and r['order_id'] in intents
                classes[r['order_id']] = r
            elif kind == 'ph_risk_reservation':
                assert risk_sizing and r['variant'] == variant
                oid, sid, day = r['order_id'], r['sid'], r['at'][:10]
                z = intents[oid]
                assert oid not in risk_orders
                price = D(str(facts[sid].loc[day, 'raw_close'])) * (1 + slip)
                assert D(r['reference_price']) == price
                assert D(r['original_budget']) <= D('.15') * D(z['nav']) + D('.01')
                assert D(r['R_a']) == D(z['risk_budget'])
                qty = int(r['target_shares'])
                assert qty > 0 and qty >= int(reserved[oid]['target_shares'])
                assert qty * price <= D(r['original_budget'])
                floor = D(z['floor_signal']) / D(str(facts[sid].loc[day, 'factor']))
                nominal = loss(sid, day, qty, qty * price, fees(sid, day, 'buy', qty * price, qty, mult), floor)
                assert abs(nominal - D(r['nominal_loss'])) <= EPS and nominal <= D(r['R_a']) + EPS
                risk_orders[oid] = r
                counts['independent_risk_reservation'] += 1
            elif kind == 'fill':
                x = r['receipt'];sid, day, oid = x['security_id'], x['at'][:10], r['order_id']
                qty = int(x['shares'])
                assert x['at'][11:19] == '09:30:00'
                assert D(r['price']) == D(r['raw_open']) * (1 + slip if x['side'] == 'buy' else 1 - slip)
                if x['side'] == 'buy':
                    z = intents[oid]
                    assert oid in classes and z['decision_at'][:10] < day
                    assert sid not in locked
                    _, _, f = latest(sid, day)
                    floor = D(z['floor_signal']) / D(str(f.factor))
                    assert D(r['raw_open']) > floor
                    if not quantities[sid]:
                        if variant != 'A_E0':
                            expected_seq += 1
                            awaiting_start[sid] = dict(phase='E0' if exit_policy == 'E0' else 'TRIAL',
                                P=float(z['floor_signal']), L_star=None, E_entry=float(z['floor_signal']),
                                entry_at=pd.Timestamp(x['at']).isoformat(), entry_segment=str(f.segment_id),
                                cycle_id=f'{sid}:{expected_seq}', order_id=oid, R_a=str(z['risk_budget']))
                    elif variant != 'A_E0':
                        assert live[sid]['order_id'] == oid and live[sid]['phase'] != 'EXIT_PENDING'
                    quantities[sid] += qty
                    t = totals[oid];t['qty'] += qty;t['gross'] += D(x['gross_cny']);t['fees'] += D(x['fees_cny'])
                    if variant != 'A_E0':
                        destination = awaiting_start.get(sid, live.get(sid))
                        destination['Loss_fill'] = str(loss(sid, day, t['qty'], t['gross'], t['fees'], floor))
                    assert t['qty'] <= int(reserved[oid]['target_shares'])
                    assert t['gross'] <= D(z['budget']) + EPS
                    if risk_sizing:
                        assert oid in risk_orders
                        assert loss(sid, day, t['qty'], t['gross'], t['fees'], floor) <= D(z['risk_budget']) + EPS
                    counts['independent_actual_buy_bounds'] += 1
                else:
                    assert sid in locked, (aid, sid, 'sale without exit request')
                    quantities[sid] -= qty
                    assert quantities[sid] >= 0
                    if not quantities[sid]:
                        locked.remove(sid)
                        if variant != 'A_E0':
                            ended.add(live[sid]['cycle_id'])
                    counts['actual_sell_lock'] += 1
            elif kind in ('split', 'split_fraction_floor_proxy'):
                quantities[r['sid']] = int(D(quantities[r['sid']]) * D(r['ratio']))
            elif kind == 'ph_risk_fill_check':
                assert risk_sizing and r['variant'] == variant
                oid, sid, day = r['order_id'], r['sid'], r['at'][:10]
                z, t = intents[oid], totals[oid]
                _, _, f = latest(sid, day)
                floor = D(z['floor_signal']) / D(str(f.factor))
                assert int(r['filled_shares']) == t['qty'] and D(r['gross']) == t['gross'] and D(r['buy_fees']) == t['fees']
                assert D(r['floor_raw']) == floor and D(r['R_a']) == D(z['risk_budget']) and D(r['budget']) == D(z['budget'])
                nominal = loss(sid, day, t['qty'], t['gross'], t['fees'], floor)
                assert abs(D(r['nominal_loss']) - nominal) <= EPS and nominal <= D(z['risk_budget']) + EPS
                counts['independent_cumulative_risk_fill'] += 1
            elif kind == 'ph_cycle_start':
                assert variant != 'A_E0' and r['variant'] == variant
                sid = r['sid'];expected = awaiting_start.pop(sid)
                assert sid not in live and r['quantity'] == quantities[sid] > 0
                for k, value in expected.items():
                    exact(r[k], value, (aid, sid, 'initial', k))
                assert expected['cycle_id'] not in starts
                starts.add(expected['cycle_id']);live[sid] = expected
                counts['cycle_initialized_once_after_actual_fill'] += 1
            elif kind == 'ph_cycle_fill':
                assert variant != 'A_E0' and r['variant'] == variant
                sid = r['sid'];state = live[sid]
                assert r['quantity'] == quantities[sid] > 0
                for k, value in state.items():
                    exact(r[k], value, (aid, sid, 'partial_fill', k))
                counts['partial_fill_keeps_cycle_updates_loss'] += 1
            elif kind == 'ph_checkpoint':
                assert exit_policy != 'E0' and r['variant'] == variant
                sid, day = r['sid'], r['at'][:10]
                assert sid in live and r['quantity'] == quantities[sid] > 0
                state = live[sid]
                exact(r['state_before'], state, (aid, sid, day, 'state_before'))
                f, j, row = latest(sid, day)
                assert str(row.segment_id) == state['entry_segment'], (sid, day, 'undefined source transition')
                today = pd.Timestamp(day) in f.index
                er = table('event', sid).loc[day] if today else None
                ff = table('fast', sid);fr = ff.loc[day] if pd.Timestamp(day) in ff.index else None
                expected_obs = dict(at=pd.Timestamp(r['at']).isoformat(), close=float(row.close), E=float(row.i_floor),
                    E_prev=float(f.iloc[j-1].i_floor) if j > 0 else None,
                    E_up=bool(today and er is not None and er['event'] == 1),
                    pivot=float(er['pivot']) if er is not None and math.isfinite(er['pivot']) else None,
                    pivot_at=stamp(er['pivot_date']) if er is not None else None,
                    F_up=bool(today and fr is not None and fr['event'] == 1),
                    F_pivot=float(fr['pivot']) if fr is not None and math.isfinite(fr['pivot']) else None,
                    F_pivot_at=stamp(fr['pivot_date']) if fr is not None else None,
                    risk_on=bool(risk_by_day[day]['on']), original_up=bool(row.i_target), exit_pending=sid in locked)
                exact(r['obs'], expected_obs, (aid, sid, day, 'observation'))
                assert r['observed'] is today
                expected, diag = independent_step(state, expected_obs, 'F' if exit_policy == 'F' else 'PH')
                exact(r['state_after'], expected, (aid, sid, day, 'state_after'))
                for k, value in diag.items():
                    exact(r[k], value, (aid, sid, day, k))
                if 'mature' in r:
                    assert r['mature'] is diag['handoff'], (aid, sid, day, 'mature alias')
                assert r['cycle_id'] == state['cycle_id'] and (sid, day) not in checkpoints
                checkpoints.add((sid, day));live[sid] = expected
                if diag['exit_required']:
                    needed_exits.add((sid, day))
                if diag['handoff']:
                    counts['independently_proven_M'] += 1
                counts['phase_checkpoints'] += 1
                counts['F_application' if diag['F_applied'] else 'no_F_application'] += 1
            elif kind == 'exit_request':
                sid, day = r['sid'], r['at'][:10]
                _, _, f = latest(sid, day)
                if exit_policy == 'E0':
                    assert not bool(f.i_target) or not risk_by_day[day]['on'], (sid, day, 'non-original E0 exit')
                else:
                    assert (sid, day) in needed_exits or sid in locked, (sid, day, 'unexplained stage exit')
                locked.add(sid);exit_dates[sid].append(day)
                counts['explained_exit_requests'] += 1
            elif kind == 'ph_cycle_end':
                sid = r['sid']
                assert variant != 'A_E0' and r['variant'] == variant and not quantities[sid]
                state = live.pop(sid)
                assert state['cycle_id'] in ended
                for k, value in state.items():
                    exact(r[k], value, (aid, sid, 'liquidation', k))
                counts['cycle_closed_only_after_liquidation'] += 1
            elif kind.startswith('ph_risk_'):
                assert risk_sizing, (variant, kind)

        assert not awaiting_start
        assert set(intents) == set(classes)
        if risk_sizing:
            assert set(intents) == set(risk_orders)
            assert counts['independent_actual_buy_bounds'] == counts['independent_cumulative_risk_fill']
        if variant == 'A_E0':
            assert not starts and not checkpoints
        if exit_policy != 'E0':
            for d in ds:
                day = d['at'][:10]
                for sid in d['positions']:
                    f, _, row = latest(sid, day)
                    if pd.Timestamp(day) in f.index or not risk_by_day[day]['on'] or not bool(row.i_target):
                        assert (sid, day) in checkpoints, (aid, sid, day, 'missing held-close checkpoint')
            for sid, day in needed_exits:
                assert any(x <= day for x in exit_dates[sid]), (sid, day, 'missing latched exit request')
        assert starts - ended == {v['cycle_id'] for v in live.values()}
        return dict(passed=True, checks=dict(counts), variant=variant,
                    independently_reconstructed_phase=True, no_policy_helper_reuse=True)
    return check


def audit(sector, variant, stage='economic'):
    root = O / sector / variant
    analyzer = P.A
    analyzer.CORE = PRIOR / 'input' if sector == 'TECH' else PREPS[sector]
    analyzer.PREP, analyzer.HERE = PREPS[sector], root
    analyzer.check_contract = contract_checker(sector, variant, root)
    analyzer.main(stage)


def control(sector, stage='economic'):
    root, reference = O / sector / 'A_E0', SA / sector / 'AMT' / 'accounts-v2'
    source = root / ('technical/short-v2' if stage == 'short' else 'accounts-v2')
    daily = rows(source / 'daily.jsonl.gz')
    previous = {(r['account'], r['at']): r for r in rows(reference / 'daily.jsonl.gz')}
    assert daily
    for r in daily:
        assert r == previous[r['account'], r['at']], (r['account'], r['at'], 'daily identity')
    end = max(r['at'] for r in daily)
    accounts = sorted({r['account'] for r in daily})
    for aid in accounts:
        assert read(source / f'{aid}.json')['fills'] == [r for r in read(reference / f'{aid}.json')['fills'] if r['at'] <= end], aid
    out = dict(passed=True, accounts=len(accounts), daily_rows=len(daily), complete_daily_rows_exact=True,
               fills_exact=True, reference=str(reference), final_timestamp=end)
    save(root / ('control-short.json' if stage == 'short' else 'control-full.json'), out)
    return out


def prefix(sector, variant):
    root = O / sector / variant
    full, short = root / 'accounts-v2', root / 'technical/prefix'
    counts = {}
    for name in ('daily', 'decisions'):
        ref = {(r['account'], r['at']): r for r in rows(full / f'{name}.jsonl.gz')}
        current = rows(short / f'{name}.jsonl.gz')
        assert current
        for r in current:
            assert r['at'][:10] <= '2026-06-30' and r == ref[r['account'], r['at']], (name, r['account'], r['at'])
        counts[name] = len(current)
    accounts = sorted({r['account'] for r in rows(short / 'daily.jsonl.gz')})
    for aid in accounts:
        a, b = read(short / f'{aid}.json'), read(full / f'{aid}.json')
        assert a['fills'] == [r for r in b['fills'] if r['at'][:10] <= '2026-06-30'], aid
        assert [r for r in a['audit_log'] if r['kind'].startswith('ph_')] == [r for r in b['audit_log'] if r['kind'].startswith('ph_') and r['at'][:10] <= '2026-06-30'], (aid, 'phase/risk prefix')
    result = dict(passed=True, accounts=len(accounts), cutoff='2026-06-30', fills_exact=True,
                  phase_and_risk_logs_exact=True, **counts)
    save(root / 'prefix-verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['audit', 'control', 'prefix'])
    parser.add_argument('sector', choices=['TECH', 'DRUG'])
    parser.add_argument('variant', choices=VARIANTS)
    parser.add_argument('stage', nargs='?', default='economic', choices=['short', 'economic'])
    args = parser.parse_args()
    if args.action == 'audit':
        audit(args.sector, args.variant, args.stage)
    elif args.action == 'control':
        assert args.variant == 'A_E0'
        control(args.sector, args.stage)
    else:
        prefix(args.sector, args.variant)
