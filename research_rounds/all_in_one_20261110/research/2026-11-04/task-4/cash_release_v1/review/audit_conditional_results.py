"""Saved final fixed-combination arithmetic; never calls projection/model/account."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,localcontext,ROUND_CEILING,ROUND_HALF_UP
import json,hashlib,copy,time
O=Path(__file__).resolve().parent;F=O.parent/'funding';ROOT=O.parents[1]
PR=ROOT/'reentry_v1/funding_agent/private_projection';read=lambda p:json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resources(s,pool=None,sector=None):
 ls=[x for x in s['lots']if(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)]
 os=[x for x in s['orders'].values()if x['qty']>0 and x['status']in['open','cancel_pending']and(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)]
 return(sum(x['qty']*s['prices'][x['stock']]for x in ls)+sum(x['qty']*x['limit']for x in os),sum(x['qty']*max(0,s['prices'][x['stock']]-x['floor'])for x in ls)+sum(x['qty']*max(0,x['limit']-x['floor'])for x in os),sum(x['qty']*(x['limit']+x['fee_per_share'])for x in os),sum(x['qty']*x['fee_per_share']for x in os))
def fee(q,p,cs,par,side='buy'):
 v=D(0)
 for c in cs:
  if c.get('side','both')not in['both',side]:continue
  basis=c.get('amount_basis','notional');base=D(q)*p if basis=='notional'else D(q)if basis=='shares'else D(q)*par
  x=max(D(c.get('minimum_local',0)),base*D(c['rate']))
  if c.get('maximum_local')is not None:x=min(x,D(c['maximum_local']))
  if c.get('rounding_unit')is not None:
   u=D(c['rounding_unit']);x=(x/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  v+=x
 return v
def main():
 start=time.monotonic();completion=read(F/'CONDITIONAL_RUN_COMPLETION.json');assert completion['passed']and completion['compute_wall_seconds']<180 and completion['OPEN_plans']==52
 assert not(F/'CONDITIONAL_RUN_FAILURE.json').exists()and not(F/'CONDITIONAL_INVALID_PLAN.json').exists()
 freeze=read(F/'CONDITIONAL_RUN_FREEZE.json');assert all(sha(p)==h for p,h in freeze['sources'].items())
 ids=read(F/'CONDITIONAL_REFERENCE_IDENTITIES.json');assert ids['passed']and len(ids['checks'])==26
 s0={k[:10]:v['state']for k,v in read(ROOT/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json').items()}
 permission=read(F/'FROZEN_SIGNAL_PERMISSION.json')['dates'];dates=sorted(s0);plans={a:{}for a in['A0','B0','A1','B1']};counts=Counter();armtotals={};cashrows=[];outbatches=[]
 with localcontext()as ctx:
  ctx.prec=70
  for arm in plans:
   totalorders=0;gross=D(0);fees=D(0)
   for day in dates:
    z=read(F/(arm+'_'+day+'.json'));plans[arm][day]=z;ps=read(PR/('PREVIEWS_'+day+'.json'));by={'B|'+p['clock']['decision_at']+'|'+p['sid']+'|'+p['role']:p for p in ps}
    if arm in['A0','B0']:
     old=read(PR/(('OFF_'if arm=='A0'else'ON_')+day+'.json'))
     for k,v in old.items():assert z[k]==v,(arm,day,k)
     counts['complete_control_identities']+=1
    digest=hashlib.sha256(json.dumps([s0[day],ps],sort_keys=True,ensure_ascii=False,default=str,allow_nan=False).encode()).hexdigest()
    assert digest==(z['input_sha256']if arm.startswith('A')else z['input_before_sha256'])
    orders={o['key']:o for o in z['orders']};assert len(orders)==len(z['orders'])==len({o['sid']for o in z['orders']})
    if arm.startswith('B'):
     first={o['key']:o for o in z['first_pass']};assert set(first)==set(orders)
     assert set(orders)|{r['key']for r in z['rejected']}==set(by)
    else:
     assert len(z['attempts'])==len(ps)
     assert {'B|'+bykey['clock']['decision_at']+'|'+t['sid']+'|'+t['role']for t in z['attempts']for bykey in[by[next(k for k,p in by.items()if p['sid']==t['sid']and p['role']==t['role'])]]}==set(by)
    for k,o in orders.items():
     p=by[k];x=p['preview'];q=o['quantity'];par=D(p['quote']['par_value']);cs=x['schedule']['components']
     assert o['sid']==p['sid']and o['role']==p['role']and o['CP1_id']==p['CP1_id']and o['floor']==x['floor']
     assert x['minq']<=q<=x['maxq']and(q-x['minq'])%x['rule']['buy_step']==0
     assert D(o['gross'])==D(q)*D(x['price'])and D(o['gross'])<=D(p['budget'])
     assert D(o['fee'])==fee(q,D(x['price']),cs,par)
     if arm.startswith('B'):
      a=first[k];assert a['pool']==o['pool']and a['role']==o['role']and a['CP1_id']==o['CP1_id']
      if a['pool']=='confirmed':assert a['quantity']==x['minq']and a['quantity']<=q
      else:assert a['quantity']==q
    s=copy.deepcopy(s0[day]);available=D(s['available_exact']);mby=defaultdict(list);consumed=set(s['consumed']);requests=set(s['stock_requests'])
    for m in z['migrations']:mby[m['candidate']].append(m)
    for attempt in z['attempts']:
     k=attempt['key']if arm.startswith('B')else next(k for k,p in by.items()if p['sid']==attempt['sid']and p['role']==attempt['role'])
     p=by[k];sec=s['sector_by_sid'][p['sid']];sect=s['sectors'][sec];ms=mby.pop(k,[])
     if arm.startswith('B'):assert attempt['eval_migrate']==any(m['phase']=='evaluation'for m in ms)
     for m in ms:
      assert m['sector']==sec and m['old_status']==sect['status']
      pending=any(x['sector']==sec and x['attempt']==sect['attempt']and x['pool']=='probe'and x['qty']>0 and x['status']in['open','cancel_pending']for x in s['orders'].values())
      ok=bool(sect['level']>0 and sect['active']and not pending);assert ok==m['result'];moved=[]
      if ok:
       for l in s['lots']:
        if l['sector']==sec and l['attempt']==sect['attempt']and l['pool']=='probe':l['pool']='confirmed';moved.append(l['batch'])
       sect['status']='confirmed'if sect['level']==1 else'expanded'
      elif pending:sect['status']='confirmed_unfunded'
      assert sorted(moved)==m['moved']and sect['status']==m['new_status'];counts['recorded_migrations_independently_replayed']+=1
     if k not in orders:continue
     o=orders[k];q=o['quantity'];x=p['preview'];pool=o['pool'];price=float(x['price']);floor=float(x['floor']);ff=float(D(o['fee']));sd=p['clock']['decision_at'][:10]
     perm=permission[sd];eligible=perm['ACT_on']and perm['sectors'][sec]['stage_name']in['confirmed','expanded']
     buffer=D(0)if arm in['A1','B1']and eligible else D(s['decision_nav'])*D('.1')
     pc,pr,_,_=resources(s,pool);sc,sr,_,_=resources(s,sector=sec);_,_,reserve,pendingfee=resources(s);nav=s['nav']-pendingfee-ff;cap=q*price;risk=q*max(0,price-floor)
     assert cap+ff<=min(float(available-buffer),s['cash']-reserve)+1e-7,(arm,day,k,'cash')
     if pool=='probe':assert pc+cap<=.1*nav+1e-7 and pr+risk<=.005*nav+1e-7
     else:assert p['role']=='mobile'and sect['level']>0
     assert sc+cap<=(.02 if pool=='probe'else(.02,.1,.2)[sect['level']])*nav+1e-7 and sr+risk<=.01*nav+1e-7
     held=sum(l['qty']for l in s['lots']if l['stock']==p['sid']);assert held*float(x['known_open'])+cap<=.1*float(D(s['decision_nav']))+1e-7
     if p['role']=='core':
      assert s['core_epoch'].get(p['sid'])!=p['epoch'];par=D(p['quote']['par_value']);cs=x['schedule']['components'];stop=D(x['floor'])*D('.9995')
      allin=max(D(0),D(q)*(D(x['price'])-stop)+fee(q,D(x['price']),cs,par)+fee(q,stop,cs,par,'sell'));assert allin<=D(p['risk_budget'])
     else:assert p['CP1_id']not in consumed;consumed.add(p['CP1_id'])
     assert k not in requests;requests.add(k);mirror=z['final_state']['orders'][k]
     assert mirror['qty']==q and mirror['role']==p['role']and mirror['pool']==pool and mirror['floor']==floor and mirror['limit']==price
     assert abs(mirror['fee_per_share']-float(D(o['fee'])/D(q)))<1e-15
     s['orders'][k]=copy.deepcopy(mirror);s['prices'].setdefault(p['sid'],price);available-=D(o['gross'])+D(o['fee']);counts['final_order_prefixes_independently_checked']+=1
    assert not mby
    for k in['lots','orders','sectors','prices']:assert s[k]==z['final_state'][k],(arm,day,k)
    assert consumed==set(z['final_state']['consumed'])and requests==set(z['final_state']['stock_requests'])and available==D(z['available'])
    cap,risk,reserve,_=resources(s)
    assert abs(cap-z['capital'])<1e-7 and abs(risk-z['nominal_risk'])<1e-7 and abs(reserve-z['cash_reserve'])<1e-7
    assert sum((D(o['fee'])for o in orders.values()),D(0))==D(z['fees'])
    totalorders+=len(orders);gross+=sum((D(o['gross'])for o in orders.values()),D(0));fees+=D(z['fees'])
    outbatches.append(dict(arm=arm,opening=day,orders=len(orders),available=str(available),cash_pct_decisionNAV=float(available/D(s['decision_nav'])*100),nominal_risk=repr(risk),all_retained_prefix_guards_passed=True))
   armtotals[arm]=dict(order_count=totalorders,gross_sum_of_independent_reservations=str(gross),reserved_Fq=str(fees))
  changes={};comparison_counts={}
  for prefix,oldarm,newarm in[('A_NATIVE','A0','A1'),('B_MINFIRST','B0','B1')]:
   rows=read(F/(prefix+'_ALL4172_COMPARISONS.json'));assert len(rows)==len({(r['opening'],r['key'])for r in rows})==4172;c=Counter()
   for r in rows:
    d=r['opening'];key=r['key'];old={o['key']:o for o in plans[oldarm][d]['orders']}.get(key);new={o['key']:o for o in plans[newarm][d]['orders']}.get(key)
    assert r['old_order']==old and r['new_order']==new
    qty=lambda v:v['quantity']if v else 0;assert r['quantity_delta']==qty(new)-qty(old)
    assert D(r['gross_delta'])==(D(new['gross'])if new else D(0))-(D(old['gross'])if old else D(0))
    assert D(r['fee_delta'])==(D(new['fee'])if new else D(0))-(D(old['fee'])if old else D(0))
    stage=permission[r['signal_day']]['sectors'][r['sector']]['stage_name'];eligible=permission[r['signal_day']]['ACT_on']and stage in['confirmed','expanded'];assert eligible==r['cash_release_eligible']
    expectedbuffer=D(0)if eligible else D(s0[d]['decision_nav'])*D('.1');assert D(r['required_buffer_new'])==expectedbuffer
    status='added'if new and not old else'lost'if old and not new else'shrunk'if qty(new)<qty(old)else'increased'if qty(new)>qty(old)else'unchanged_reserved'if old else'not_reserved_both';c[status]+=1
    if old and new and old['pool']!=new['pool']:c['common_pool_changed']+=1
   changes[prefix]={k:c[k]for k in['added','lost','shrunk','increased','common_pool_changed']};comparison_counts[prefix]=len(rows)
  summary=read(F/'CONDITIONAL_MATRIX_SUMMARY.json')
  for arm,want in summary['arms'].items():
   assert armtotals[arm]['order_count']==want['order_count']
   assert D(armtotals[arm]['gross_sum_of_independent_reservations'])==D(want['gross_sum_of_independent_reservations'])and D(armtotals[arm]['reserved_Fq'])==D(want['reserved_Fq'])
  for prefix,key in[('A_NATIVE','A1_vs_A0'),('B_MINFIRST','B1_vs_B0')]:
   for field,v in summary[key].items():assert changes[prefix][field]==v
  focus=read(ROOT/'reentry_v1/funding_agent/ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');rescues={arm:[]for arm in plans}
  for target in focus:
   d=target['next_open'];sd=target['signal_day'];sid=target['sid'];rid=target['receipt']
   for arm in plans:
    found=[o for o in plans[arm][d]['orders']if o['sid']==sid and o['role']=='mobile'and o['CP1_id']==rid]
    if found:rescues[arm].append(dict(opening=d,signal_day=sd,sid=sid,quantity=found[0]['quantity'],pool=found[0]['pool'],receipt=rid))
  for f in read(F/'CONDITIONAL_ALL16_FOCUS.json'):
   for arm in plans:assert f[arm]==[o for o in plans[arm][f['opening']]['orders']if o['sid']==f['sid']and o['role']=='mobile'and o['key'].split('|')[1][:10]==f['signal_day']]
 result=dict(status='PASS_CONDITIONAL_COMPONENT_ONLY_STOP_ACCOUNT',controls_exact=counts['complete_control_identities'],independent_checks=dict(counts),arm_totals=armtotals,changes=changes,complete_comparison_rows=comparison_counts,original16_target_receipt_matches=rescues,compute_seconds=completion['compute_wall_seconds'],new_accounts=0,new_restores=0,scope='All final fixed reservations and recorded migrations replayed with plain JSON arithmetic; all fees, cash, capital, retained risk/stock/quantity/core-risk/consumption checked. Full maxq argmax and topup binary searches reviewed in frozen source, not independently rerun.',seconds=time.monotonic()-start,batches=outbatches)
 (O/'CONDITIONAL_RESULT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in['batches','original16_target_receipt_matches']},ensure_ascii=False,indent=2));print('rescues',{k:len(v)for k,v in rescues.items()})
if __name__=='__main__':main()
