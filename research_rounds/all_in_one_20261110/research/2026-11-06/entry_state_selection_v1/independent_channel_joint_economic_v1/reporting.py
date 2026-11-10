"""Frozen §12 research attribution. Import-safe: no file/network/strategy I/O.

All inputs are caller supplied records or DataFrames. Main unit is stock/window,
not winning or closed rounds. Financial and execution evidence is not inferred.
Amounts are currency PnL, never shared-account returns or tradable profits.
"""
from collections import Counter, defaultdict, deque
from itertools import product
import json
import math

PROTOCOL_SHA256 = '94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687'
KEY = ('sid', 'window', 'arm', 'lane')


def records(value):
    if value is None:
        return []
    if hasattr(value, 'to_dict'):
        return value.to_dict('records')
    return [dict(r) for r in value]


def number(value, label):
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f'{label} must be finite')
    return x


def key(r):
    return tuple(str(r.get(k, r.get('owner_lane') if k == 'lane' else '')) for k in KEY)


def indexed(rows, label):
    out = {}
    for r in records(rows):
        k = key(r)
        if k in out:
            raise ValueError(f'duplicate {label}: {k}')
        out[k] = r
    return out


def exact_permit_audit(reference, candidate):
    """Compare full records with duplicate multiplicity; do not project fields."""
    canonical = lambda rows: Counter(json.dumps(r, sort_keys=True, ensure_ascii=False,
                                               allow_nan=False, default=str) for r in records(rows))
    a, b = canonical(reference), canonical(candidate)
    return {'exact': a == b, 'reference_count': sum(a.values()),
            'candidate_count': sum(b.values()),
            'missing': list((a-b).elements()), 'extra': list((b-a).elements())}


def _role(r):
    role = str(r['role']).upper()
    return 'PROBE' if role == 'CORE' else role


