"""Frozen three-original-entry arithmetic, never an Account or strategy replay."""
from pathlib import Path
from decimal import Decimal as D
import hashlib, json, math
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
EQ = O.parents[1]
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
CHAIN = EQ / 'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json'
SM = W / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
RULES = R / 'pvr-act-comparison-20261027/execution-rules-v2.json'
SLIP, RATIO = D('.0005'), D('.0025')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def version(rows, day):
    out = [r for r in rows if r['from'] <= day and (r.get('to') is None or day < r['to'])]
    assert len(out) == 1
    return out[0]


def fee_fresh(schedule, qty, price, side, par):
    """Original five components, fresh logical order paid/accrued={}, multiplier1."""
    out = {}
    for c in schedule['components']:
        if c.get('side', 'both') not in ['both', side]: continue
        assert c.get('basis', 'order') in ['order', 'fill']
        basis = c.get('amount_basis', 'notional')
        amount = D(qty)*price if basis == 'notional' else D(qty) if basis == 'shares' else D(qty)*D(par)
        value = max(D(c.get('minimum_local', '0')), amount*D(c['rate']))
        if c.get('maximum_local') is not None: value = min(value, D(c['maximum_local']))
        assert c.get('rounding_unit') is None, 'No rounding extension invented'
        out[c['name']] = value
    return out


def legal_floor(n, rule):
    minimum, step = rule['buy_minimum'], rule['buy_step']
    return 0 if n < minimum else minimum + (n-minimum)//step*step


