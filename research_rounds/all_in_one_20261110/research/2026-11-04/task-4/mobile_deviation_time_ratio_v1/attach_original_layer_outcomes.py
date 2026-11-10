"""Attach saved closed-layer outcomes after R was frozen; no financial replay."""
from pathlib import Path
import json,csv,hashlib
O=Path(__file__).resolve().parent
rs=json.loads((O/'all59.json').read_text());lr=json.loads((O/'layer_review/ALL_19_ORIGINAL_MOBILE_LAYERS.json').read_text())
if isinstance(lr,dict):lr=lr['rows']
by={(r['sid'],r['signal_day']):r for r in lr};assert len(by)==19
out=[];independent=[]
for src in rs:
 r=dict(src);s=by.get((r['sid'],r['date']));filled=int(r['original_mobile_filled_shares']or 0)
 assert bool(s)==bool(filled),(r['sid'],r['date'],'layer mapping')
 if s:
  assert int(s['original_actual_buy_qty'])==filled
  independent.append(abs(r['deviation_time_ratio']-float(s['R_price_observations'])))
  for k in ['original_layer_id','original_opened','original_closed','original_buy_cash_cost','original_closed_lifecycle_net','original_lifecycle_net_per_buy_cost_pct','net_sign']:
   r['evaluation_'+k]=s[k]
 else:
  for k in ['original_layer_id','original_opened','original_closed','original_buy_cash_cost','original_closed_lifecycle_net','original_lifecycle_net_per_buy_cost_pct']:
   r['evaluation_'+k]=None
  r['evaluation_net_sign']='NO_ORIGINAL_MOBILE_FILL_NO_COUNTERFACTUAL_LABEL'
 r['evaluation_outcome_used_in_R_or_signal_identity']=False;out.append(r)
with (O/'all59_with_original_outcomes.csv').open('w',newline='')as h:
 w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
(O/'all59_with_original_outcomes.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
pos=[r for r in out if r['evaluation_net_sign']=='positive'];neg=[r for r in out if r['evaluation_net_sign']=='negative']
summ={'original_filled_layers':len(pos)+len(neg),'positive_net_layers':len(pos),'negative_net_layers':len(neg),'positive_R_min_max':[min(r['deviation_time_ratio']for r in pos),max(r['deviation_time_ratio']for r in pos)],'negative_R_min_max':[min(r['deviation_time_ratio']for r in neg),max(r['deviation_time_ratio']for r in neg)],'independent_scalar_R_max_abs_difference':max(independent),'parent_denominator_diagnostic':'RATIO_SCOPE_AND_DENOMINATORS.json; no return-label threshold fitted','decision':'Reject this ratio as a standalone global monotone discriminator/risk-priority direction for preserving all original positives while removing failed reentries in this diagnostic set. No piecewise/stock-specific rescue or account test.','limit':'This interleaving is not a proof of zero predictive information under every possible future conditional model. No such model is proposed or tested.','unfilled_outcomes':'Missing, never zero or imaginary returns','original_fills':'Daily-bar-proxy ledger, lifecycle net with original modeled fees/dividends, not broker or calendar-year/account returns','source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [O/'all59.json',O/'layer_review/ALL_19_ORIGINAL_MOBILE_LAYERS.json']}}
(O/'OVERLAP_DIAGNOSTIC.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summ,ensure_ascii=False))
for r in out:
 if int(r['original_mobile_filled_shares']or 0):print(r['name'],r['date'],round(r['deviation_time_ratio'],6),r['evaluation_original_layer_id'],r['evaluation_original_closed_lifecycle_net'])