def build_report(roster, windows, arms, lanes, actions=(), claims=(), states=(),
                 terminal_marks=(), coverage=(), *, expected_roster_size=1709,
                 reference_permits=None, candidate_permits=None, ab_changes=(),
                 stock_adjustments=(), closed_cash_checks=(), core_diagnostics=(),
                 pvr_diagnostics=()):
    """Return JSON-ready tables, no writes and no implicit source discovery.

    states: one sid/window/arm/lane row, status NEVER_ENTERED/CLOSED/
      OPEN_CENSORED/UNKNOWN; optional last_known_mark/day, frozen_amount,
      unknown_inventory/order/equity. NEVER_ENTERED asserts no responsibilities.
    stock_adjustments: forbidden under frozen PURE_CASH-only contract.
    closed_cash_checks: same key + round_id, cash_plus_receivable; provide closed
      round cash+receivable PnL, not account cash. Claims need round_id for checks.
    actions: same key + round_id, role, side BUY/SELL, q, price, fee,
      day, known_day, sequence. Caller splits multi-role sells with apportioned
      actual sell fees. Only known fills belong here; unfilled orders in states.
    claims: claim_id, amount, legal_ex_confirmed bool, tax_scenario NET80,
      receivable; one row per claim (pay is not another income row).
    terminal_marks: key + round_id, role, q, verified bool, mark_raw,
      sell_slippage (fraction), estimated_dated_sell_fee, terminal_day.
      Caller verifies uniform endpoint, dated fee and inventory evidence.
    coverage: same key + financial_covered bool, reason. Missing is unavailable.
    Arms ordered [baseline, joint]. Lanes normally AB, PRICE; absent PRICE in
      baseline needs explicit NEVER_ENTERED rows, not fabricated zeros.
    """
    roster = [str(s) for s in roster]
    windows, arms, lanes = map(lambda xs: [str(x) for x in xs], (windows, arms, lanes))
    if len(roster) != expected_roster_size or len(set(roster)) != len(roster):
        raise ValueError('fixed roster cardinality/uniqueness failed')
    if len(arms) != 2 or len(set(arms)) != 2:
        raise ValueError('exactly two distinct FULL arms required')
    if not windows or not lanes or len(set(windows)) != len(windows) or len(set(lanes)) != len(lanes):
        raise ValueError('windows and lanes must be nonempty and unique')
    universe = set(product(roster, windows, arms, lanes))
    state, cov = indexed(states, 'state'), indexed(coverage, 'coverage')
    grouped, claim_groups, mark_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    for source, target in ((actions, grouped), (claims, claim_groups), (terminal_marks, mark_groups)):
        for r in records(source):
            if key(r) not in universe:
                raise ValueError(f'out-of-roster record: {key(r)}')
            target[key(r)].append(r)
    if (set(state) | set(cov)) - universe:
        raise ValueError('out-of-roster state/coverage')
    if records(stock_adjustments):
        raise ValueError('UNADMITTED corporate share action: lock responsibility UNKNOWN upstream')
    check_groups = defaultdict(list)
    for check in records(closed_cash_checks):
        if key(check) not in universe:
            raise ValueError('out-of-roster closed cash check')
        check_groups[key(check)].append(check)
    round_reconciliation = []
    lane_rows = []
    for k in sorted(universe):
        s = state.get(k, {})
        status = s.get('status', 'UNKNOWN')
        if status not in {'NEVER_ENTERED', 'CLOSED', 'OPEN_CENSORED', 'UNKNOWN'}:
            raise ValueError('invalid responsibility status')
        lots, realized, fees = defaultdict(deque), 0.0, 0.0
        role_realized, role_fees = defaultdict(float), defaultdict(float)
        round_realized, round_income = defaultdict(float), defaultdict(float)
        seen_lots = set()
        entered, one_price = False, False
        acts = grouped[k]
        clock_keys = []
        for a in acts:
            clock_keys.append((str(a['known_day']), int(a['sequence'])))
            if str(a['known_day']) < str(a['day']):
                raise ValueError('fill known before trade day')
        if len(set(clock_keys)) != len(clock_keys):
            raise ValueError('ambiguous fill FIFO clock; sequence must disambiguate')
        for a in sorted(acts, key=lambda r: (str(r['known_day']), int(r['sequence']))):
            q, p, f = (number(a[n], n) for n in ('q', 'price', 'fee'))
            if q <= 0 or p <= 0 or f < 0:
                raise ValueError('invalid fill quantities/prices/fees')
            role = _role(a)
            rk = (str(a['round_id']), role)
            fees += f
            role_fees[role] += f
            one_price |= a.get('one_price_ohlc') is True
            side = str(a['side']).upper()
            if side == 'BUY':
                entered = True
                lot_id = str(a.get('lot_id', f"{a['known_day']}:{a['sequence']}"))
                if lot_id in seen_lots:
                    raise ValueError('duplicate buy lot_id')
                seen_lots.add(lot_id)
                lots[rk].append([q, q*p+f, lot_id])
            elif side == 'SELL':
                remaining, allocated = q, 0.0
                while remaining > 1e-9:
                    if not lots[rk]:
                        raise ValueError('sell exceeds known role/round inventory')
                    lot = lots[rk][0]
                    take = min(remaining, lot[0])
                    cost = lot[1] * take / lot[0]
                    allocated += cost
                    lot[0] -= take
                    lot[1] -= cost
                    remaining -= take
                    if lot[0] < 1e-9:
                        lots[rk].popleft()
                gain = q*p-f-allocated
                realized += gain
                role_realized[role] += gain
                round_realized[str(a['round_id'])] += gain
            else:
                raise ValueError('side must be BUY/SELL; normalize original actions first')
        income, receivable, claim_ids = 0.0, 0.0, set()
        unconfirmed = False
        for c in claim_groups[k]:
            cid = str(c['claim_id'])
            if cid in claim_ids:
                raise ValueError('duplicate claim income/payment row')
            claim_ids.add(cid)
            if c.get('legal_ex_confirmed') is not True or c.get('tax_scenario') != 'NET80':
                unconfirmed = True
                continue
            income += number(c['amount'], 'claim amount')
            if 'round_id' in c:
                round_income[str(c['round_id'])] += number(c['amount'], 'claim amount')
            elif check_groups[k]:
                raise ValueError('round_id required on claims for round cash reconciliation')
            receivable += number(c['receivable'], 'receivable')
        inventory = {rk: (sum(x[0] for x in ls), sum(x[1] for x in ls)) for rk, ls in lots.items() if ls}
        remaining_cost = sum(x[1] for x in inventory.values())
        for check in check_groups[k]:
            rid = str(check['round_id'])
            if any(rk[0] == rid for rk in inventory):
                raise ValueError('closed cash check targets open round')
            if rid not in {str(a['round_id']) for a in acts}:
                raise ValueError('closed cash check targets absent round')
            actual = round_realized[rid] + round_income[rid]
            expected = number(check['cash_plus_receivable'], 'closed cash+receivable')
            if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-7):
                raise ValueError(f'closed round cash+receivable mismatch: {rid}: {actual} != {expected}')
            round_reconciliation.append(dict(zip(KEY,k), round_id=rid,
                decomposed_pnl=actual, cash_plus_receivable=expected, exact_within_tolerance=True))
        if status == 'NEVER_ENTERED' and (acts or claim_groups[k] or inventory):
            raise ValueError('NEVER_ENTERED contradicts activity')
        if status == 'CLOSED' and inventory:
            raise ValueError('CLOSED contradicts remaining inventory')
        if status == 'NEVER_ENTERED' and any(s.get(n) is True for n in ('unknown_inventory', 'unknown_order', 'unknown_equity')):
            raise ValueError('NEVER_ENTERED contradicts unknown responsibilities')
        liability_unknown = status == 'UNKNOWN' or unconfirmed or any(s.get(n) is True for n in ('unknown_inventory', 'unknown_order', 'unknown_equity'))
        mark_map = {}
        for m in mark_groups[k]:
            rk = (str(m['round_id']), _role(m))
            if rk in mark_map:
                raise ValueError('duplicate terminal mark')
            mark_map[rk] = m
        liquidation = 0.0
        marked = not liability_unknown
        endpoints = set()
        if not liability_unknown:
            for rk, (q, cost) in inventory.items():
                m = mark_map.get(rk)
                if not m or m.get('verified') is not True or abs(number(m['q'], 'mark q')-q) > 1e-8:
                    marked = False
                    continue
                slip = number(m['sell_slippage'], 'sell slippage')
                fee = number(m['estimated_dated_sell_fee'], 'sell fee')
                raw = number(m['mark_raw'], 'mark price')
                if not 0 <= slip < 1 or raw <= 0 or fee < 0:
                    raise ValueError('invalid mark inputs')
                endpoints.add(str(m['terminal_day']))
                liquidation += q*raw*(1-slip)-fee
        unrealized = liquidation-remaining_cost if marked else None
        total = realized+income+unrealized if unrealized is not None else None
        covered = cov.get(k, {}).get('financial_covered') is True
        lane_rows.append(dict(zip(KEY, k), status=status, entered=entered,
            trade_realized=realized, confirmed_net80_income=income,
            realized_plus_income=realized+income, confirmed_receivable=receivable,
            remaining_cost=remaining_cost, terminal_net_liquidation=liquidation if marked else None,
            unrealized=unrealized, known_total_pnl=total, fees=fees,
            identifiable_pnl=realized+income, unknown_liability=liability_unknown,
            last_known_day=s.get('last_known_day'), last_known_mark=s.get('last_known_mark'),
            frozen_amount=s.get('frozen_amount'), financial_covered=covered,
            coverage_reason=cov.get(k, {}).get('reason', 'MISSING_COVERAGE'),
            comparable=covered and total is not None, one_price_ohlc_dependency=one_price,
            one_price_annotation_missing_count=sum(a.get('one_price_ohlc') not in (True, False) for a in acts),
            terminal_days=sorted(endpoints),
            historical_tradability='UNKNOWN', actual_ack='UNKNOWN',
            holding_sessions=s.get('holding_sessions'), risk_over_budget_gap=s.get('risk_over_budget_gap'),
            industry_gate_delay_sessions=s.get('industry_gate_delay_sessions'),
            pvr_resource_loss=s.get('pvr_resource_loss'),
            pvr_unknown_applications=s.get('pvr_unknown_applications'),
            pvr_unknown_slot_grants=s.get('pvr_unknown_slot_grants'),
            pvr_unknown_rank_blocks=s.get('pvr_unknown_rank_blocks'),
            role_trade_realized=dict(role_realized),
            role_fees=dict(role_fees), round_count=len({str(a['round_id']) for a in acts})))
    # Different windows may have different endpoints, but never within one window.
    for w in windows:
        if len({d for r in lane_rows if r['window'] == w for d in r['terminal_days']}) > 1:
            raise ValueError('nonuniform terminal endpoint within window')
    stock_rows = []
    by_stock = defaultdict(list)
    for r in lane_rows:
        by_stock[(r['sid'], r['window'], r['arm'])].append(r)
    for (sid, w, arm), rs in sorted(by_stock.items()):
        known = all(r['known_total_pnl'] is not None for r in rs)
        stock_rows.append({'sid': sid, 'window': w, 'arm': arm,
            'known_total_pnl': sum(r['known_total_pnl'] for r in rs) if known else None,
            'identifiable_pnl': sum(r['identifiable_pnl'] for r in rs),
            'comparable': all(r['comparable'] for r in rs),
            'closed': all(r['status'] in {'CLOSED', 'NEVER_ENTERED'} for r in rs),
            'never_entered': all(r['status'] == 'NEVER_ENTERED' for r in rs),
            'unknown_liability': any(r['unknown_liability'] for r in rs),
            'financial_covered': all(r['financial_covered'] for r in rs),
            'fees': sum(r['fees'] for r in rs),
            'coverage_reasons': sorted({r['coverage_reason'] for r in rs if not r['financial_covered']}),
            'one_price_ohlc_dependency': any(r['one_price_ohlc_dependency'] for r in rs)})
    summary, differences = [], []
    stock_index = {(r['sid'], r['window'], r['arm']): r for r in stock_rows}
    lane_index = {key(r): r for r in lane_rows}
    for w in windows:
        common = [sid for sid in roster if all(stock_index[sid,w,a]['comparable'] for a in arms)]
        for arm in arms:
            rs = [stock_index[sid,w,arm] for sid in roster]
            comparable = [r for r in rs if r['comparable']]
            closed = [r for r in rs if r['closed'] and r['known_total_pnl'] is not None]
            fin_closed = [r for r in closed if r['financial_covered']]
            summary.append({'window': w, 'arm': arm, 'fixed_denominator': len(roster),
                'common_covered_count': len(common), 'common_covered_sids': common,
                'common_covered_pnl': sum(stock_index[sid,w,arm]['known_total_pnl'] for sid in common),
                'arm_only_covered_sids': [r['sid'] for r in comparable if r['sid'] not in common],
                'conditional_closed_count': len(closed), 'conditional_closed_pnl': sum(r['known_total_pnl'] for r in closed),
                'financial_closed_count': len(fin_closed), 'financial_closed_pnl': sum(r['known_total_pnl'] for r in fin_closed),
                'unknown_count': sum(r['unknown_liability'] for r in rs),
                'known_zero_never_entered_count': sum(r['never_entered'] for r in rs),
                'excluded': [{'sid': r['sid'], 'reasons': r['coverage_reasons'] + ([] if r['known_total_pnl'] is not None else ['UNKNOWN_TOTAL'])} for r in rs if not r['comparable']],
                'one_price_dependent_count': sum(r['one_price_ohlc_dependency'] for r in rs),
                'one_price_dependent_known_pnl': sum(r['known_total_pnl'] for r in rs if r['one_price_ohlc_dependency'] and r['known_total_pnl'] is not None)})
        for sid in roster:
            base, joint = (stock_index[sid,w,a] for a in arms)
            delta = joint['known_total_pnl']-base['known_total_pnl'] if all(r['known_total_pnl'] is not None for r in (base,joint)) else None
            parts = {}
            for lane in lanes:
                b, j = (lane_index[sid,w,a,lane]['known_total_pnl'] for a in arms)
                parts[lane] = j-b if b is not None and j is not None else None
            if delta is not None and not math.isclose(sum(parts.values()), delta, abs_tol=1e-8):
                raise AssertionError('lane contribution reconciliation failed')
            differences.append({'sid': sid, 'window': w, 'joint_minus_baseline': delta,
                'lane_contributions': parts, 'common_covered': sid in common})
    distributions = []
    for w, arm, lane in product(windows, arms, lanes):
        selected = [r for r in lane_rows if (r['window'], r['arm'], r['lane']) == (w, arm, lane)]
        entered = [r for r in selected if r['entered']]
        known = [r for r in entered if r['known_total_pnl'] is not None]
        values = sorted(r['known_total_pnl'] for r in known)
        def quantile(fraction):
            if not values:
                return None
            point = (len(values)-1)*fraction
            low, high = math.floor(point), math.ceil(point)
            return values[low] + (values[high]-values[low])*(point-low)
        top = sorted(known, key=lambda r: (-r['known_total_pnl'], r['sid']))
        distributions.append({'window': w, 'arm': arm, 'lane': lane,
            'unit': 'entered_stock_window_all_rounds', 'fixed_denominator': len(roster),
            'entered_count': len(entered), 'known_count': len(known),
            'unknown_total_count': len(entered)-len(known),
            'wins': sum(x > 0 for x in values), 'losses': sum(x < 0 for x in values),
            'zeros': sum(x == 0 for x in values), 'known_net': sum(values),
            'known_mean': sum(values)/len(values) if values else None,
            'known_median': quantile(.5), 'known_p90': quantile(.9),
            'known_max': max(values) if values else None,
            'right_tail_top10': [{'sid': r['sid'], 'pnl': r['known_total_pnl']} for r in top[:10]],
            'all_entered_results': [{'sid': r['sid'], 'pnl': r['known_total_pnl'],
                                    'comparable': r['comparable']} for r in entered],
            'fees': sum(r['fees'] for r in selected),
            'one_price_dependent_known_net': sum(r['known_total_pnl'] for r in known if r['one_price_ohlc_dependency']),
            'diagnostic_inputs_missing': [field for field in ('holding_sessions', 'risk_over_budget_gap',
                  'industry_gate_delay_sessions', 'pvr_resource_loss') if any(r[field] is None for r in entered)]})
    permit = None
    if (reference_permits is None) != (candidate_permits is None):
        raise ValueError('both permit collections required')
    if reference_permits is not None:
        permit = exact_permit_audit(reference_permits, candidate_permits)
    return {'protocol_sha256': PROTOCOL_SHA256, 'main_unit': 'stock_x_window',
        'fixed_roster_count': len(roster), 'lane_rows': lane_rows, 'stock_rows': stock_rows,
        'summary': summary, 'differences': differences, 'permit_audit': permit,
        'ab_changes': records(ab_changes), 'lane_distributions': distributions,
        'closed_round_reconciliation': round_reconciliation,
        'core_independent_dated_fee_diagnostics': records(core_diagnostics),
        'pvr_stage_diagnostics': records(pvr_diagnostics),
        'unprovided_diagnostics': ([] if records(core_diagnostics) else ['CORE_INDEPENDENT_DATED_FEES']) +
            ([] if records(pvr_diagnostics) else ['UNKNOWN_PVR_APPLICATION_SLOT_AND_TRUE_RANK_BLOCK']),
        'comparison_release_ready': False,
        'permit_exact_verified': permit is not None and permit['exact'],
        'release_gate_owner': 'caller: full protocol diagnostics and stage authorization still required',
        'limitations': ['Proxy research PnL, not shared-account return or actual tradability.',
            'One-price OHLC flags are posterior dependency diagnostics, not execution evidence.',
            'UNKNOWN is not zero; identifiable components do not establish total PnL.',
            'Claims are recognized at legal ex once; receivables are not added again.']}


