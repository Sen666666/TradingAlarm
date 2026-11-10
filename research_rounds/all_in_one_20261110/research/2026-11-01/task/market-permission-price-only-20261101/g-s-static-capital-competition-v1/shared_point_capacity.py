"""Pure static common decision-point resource arithmetic. No account objects.

Only the same-close A-only funding lock is endogenous to A. Keep its inventory
and all cash; remove its extra lock charge from this comparison ledger of
constraints, retaining every independent/prior duty. This is not an account
rollback, cancellation, sale, or target solver.
"""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import analyze_static as A
O=Path(__file__).resolve().parent;N=A.N;Z=D(0)
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 result={};sources={}
 for key,day in [('2022','2022-01-06'),('2025_26','2025-07-03')]:
  p=N/'run'/key/'close'/f'{day}-CLOSE.json';cl=read(p);a=cl['account'];sources[str(p)]=sha(p)
  rp=N/'inputs'/key/'rules.json';rules=read(rp);sources[str(rp)]=sha(rp)
  cp=O/(key+'-COMPETITION.json');comp=read(cp);sources[str(cp)]=sha(cp)
  actual=A.resource_rows(a);shared=[];omitted=[]
  for r in actual:
   locks=[]
   for e in a['policy']['locks'].values():
    if e['lot']!=r['layer'] or not e['remaining']:continue
    duty=a['exit_duties'][e['eid']]
    endogenous=e['reason']=='actionable_S_funding' and duty['requested_at'][:10]==day and set(duty['reasons'])=={'actionable_S_funding'}
    if endogenous:omitted.append(dict(eid=e['eid'],sid=e['sid'],layer=e['lot'],remaining=e['remaining']))
    else:locks.append(e)
   qty=sum(e['remaining'] for e in locks);risk=D(r['qty']-qty)*max(Z,r['raw_mark']-r['raw_floor'])
   for e in locks:risk+=max(D(e['remaining'])*max(Z,r['raw_mark']-r['raw_floor']),D(e['e0'])*D(e['remaining'])/(D(e['ratio'])*D(e['q0'])))
   shared.append(dict(r,risk=risk))
  assert sum(r['capital'] for r in shared)==sum(r['capital'] for r in actual)
  used=[];individual=0
  for x in comp:
   if not x['fresh_mobile']:continue
   c=dict(x['candidate'])
   for k in ['close_buy_proxy','fresh_raw_floor','minimum_fee','minimum_notional','sector_cap_fraction']:
    if k in c:c[k]=D(c[k])
   once=A.minimum_check(c,shared,a,rules)
   if once['fit']:individual+=1
   check=A.minimum_check(c,shared,a,rules,used)
   if check['fit']:used.append(dict(sid=c['sid'],sector=c['sector'],gross=check['gross'],fee=check['fee'],risk=check['risk']))
  result[key]=dict(common_point='after original stock/F1 close processing, before same-close A-only funding request; unchanged inventory/cash/core',
   actual_recorded_resource_risk=sum(r['risk'] for r in actual),common_point_resource_risk=sum(r['risk'] for r in shared),
   omitted_endogenous_lock_charge_only=omitted,no_inventory_removed=True,no_cash_or_sale_credit_added=True,independent_and_prior_duties_retained=True,
   standalone_minimum_fits=individual,rank_order_joint_minimum_unit_witness_count=len(used),minimum_unit_witness=used,
   no_joint_optimal_target_claim=True,next_open_execution_unknown=True)
 (O/'SHARED_PRE_ALLOCATION_STATIC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
 (O/'SHARED_POINT_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False,indent=2,default=str)[:2800])

if __name__=='__main__':main()
