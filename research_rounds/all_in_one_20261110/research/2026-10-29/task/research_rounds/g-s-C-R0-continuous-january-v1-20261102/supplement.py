"""Whole-account role/receipt effects and R0 conservation; saved states only."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D
from collections import defaultdict,Counter
import json
import jan_r0 as X
P=X.HERE;O=P/'analysis';Z=D(0)
def read(p):return X.read(p)
def save(n,x):X.save(O/n,x)
def main():
 rows=read(O/'RESULTS.json');ll=read(O/'ALL_LAYERS.json');oldll=read(P/'baseline_readonly/ALL_LAYERS.json');names=read(X.M.HERE/'inputs/2022/metadata.json');out={};riskout={}
 for mode in [z['mode'] for z in rows]:
  root=P/'runs'/mode;pr=read(root/'PROGRESS.json');x=read(Path(pr['checkpoint']).with_suffix('.json'));risk=x['approved_risk'];aa=[]
  for key,z in risk['approvals'].items():
   p=z['approved'];fs=[v for v in risk['fills'].values() if v['key']==key];q=sum((F(v['anchor_q']) for v in fs),F(0));spent=sum((F(v['consumed']) for v in fs),F(0));R0=F(p['R0']);assert spent==F(z['spent']) and spent<=R0 and F(z['remaining'])+q<=F(p['Q0'])
   aa.append(dict(key=key,sid=p['sid'],name=names[p['sid']]['name'],canonical_receipt=p['receipt'],known_at=p['known_at'],deadline=p['deadline'],Q0=p['Q0'],approved_price=p['p0'],approved_effective_raw_floor=p['f0'],R0=str(R0),actual_C_fill_anchor_quantity=str(q),actual_C_consumed_risk=str(spent),remaining_anchor_authority=z['remaining'],permanently_shrunk_or_terminal_unfilled=str(F(p['Q0'])-q-F(z['remaining'])),order=z['order'],attempted=z['attempted'],closed=z['closed'],fills=fs,standalone_Q0_risk_at_actual_fill_ratios=[str(F(p['Q0'])*max(F(0),F(v['price'])-F(v['floor']))/R0) for v in fs]))
  riskout[mode]=dict(positive_stock_authorizations=len(aa),distinct_certificates=len({z['approved']['cid'] for z in risk['approvals'].values()}),actual_C_filled_stock_authorizations=sum(F(z['actual_C_fill_anchor_quantity'])>0 for z in aa),C_native_fill_receipts=len(risk['fills']),all_R0_spend_and_quantity_bridges=True,rows=aa,not_direct_incremental_PNL=True,smaller_actual_quantity_may_also_include_original_resource_and_execution_limits=True)
  def key(z):return (z['sid'],z['signal_at'],z['role'],z['pool'])
  old={key(z):z for z in oldll[mode]};new={key(z):z for z in ll[mode]};assert len(old)==len(oldll[mode]) and len(new)==len(ll[mode]),'ambiguous layer comparison key; do not silently pair'
  matched=[];newonly=[];lost=[]
  for k in new.keys()|old.keys():
   a=new.get(k);b=old.get(k)
   v=dict(sid=k[0],name=names[k[0]]['name'],signal_at=k[1],role=k[2],pool=k[3],old_layer=b,new_layer=a)
   if a and b:matched.append(v)
   elif a:newonly.append(v)
   else:lost.append(v)
  def totals(zs,side):
   zz=[z[side] for z in zs];return dict(layers=len(zz),stocks=len({z['sid'] for z in zz}),buy_gross=sum((D(z['buy_gross']) for z in zz),Z),realized=sum((D(z['realized_trade_PNL']) for z in zz),Z),unrealized=sum((D(z['unrealized_net_buy_cost']) for z in zz),Z),dividend=sum((D(z['booked_dividend_income']) for z in zz),Z),contribution=sum((D(z['total_contribution']) for z in zz),Z))
  out[mode]=dict(pair_key='sid+signal_at+role+pool, actual fill layers; does not infer same receipt if roles differ',matched_count=len(matched),matched=matched,new_actual_layers=newonly,lost_old_actual_layers=lost,new_actual_layer_totals=totals(newonly,'new_layer'),lost_old_actual_layer_totals=totals(lost,'old_layer'),new_roles=Counter(z['role'] for z in ll[mode]),old_roles=Counter(z['role'] for z in oldll[mode]),whole_account_state_feedback_not_local_trade_deletion=True)
 save('AUTHORIZATION_RISK_BRIDGES.json',riskout);save('FUNDED_LAYER_CHANGES.json',out)
 print('SUPPLEMENT_PASS',[(m,riskout[m]['positive_stock_authorizations'],len(out[m]['new_actual_layers']),len(out[m]['lost_old_actual_layers'])) for m in out])
if __name__=='__main__':main()