def normalize_native_actions(actions, rounds):
    """Normalize frozen PURE_CASH consumer ledger without reading any data.

    sell_all fees are proportional reporting allocations with final remainder;
    never use these allocations as independent dated CORE diagnostic fees.
    Unknown share changes cannot be repaired here and are rejected.
    """
    round_rows = records(rounds)
    round_map = {str(r['round_id']): r for r in round_rows}
    if len(round_map) != len(round_rows):
        raise ValueError('duplicate native round_id')
    inventory = defaultdict(lambda: {'PROBE': 0.0, 'ADD': 0.0})
    normalized = []
    sequence = 0
    for source in records(actions):
        rid = str(source['round_id'])
        if rid not in round_map:
            raise ValueError('action missing owner round metadata')
        rd = round_map[rid]
        if 'owner_lane' not in rd and 'lane' not in rd:
            raise ValueError('round needs explicit owner_lane')
        if number(source.get('quantity_factor', 1), 'quantity_factor') != 1:
            raise ValueError('UNADMITTED share adjustment')
        action = dict(source)
        for n in ('sid', 'window', 'arm'):
            action[n] = source.get(n, rd[n])
        action['lane'] = rd.get('owner_lane', rd.get('lane'))
        action['known_day'] = str(source['day'])[:10]
        action['day'] = str(source['day'])[:10]
        side = str(source['side']).lower()
        q = number(source['q'], 'q')
        fee = number(source['fee'], 'fee')
        inv = inventory[rid]
        if side in {'buy_core', 'buy_probe', 'buy_add'}:
            role = 'ADD' if side == 'buy_add' else 'PROBE'
            allocations = [(role, q, fee, 'BUY')]
        elif side == 'sell_add':
            allocations = [('ADD', q, fee, 'SELL')]
        elif side == 'sell_all':
            total = sum(inv.values())
            if not math.isclose(q, total, abs_tol=1e-8):
                raise ValueError('sell_all qty mismatch; unknown/unadmitted share bridge cannot be guessed')
            allocations, allocated_fee = [], 0.0
            roles = [r for r in ('PROBE', 'ADD') if inv[r] > 0]
            for i, role in enumerate(roles):
                part_fee = fee-allocated_fee if i == len(roles)-1 else fee*inv[role]/total
                allocated_fee += part_fee
                allocations.append((role, inv[role], part_fee, 'SELL'))
        elif side in {'buy', 'sell'} and 'role' in source:
            allocations = [(_role(source), q, fee, side.upper())]
        else:
            raise ValueError(f'unsupported native side: {side}')
        for role, amount, part_fee, normalized_side in allocations:
            sequence += 1
            if normalized_side == 'SELL' and inv[role]+1e-8 < amount:
                raise ValueError('native role oversell')
            inv[role] += amount if normalized_side == 'BUY' else -amount
            normalized.append(dict(action, side=normalized_side, role=role, q=amount,
                                   fee=part_fee, sequence=sequence,
                                   native_fee_allocation='QUANTITY_PROPORTIONAL_REPORT_ONLY' if side=='sell_all' else 'ACTUAL_ROLE_FEE'))
    return normalized


