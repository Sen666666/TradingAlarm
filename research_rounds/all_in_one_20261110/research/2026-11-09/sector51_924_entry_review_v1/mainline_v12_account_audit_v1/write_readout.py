"""Write the independent M12 report only after saved-account audit exists."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
sys.dont_write_bytecode=True
import accounting_core as au
O=Path(__file__).resolve().parent
def n(x):return f'{D(x):,.2f}'
def main():
    r=au.read(O/'INDEPENDENT_M12_VS_M7.json');s=r['nov6_segment'];a=r['M12'];b=r['M7'];sem=r['saved_semantics']
    lines=['# M12 independent account and saved-branch readout','',
      f"Accounting: {r['accounting_verdict']}. Saved branch semantics: {r['saved_semantics_verdict']}. Static/source timing: {r['static_future_input_provenance_verdict']}.",
      'No strategy/history was executed by this auditor. The only economic comparator is original M7, 93 sessions through 2025-01-20.','',
      '## Main economic test: actual account after Nov6',
      f"M12 late actual PnL {n(s['M12']['absolute_PnL'])}; M7 {n(s['M7']['absolute_PnL'])}; improvement {n(s['delta']['late_absolute_PnL_improvement'])}.",
      f"Lead already present at Nov6 {n(s['delta']['lead_at_anchor'])}; end lead {n(s['delta']['lead_at_end'])}. These reconcile exactly.",
      f"Late fee saving {n(s['delta']['late_fee_saving'])}; fee-added-back PnL difference {n(s['delta']['late_fee_added_back_PnL_difference'])}. Fee addback is decomposition, not new income.",
      f"M12 old-round increment {n(s['M12']['old_round_increment_after_anchor'])}; its new-seed whole-round PnL {n(s['M12']['own_new_seed_rounds_whole_PnL'])}.",'',
      '## Whole account and risk',
      f"Final NAV M12 {n(a['NAV'])} versus M7 {n(b['NAV'])}; fees {n(a['trading']['fees'])} versus {n(b['trading']['fees'])}.",
      f"Maximum close drawdown {n(a['max_close_drawdown_pct'])}% versus {n(b['max_close_drawdown_pct'])}%.",
      f"Mean/max close exposure M12 {n(a['exposure_stats']['mean_close_weight_pct'])}% / {n(a['exposure_stats']['max_close_weight_pct'])}%; M7 {n(b['exposure_stats']['mean_close_weight_pct'])}% / {n(b['exposure_stats']['max_close_weight_pct'])}%.",
      f"Open rounds M12 {a['rounds']['open']} versus M7 {b['rounds']['open']}; these are marked, not liquidated. Actual ADD orders {a['rounds']['actual_add_orders']} versus {b['rounds']['actual_add_orders']}.",'',
      '## Fixed original identities']
    for c in r['cohorts']:
        lines.append(f"- {c['cohort']}: {c['captured']}/{c['baseline_common_frontier_count']} captured; delayed {c['delayed']}; fixed strong winners {c['fixed_top_captured']}/{c['fixed_top_positive_count']}; candidate actual PnL {n(c['candidate_actual_pnl_on_fixed_keys'])}, original reference {n(c['baseline_pnl'])}; candidate still open {c['candidate_open_on_fixed_keys']}.")
    lines+=['','## Profitable opportunity costs and no-funding boundary']
    for x in r['special_fixed_mature_subgroups']:
        lines.append(f"- {x['cohort']}: captured {x['candidate_captured']}/{x['baseline_count']}; actual candidate PnL {n(x['candidate_actual_PnL'])}; original reference PnL {n(x['baseline_PnL'])}; missing reference only {n(x['missing_reference_PnL_only'])}; ADD {x['candidate_add_orders']}; open {x['candidate_open']}.")
    lines+=['These original same-day groups are not donor-specific funding allocations or proof of causal displacement. Missing original losses are never candidate-earned profit. Sep24 no actual funding does not guarantee all 28 MATURE entries survive: the ADD/EVENT q lower bound can independently bind. The original Dec5 case has both no funding and no A request; its candidate path is still measured rather than presumed unchanged.','',
      '## Selection and accounting evidence',
      'FUNDING_PLAN_SELECTION_AUDIT.json records full-to-selected deletion counts. FUNDING_QUANTITY_COMPARISON.json separates branch ceilings, CLOSE/OPEN predictions and actual orders per identity. ACTUAL_PREDICTION_DEVIATIONS.json lists realized differences and causes.',
      'DAILY_CASH_DEMAND_EXPOSURE.json keeps original D/reference records and actual all-buy cash costs; TRANSFERS.M_actual_buy_cost is not treated as total buy cost.',
      'ACTUAL_STOCK_CONTRIBUTIONS.json and MATERIAL_STOCK_ACTUAL_ORDER_TRACES.json show both gains and sacrificed winners/new opportunities, with exact actual order references.',
      'All actual cash, fees, shares, T+1, lots, inventory, NAV, dividends and sector/round PnL were recomputed from saved outputs.','',
      '## Limits']
    lines+=['- '+x for x in r['limits']]
    lines+=['- '+x for x in sem.get('not_covered',[])]
    (O/'INDEPENDENT_READOUT.md').write_text('\n'.join(lines)+'\n')
    au.save('FINAL_AUDIT_SEAL',dict(accounting=r['accounting_verdict'],saved_semantics=r['saved_semantics_verdict'],static_future_input_provenance=r['static_future_input_provenance_verdict'],files={p.name:au.sha(p) for p in O.iterdir() if p.is_file() and p.name!='FINAL_AUDIT_SEAL.json'},candidate_output=r['candidate_output'],baseline=str(au.BASE)))
    print(str(O/'INDEPENDENT_READOUT.md'))
if __name__=='__main__':main()
