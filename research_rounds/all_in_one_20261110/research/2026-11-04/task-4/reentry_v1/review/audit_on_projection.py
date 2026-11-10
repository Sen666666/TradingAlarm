from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,localcontext
import json,hashlib,copy
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1/funding_agent/private_projection');F=O.parent;R=F.parent/'review';D=Decimal
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s0={k[:10]:v['state'] for k,v in read(F/'PREOPEN_EXACT_STATE.json').items()};completion=read(O/'ON_COMPLETION.json');identity=read(O/'OFF_IDENTITY.json')
assert completion['passed'] and completion['OFF_ON_compute_seconds']<180 and completion['OPENs']==13
assert not (O/'INVALID_PLAN.json').exists() and not (O/'ON_FAILURE.json').exists()
for p,h in read(O/'ON_SOURCE_SHA256.json').items():assert sha(p)==h
# The evaluated route and fixed-pool predicates retain all No60 original guards.
orig=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py').read_text()
old="    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')";new="    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')";route=orig.replace(old,new)
assert (O/'no60_full_target_evaluation.py').read_text()==route[:route.index('  bid=')]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
source=(O/'confirmed_min_first_plan.py').read_text()
for token in ["q=x['minq'] if result['pool']=='confirmed' else result['quantity']","if old['pool']!='confirmed':continue","candidate=order_record(i,q,'confirmed',x,fee)","result,why=EVAL_ROUTE(runner,a,i,x,at)","migration_signature"]:
 if token!='migration_signature':assert token in source
assert "migration_signature(b.migrations)!=migration_signature(expected_migrations)" in (O/'fixed_combination_validation.py').read_text()
assert "core_epoch_locked=i['role']=='core' and a.core_epoch.get(i['sid'])==i['epoch']" in (O/'retained_fixed_reservation.py').read_text()
def resources(s,pool=None,sector=None):
 ls=[z for z in s['lots'] if (pool is None or z['pool']==pool) and (sector is None or z['sector']==sector)]
 os=[z for z in s['orders'].values() if z['qty']>0 and z['status'] in ['open','cancel_pending'] and (pool is None or z['pool']==pool) and (sector is None or z['sector']==sector)]
 return (sum(z['qty']*s['prices'][z['stock']] for z in ls)+sum(z['qty']*z['limit'] for z in os),sum(z['qty']*max(0,s['prices'][z['stock']]-z['floor']) for z in ls)+sum(z['qty']*max(0,z['limit']-z['floor']) for z in os),sum(z['qty']*(z['limit']+z['fee_per_share']) for z in os),sum(z['qty']*z['fee_per_share'] for z in os))
def fee(q,p,cs,side='buy'):
 return sum((max(D(q)*p*D(c['rate']),D(c['minimum_local'])) for c in cs if c['side'] in ['both',side]),D(0))