def main():
    chains = json.loads(CHAIN.read_text())
    c = next(x for x in chains if x['campaign']['sid'] == '002583.SZ')
    assert c['campaign']['layer_ids'] == [1994, 2017, 2039]
    rec = next(r for r in json.loads(SM.read_text()) if r['symbol'] == '002583.SZ')
    paths = {k: Path(rec['refs'][k]) for k in ['facts', 'CP1_input', 'CP1']}
    for p in paths.values(): assert sha(p) == rec['output_sha256'][str(p)]
    facts, inp, cp = (pd.read_parquet(paths[k]) for k in ['facts', 'CP1_input', 'CP1'])
    # Reused runtime facts/CP can extend beyond this manifest's CP1_input horizon.
    # Compare only the shared immutable prefix, just as the native input loader.
    common_facts = facts.loc[:inp.index.max()]
    assert common_facts.index.as_unit('ns').equals(inp.index.as_unit('ns'))
    assert np.array_equal(common_facts.close, inp.close)
    assert np.array_equal(common_facts.segment_id, inp.segment_id)
    rules = json.loads(RULES.read_text())
    rows = []
    for e in c['entries']:
        a, original = e['original_signal_and_authorization'], e['actual_buy']
        intent, sid = a['frozen_intent'], '002583.SZ'
        day, open_day = a['signal_day'], original['at'][:10]
        at = facts.index.get_loc(pd.Timestamp(day))
        prior = facts.iloc[at-64:at]
        assert len(prior) == 64 and prior.index[-1] < pd.Timestamp(day)
        assert prior.segment_id.eq(facts.loc[day, 'segment_id']).all()
        assert np.isfinite(prior.close).all() and prior.close.gt(0).all()
        returns = np.diff(np.log(prior.close.to_numpy(float)))
        s63 = float(1.4826 * np.median(np.abs(returns)))
        assert s63 == float(cp.loc[day, 's']), 'Existing current CP.s cross-check, not z/frozen used scale'
        factor_signal, factor_open = D(str(a['signal_factor'])), D(str(a['fill_factor']))
        assert factor_signal == factor_open, 'No unexplained share action/unit change accepted'
        h = D(intent['floor']) / factor_signal
        stress_h = h * D(str(math.exp(-2*s63)))
        h_open = D(intent['floor']) / factor_open
        stress_h_open = h_open * D(str(math.exp(-2*s63)))
        nav = D(a['decision_NAV']); budget = RATIO * nav
        raw_c, raw_o = D(a['signal_close_raw']), D(original['raw_open'])
        p_close, p_open = raw_c*(1+SLIP), raw_o*(1+SLIP)
        assert p_open == D(original['price']) and raw_o > h_open
        vr_c = version(rules['venue_versions'][sid], day)
        vr_o = version(rules['venue_versions'][sid], open_day)
        assert vr_c['venue'] == vr_o['venue'] == 'SZSE_MAIN'
        sc = version(rules['fee_versions'][vr_c['venue']], day)['schedule']
        so = version(rules['fee_versions'][vr_o['venue']], open_day)['schedule']
        qc = version(rules['quantity_versions'][sid], day)['rule']
        qo = version(rules['quantity_versions'][sid], open_day)['rule']
        par = rules['security_metadata'][sid]['par_value']

        def risk(q, p, stressed_floor, schedule):
            sale_price = stressed_floor*(1-SLIP)
            bf = fee_fresh(schedule, q, p, 'buy', par) if q else {}
            sf = fee_fresh(schedule, q, sale_price, 'sell', par) if q else {}
            return D(q)*(p-sale_price)+sum(bf.values(), D(0))+sum(sf.values(), D(0))

        def best(p, hs, schedule, rule, cap=None):
            gap = p-hs*(1-SLIP)
            assert gap > 0
            upper = int(budget/gap)
            if cap is not None: upper = min(upper, cap)
            for q in range(legal_floor(upper, rule), rule['buy_minimum']-1, -rule['buy_step']):
                if risk(q, p, hs, schedule) <= budget: return q
            return 0

        obs = next(o for o in c['observations'] if o['day'] == day)
        qty_before = sum(x['snapshot']['qty'] for x in obs['actual_live_layers'])
        assert qty_before == a['quantity_before_actual_buy']
        assert obs['account_NAV'] == a['decision_NAV'] and not obs['original_pending_sells']
        remaining_signal = max(D(0), D('.10')*nav-D(qty_before)*raw_c)
        stock_signal_cap = legal_floor(int(remaining_signal/p_close), qc)
        risk_only_close = best(p_close, stress_h, sc, qc)
        frozen_new_cap = min(risk_only_close, stock_signal_cap)
        # Each original prefix is independent; no candidate fills are carried forward.
        remaining_open = max(D(0), D('.10')*nav-D(qty_before)*raw_o)
        stock_open_cap = legal_floor(int(remaining_open/p_open), qo)
        risk_only_open = best(p_open, stress_h_open, so, qo)
        open_candidate_cap = best(p_open, stress_h_open, so, qo, min(frozen_new_cap, stock_open_cap))
        actual_fee = fee_fresh(so, original['shares'], p_open, 'buy', par)
        assert sum(actual_fee.values(), D(0)) == D(original['fees_cny'])
        next_q_close = risk_only_close + qc['buy_step']
        next_q_open = risk_only_open + qo['buy_step']
        assert risk(risk_only_close, p_close, stress_h, sc) <= budget < risk(next_q_close, p_close, stress_h, sc)
        assert risk(risk_only_open, p_open, stress_h_open, so) <= budget < risk(next_q_open, p_open, stress_h_open, so)
        row = {
            'layer': e['layer'], 'original_kind': original['kind'], 'original_role': a['role'],
            'signal_day': day, 'actual_OPEN_day': open_day, 'original_qty': original['shares'],
            'original_intent': intent, 'original_actual_buy': original,
            'original_net_context_only': a['net'],
            'signal_NAV_frozen': nav, 'budget_0_0025_signalNAV': budget,
            'raw_signal_CLOSE': raw_c, 'raw_actual_OPEN': raw_o, 'p_ref_CLOSE': p_close, 'p_OPEN': p_open,
            'original_adjusted_floor': intent['floor'], 'signal_factor': factor_signal, 'OPEN_factor': factor_open,
            'raw_h': h, 's63': s63, 'two_s63_exp_multiplier': math.exp(-2*s63),
            'raw_stress_floor': stress_h, 'stress_sell_reference_price': stress_h*(1-SLIP),
            's63_window': {'prior_close_count': 64, 'prior_return_count': 63, 'first_close_day': str(prior.index[0].date()),
                           'first_return_end_day': str(prior.index[1].date()), 'last_return_end_day': str(prior.index[-1].date()),
                           'signal_return_excluded': True, 'source_segment': int(facts.loc[day, 'segment_id']),
                           'history': [{'day': str(t.date()), 'adjusted_close': float(v)} for t, v in prior.close.items()],
                           'exact_existing_CP_current_s': float(cp.loc[day, 's']), 'not_CP_z_or_receipt_used_scale': True},
            'dated_quantity_signal': qc, 'dated_quantity_OPEN': qo,
            'dated_fee_signal': sc, 'dated_fee_OPEN': so, 'par_value': par,
            'actual_buy_fee_components_crosscheck': actual_fee,
            'risk_only_CLOSE_cap': risk_only_close,
            'R_risk_only_CLOSE_cap': risk(risk_only_close, p_close, stress_h, sc),
            'R_next_CLOSE_legal_q': risk(next_q_close, p_close, stress_h, sc),
            'original_prefix_quantity_before_signal': qty_before,
            'stock10_remaining_gross_at_signal': remaining_signal, 'stock10_signal_quantity_cap': stock_signal_cap,
            'new_frozen_signal_cap': frozen_new_cap,
            'risk_only_OPEN_cap_without_signal_freeze': risk_only_open,
            'stock10_remaining_gross_at_OPEN': remaining_open, 'stock10_OPEN_quantity_cap': stock_open_cap,
            'OPEN_cap_with_new_signal_freeze_and_stock10': open_candidate_cap,
            'R_OPEN_candidate': risk(open_candidate_cap, p_open, stress_h_open, so),
            'R_next_OPEN_legal_q_unfrozen': risk(next_q_open, p_open, stress_h_open, so),
            'candidate_OPEN_gross': D(open_candidate_cap)*p_open,
            'candidate_OPEN_buy_fee': sum(fee_fresh(so, open_candidate_cap, p_open, 'buy', par).values(), D(0)),
            'candidate_OPEN_sell_reference_fee': sum(fee_fresh(so, open_candidate_cap, stress_h_open*(1-SLIP), 'sell', par).values(), D(0)),
            'R_original_qty_at_CLOSE_reference': risk(original['shares'], p_close, stress_h, sc),
            'R_original_qty_at_actual_OPEN': risk(original['shares'], p_open, stress_h_open, so),
            'old_source_cap_comparison_only': intent['cap'], 'old_source_gross_budget_comparison_only': intent['budget'],
            'old_mobile_2pct_not_applied_to_candidate': True,
            'sector_pool_cash_final_grant': 'NOT_CHECKED_NO_FINAL_GRANT',
            'scope': 'Independent original prefix paper quantity only. New first-leg quantity is not carried into later observations.'}
        rows.append(row)
        print(json.dumps({k: row[k] for k in ['layer', 'risk_only_CLOSE_cap', 'new_frozen_signal_cap', 'OPEN_cap_with_new_signal_freeze_and_stock10', 'original_qty']}, default=str))
    sources = {str(CHAIN): sha(CHAIN), str(SM): sha(SM), str(RULES): sha(RULES),
               **{str(p): sha(p) for p in paths.values()}, str(Path(__file__)): sha(Path(__file__))}
    out = {'status': 'THREE_FIXED_HAINENGDA_ORIGINAL_ENTRY_PAPER_ARITHMETIC_NO_FINAL_GRANT',
           'campaign': c['campaign'], 'formula_frozen': 's63=1.4826 median(abs prior63 logreturns); stressfloor=h*exp(-2*s63); R=q*(p-stressfloor*(1-.0005))+buyfee+sellfee <= .0025*signalNAV',
           'rows': rows, 'source_sha256': sources, 'new_accounts': 0, 'new_strategy_paths': 0,
           'parameter_search': False, 'original_financial_data_modified': False}
    (O/'THREE_ENTRY_PAPER_RESULTS.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str)+'\n')


if __name__ == '__main__': main()