def normalize_native_claims(claims, rounds):
    """Original recognized NET80 claims; settlement only transfers assets.

    Only confirmed recognized claims count as income. Unrecognized claim rows
    remain explicit unknown-equity inputs, not zeros. Original PURE_CASH caller
    contract must already have certified source admissibility.
    """
    round_rows = records(rounds)
    round_map = {str(r['round_id']): r for r in round_rows}
    if len(round_map) != len(round_rows):
        raise ValueError('duplicate native round_id')
    out = []
    for c in records(claims):
        rid = str(c['owner_round_id'])
        if rid not in round_map:
            raise ValueError('claim missing owner round metadata')
        rd = round_map[rid]
        if 'owner_lane' not in rd and 'lane' not in rd:
            raise ValueError('claim round needs owner_lane')
        if number(c.get('split_ratio', 1), 'split_ratio') != 1:
            raise ValueError('UNADMITTED non-cash claim')
        amount = number(c['amount'], 'claim amount')
        recognized = c.get('recognized') is True
        out.append(dict(sid=rd['sid'], window=rd['window'], arm=rd['arm'],
            lane=rd.get('owner_lane', rd.get('lane')), round_id=rid,
            claim_id=json.dumps(c['key'], ensure_ascii=False, default=str),
            amount=amount, legal_ex_confirmed=recognized, tax_scenario='NET80',
            receivable=amount if recognized and c.get('settled') is not True else 0.0,
            source_economic_event_id=c.get('economic_event_id'),
            core_amount=c.get('core_amount')))
    return out