counts=Counter();batch=[];inputtargets=read(F/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');rescued=[];prefixchecks=0;migrationschecked=0
with localcontext() as ctx:
 ctx.prec=70
 for check in identity['checks']:
  day=check['opening'];on=read(O/f'ON_{day}.json');off=read(O/f'OFF_{day}.json');ps=read(O/f'PREVIEWS_{day}.json')
  by={f"B|{p['clock']['decision_at']}|{p['sid']}|{p['role']}":p for p in ps}
  digest=hashlib.sha256(json.dumps([s0[day],ps],sort_keys=True,ensure_ascii=False,default=str,allow_nan=False).encode()).hexdigest()
  assert digest==on['input_before_sha256']==on['input_after_sha256']==off['input_sha256']
  first={z['key']:z for z in on['first_pass']};orders={z['key']:z for z in on['orders']};oldorders={z['key']:z for z in off['orders']}
  assert len(orders)==len(on['orders'])==len({z['sid'] for z in on['orders']}) and set(first)==set(orders)
  assert set(orders)|{z['key'] for z in on['rejected']}==set(by)
  for k,z in orders.items():
   p=by[k];x=p['preview'];a=first[k]
   assert z['role']==a['role']==p['role'] and z['pool']==a['pool']
   assert z['CP1_id']==a['CP1_id']==p['CP1_id'] and z['floor']==x['floor']
   if a['pool']=='confirmed':assert a['quantity']==x['minq']
   else:assert z['quantity']==a['quantity']
   q=z['quantity'];assert x['minq']<=a['quantity']<=q<=x['maxq'] and (q-x['minq'])%x['rule']['buy_step']==0
   assert D(z['gross'])==D(q)*D(x['price']) and D(z['gross'])<=D(p['budget'])
   assert D(z['fee'])==fee(q,D(x['price']),x['schedule']['components'])
  # Independently replay fixed original-order reservations and recorded migrations using plain JSON arithmetic.
  s=copy.deepcopy(s0[day]);available=D(s['available_exact']);mby=defaultdict(list)
  for m in on['migrations']:mby[m['candidate']].append(m)
  usedm=[];consumed=set(s['consumed']);requests=set(s['stock_requests'])
  for attempt in on['attempts']:
   k=attempt['key'];p=by[k];sec=s['sector_by_sid'][p['sid']];sect=s['sectors'][sec]
   ms=mby[k]
   assert bool(any(m['phase']=='evaluation' for m in ms))==attempt['eval_migrate']
   for m in ms:
    assert m['sector']==sec and m['old_status']==sect['status']
    pending=any(z['sector']==sec and z['attempt']==sect['attempt'] and z['pool']=='probe' and z['qty']>0 and z['status'] in ['open','cancel_pending'] for z in s['orders'].values())
    result=bool(sect['level']>0 and sect['active'] and not pending);assert result==m['result']
    moved=[]
    if result:
     for l in s['lots']:
      if l['sector']==sec and l['attempt']==sect['attempt'] and l['pool']=='probe':l['pool']='confirmed';moved.append(l['batch'])
     sect['status']='confirmed' if sect['level']==1 else 'expanded'
    elif pending:sect['status']='confirmed_unfunded'
    assert sorted(moved)==m['moved'] and sect['status']==m['new_status'];usedm.append(m);migrationschecked+=1
   if k not in orders:continue
   z=orders[k];q=z['quantity'];x=p['preview'];pool=z['pool'];pr=float(x['price']);fl=float(x['floor']);ff=float(D(z['fee']))
   pc,rr,_,_=resources(s,pool);sc,sr,_,_=resources(s,sector=sec);_,_,reserve,pendingfee=resources(s);nav=s['nav']-pendingfee-ff;cap=q*pr;risk=q*max(0,pr-fl)
   assert cap+ff<=min(float(available-D(s['decision_nav'])*D('.1')),s['cash']-reserve)+1e-7
   if pool=='probe':assert pc+cap<=.10*nav+1e-7 and rr+risk<=.005*nav+1e-7
   else:assert sect['level']>0 and p['role']=='mobile'
   fraction=.02 if pool=='probe' else (.02,.1,.2)[sect['level']]
   assert sc+cap<=fraction*nav+1e-7 and sr+risk<=.01*nav+1e-7
   held=sum(l['qty'] for l in s['lots'] if l['stock']==p['sid']);assert held*float(x['known_open'])+cap<=.1*float(D(s['decision_nav']))+1e-7
   if p['role']=='core':
    assert s['core_epoch'].get(p['sid'])!=p['epoch']
    allin=max(D(0),D(q)*(D(x['price'])-D(x['floor'])*D('.9995'))+fee(q,D(x['price']),x['schedule']['components'])+fee(q,D(x['floor'])*D('.9995'),x['schedule']['components'],'sell'))
    assert allin<=D(p['risk_budget'])
   else:assert p['CP1_id'] not in consumed;consumed.add(p['CP1_id'])
   assert k not in requests;requests.add(k)
   mirror=on['final_state']['orders'][k];assert mirror['qty']==q and mirror['role']==p['role'] and mirror['pool']==pool and mirror['floor']==fl and mirror['limit']==pr
   assert abs(mirror['fee_per_share']-float(D(z['fee'])/D(q)))<1e-15
   s['orders'][k]=copy.deepcopy(mirror);s['prices'].setdefault(p['sid'],pr);available-=D(z['gross'])+D(z['fee']);prefixchecks+=1
  assert len(usedm)==len(on['migrations'])
  assert s['lots']==on['final_state']['lots'] and s['orders']==on['final_state']['orders'] and s['sectors']==on['final_state']['sectors'] and s['prices']==on['final_state']['prices']
  assert consumed==set(on['final_state']['consumed']) and requests==set(on['final_state']['stock_requests'])
  assert available==D(on['available'])
  cap,risk,reserve,_=resources(s);assert abs(cap-on['capital'])<1e-7 and abs(risk-on['nominal_risk'])<1e-7 and abs(reserve-on['cash_reserve'])<1e-7
  assert sum((D(z['fee']) for z in orders.values()),D(0))==D(on['fees'])
  assert sorted(z['CP1_id'] for z in orders.values() if z['role']=='mobile')==on['proposed_stock_receipt_consumptions']
  new=set(orders)-set(oldorders);lost=set(oldorders)-set(orders);smaller=[k for k in set(oldorders)&set(orders) if orders[k]['quantity']<oldorders[k]['quantity']]
  counts.update(old=len(oldorders),new_total=len(orders),new_orders=len(new),lost_orders=len(lost),smaller_common_orders=len(smaller))
  for t in inputtargets:
   if t['next_open']!=day or t['exact_open_responsibility'] is None:continue
   found=[z for z in orders.values() if z['sid']==t['sid'] and z['role']=='mobile' and z['CP1_id']==t['receipt']]
   if found:rescued.append({'sid':t['sid'],'signal_day':t['signal_day'],'opening':day,'quantity':found[0]['quantity'],'pool':found[0]['pool']})
  batch.append({'opening':day,'old_orders':len(oldorders),'ON_orders':len(orders),'new':len(new),'lost':len(lost),'smaller_common':len(smaller),'all_fixed_prefix_guards_independently_passed':True})
assert counts=={'old':50,'new_total':161,'new_orders':116,'lost_orders':5,'smaller_common_orders':28}
assert rescued==[{'sid':'300666.SZ','signal_day':'2026-02-06','opening':'2026-02-09','quantity':100,'pool':'confirmed'}]
result={'status':'PASS_COMPONENT_ONLY_STOP_BEFORE_ACCOUNT','counts_are_orders_per_OPEN_not_unique_stocks_or_fills':dict(counts),'original15_rejected_target_receipts_rescued_in_private_plan':rescued,'original15_still_without_matching_mobile_plan':14,'independent_fixed_order_prefix_checks':prefixchecks,'independent_migration_replays':migrationschecked,'all_final_cash_capital_risk_reserve_fee_and_consumption_reconciled':True,'scope':'Plain JSON arithmetic replay of all final reservations and recorded evaluation/request migrations; no Runner, Account, fills or return simulation. Full-target selection predicates and confirmed-only truncation reviewed in frozen code; did not independently rerun every maxq search or every binary topup trial. Original holdings preserved except native pool migration.','judgment':'Valid allocation component behavior; the targeted rescue count is1 of15 and prior orders lose or shrink capital. No present support for continuous finance. The9 direct-release capability cases were not9 successful plans. Await original50 order opportunity-cost association before final economic interpretation; no clipped-quantity new-PnL claim.','compute_seconds_OFF_ON':completion['OFF_ON_compute_seconds'],'new_accounts':0,'new_restores':0,'source_sha256':{str(O/n):sha(O/n) for n in ['ON_COMPLETION.json','run_confirmed_min_first.py','confirmed_min_first_plan.py','fixed_combination_validation.py','retained_fixed_reservation.py','POLICY_SOURCE.diff','ON_SOURCE_SHA256.json']},'batches':batch}
(R/'PRIVATE_ON_13OPEN_RESULT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['batches','source_sha256']},ensure_ascii=False,indent=2))
