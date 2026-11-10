"""Presentation and bookkeeping validation of the six computed cases only."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
from analyze import O,R,JAN,COVER,read,save,sha

def main():
 rows=read(O/'ALL_ROWS.json');summaries=read(O/'SUMMARY.json');batches=read(COVER/'BATCHES.json')
 janlayers=read(JAN/'ALL_LAYERS.json')['C10'];janby={r['layer']:r for r in janlayers}
 all_layers={a:{r['layer']:r for r in read(R/'g-s-C-August-continuation-v1-20261102/analysis'/(a+'-LAYERS.json'))} for a in ['C10','C20']}
 out=[];details=[];checks=[]
 for s in summaries:
  rr=[r for r in rows if r['case']==s['certificate']];old=[r for r in rr if r['side']=='D' and r['actual_filled']];new=[r for r in rr if r['side']=='Q' and r['actual_filled']]
  actual_old=sum(D(o['realized_trade_PNL']) for r in old for o in r['actual_account_outcomes'])
  incoming={};legs=[]
  for r in new:
   for u in r['actual_units']:
    lid=u['layer'];z=(janby[lid] if s['arm']=='2022-C10' else all_layers[s['arm']][lid]);incoming[lid]=z
    for leg in z.get('actual_sell_parts',z.get('sell_legs',[])):
     legs.append(dict(sid=r['sid'],name=r['signal']['name'],layer=lid,at=leg['at'],shares=leg['shares'],reason=leg['reason'],realized=leg.get('realized_trade_PNL')))
  if s['arm']=='2022-C10':
   realized=sum(D(z['realized_net']) for z in incoming.values());unrealized=sum(D(z['unrealized_net']) for z in incoming.values());div=D(0);net=sum(D(z['net']) for z in incoming.values())
  else:
   outcomes=[o for r in new for o in r['actual_account_outcomes']]
   realized=sum(D(z['realized_trade_PNL']) for z in outcomes);unrealized=sum(D(z['unrealized_net_buy_cost']) for z in outcomes);div=sum(D(z['booked_dividend_income']) for z in outcomes);net=sum(D(z['total_contribution']) for z in outcomes)
  assert realized+unrealized+div==net
  metrics={}
  for side,rs in [('D',old),('Q',new)]:
   w=sum(r['actual_gross'] for r in rs)
   metrics[side]=dict(actual_gross=w,native_risk=sum(float(r['fixed_native_risk']) for r in rs),
    PVR_amount_weighted=sum(r['actual_gross']*r['signal']['PVR'] for r in rs)/w,
    stock_H1_amount_weighted=sum(r['actual_gross']*r['signal']['stock_H1'] for r in rs)/w,
    I_valid=sum(r['signal']['I_target']==1 for r in rs),G1_grade_counts={str(g):sum(r['signal']['G1_grade']==g for r in rs) for g in sorted({r['signal']['G1_grade'] for r in rs})},
    CP1_market_fresh=sum(bool(r['signal']['CP1_market_receipt']) for r in rs),stocks=len(rs))
  flips=[dict(old=a['sid'],new=b['sid']) for a in old for b in new if a['signal']['original_key']<b['signal']['original_key'] and a['signal']['C_key']>b['signal']['C_key']]
  chain=[dict(certificate=b['certificate'],plan=b['original_plan_at'],actual_receivers=[dict(sid=f['security_id'],shares=f['shares']) for f in b['same_certificate_C_buys']]) for b in batches if b['cell']==s['arm'] and any(p['layer'] in incoming for p in b['source_sell_parts'])]
  out.append(dict(summary=s,asof_basket=metrics,industry_priority_inversions=flips,inversion_pair_denominator=len(old)*len(new),inversions_are_dependent_comparisons_not_samples=True,
   actual_bookkeeping=dict(old_realized_at_funding=str(actual_old),new_realized=str(realized),new_unrealized=str(unrealized),new_booked_dividend=str(div),new_total=str(net),
    actual_cutoff='2022-01-28' if s['arm']=='2022-C10' else '2025-08-29',not_comparable_to_fixed_horizon_PNL=True),actual_new_layer_exit_legs=legs,later_actual_funding_targets=chain))
  details.append('\n'+s['arm']+' '+s['signal_close'][:10]+' CLOSE → '+s['start']+' OPEN\n')
  details.append('side sid name approved/actual | industryH1rank | PVR / stockH1 / G1 | fresh | original→C key | 5d/21d price% | fixed risk / 21d price-change-per-R\n')
  for r in rr:
   f=r['signal'];lr=r['labels']['21'].get('price_change_per_fixed_nominal_risk')
   details.append(f"{r['side']} {r['sid']} {f['name']} {r['approved_qty']}/{r['actual_qty']} | {f['sector_name']} #{f['sector_H1_rank90']}/{f['sector_rank_denominator']} | {f['PVR']:.4f}/{f['stock_H1']:.4f}/{f['G1_grade']} | {f['CP1_market_receipt']} | {f['original_key']}→{f['C_key']} | {r['labels']['5']['return_pct']:.4f}/{r['labels']['21']['return_pct']:.4f} | {r['fixed_native_risk']} / {None if lr is None else round(lr,4)}\n")
   if r['actual_filled']:
    for u in r['actual_units']:
     assert D(u['floor_raw'])>0
     if r['side']=='Q':assert float(u['floor_raw'])<r['labels']['21']['anchor_raw_open'],'future ratchet masquerading as entry floor'
   p0=r['labels']['21']['anchor_raw_open'];expected=r['actual_qty']*p0*(1+(.0005 if r['side']=='Q' else -.0005))
   assert abs(expected-r['actual_gross'])<1e-6,(r['sid'],'raw opening / actual frozen execution proxy mismatch')
   checks.append(dict(case=r['case'],side=r['side'],sid=r['sid'],actual_open_proxy_bridge=True,zero=r['zero_risk'],near_zero=r['near_zero_per_share_one_fen'],unknown=r['risk_unknown']))
 save(O/'READOUT.json',out);(O/'ALL_65_ROWS.txt').write_text(''.join(details))
 invalid=[dict(case=r['case'],sid=r['sid'],h=h,missing=z.get('missing_market_sessions')) for r in rows for h,z in r['labels'].items() if not z.get('valid') or z.get('missing_market_sessions')]
 assert not invalid
 # Original price labels are invariant to the corrected floor/Jan-part mapping.
 first=read(O/'archive-initial-analysis/ALL_ROWS.json');idx={(r['case'],r['side'],r['sid']):r for r in first}
 labels_unchanged=all(abs(r['labels'][h]['return_pct']-idx[r['case'],r['side'],r['sid']]['labels'][h]['return_pct'])<1e-10 for r in rows for h in ['5','21'])
 assert labels_unchanged
 save(O/'VALIDATION.json',dict(financial_events=0,actual_rows=sum(r['actual_filled'] for r in rows),all_rows=len(rows),fixed_price_labels=2*len(rows),fixed_endpoint_labels_valid=not invalid,
  original_open_actual_proxy_bridges=checks,actual_new_contribution_bridges=True,entry_floors_prior_known_not_terminal_ratchets=True,price_return_labels_unchanged_after_errata=labels_unchanged,
  zero_risk_count=sum(r['zero_risk'] for r in rows),near_zero_count=sum(r['near_zero_per_share_one_fen'] for r in rows),unknown_actual_risk_count=sum(r['risk_unknown'] and r['actual_filled'] for r in rows),
  actual_denominator_min_yuan_per_share=min(float(r['fixed_native_risk'])/r['actual_qty'] for r in rows if r['actual_filled']),
  no_R_ratio_aggregate=True,source_files_sha256={str(JAN/'ALL_LAYERS.json'):sha(JAN/'ALL_LAYERS.json')}))
 for z in out:
  s=z['summary'];print(s['arm'],s['signal_close'][:10],z['actual_bookkeeping'],flush=True)
if __name__=='__main__':main()
