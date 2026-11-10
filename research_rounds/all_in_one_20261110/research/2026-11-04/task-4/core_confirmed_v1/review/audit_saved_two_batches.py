"""Audit saved allocations, literal migrations and scalar equations; never route."""
from pathlib import Path
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from collections import defaultdict,Counter
import json,copy,hashlib,time
P=Path(__file__).resolve().parent.parent;R=P/'review';S=P/'saved_batches';start=time.monotonic();Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(a,b):assert abs(float(a)-float(b))<1e-6,(a,b)
def fee(q,p,s,side,par):
 total=Z
 for c in s['components']:
  if c.get('side','both')not in[side,'both']:continue
  a=D(q)*p if c.get('amount_basis','notional')=='notional'else D(q)if c.get('amount_basis')=='shares'else D(q)*par
  v=max(D(str(c.get('minimum_local',0))),a*D(str(c['rate'])))
  if c.get('maximum_local')is not None:v=min(v,D(str(c['maximum_local'])))
  if c.get('rounding_unit')is not None:
   u=D(str(c['rounding_unit']));v=(v/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  total+=v
 return total
def resources(st,pool=None,sector=None):
 ls=[x for x in st['lots']if(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)];os=[x for x in st['orders'].values()if x['qty']>0 and x['status']in('open','cancel_pending')and(pool is None or x['pool']==pool)and(sector is None or x['sector']==sector)]
 return [sum(x['qty']*st['prices'][x['stock']]for x in ls)+sum(x['qty']*x['limit']for x in os),sum(x['qty']*max(0.,st['prices'][x['stock']]-x['floor'])for x in ls)+sum(x['qty']*max(0.,x['limit']-x['floor'])for x in os),sum(x['qty']*(x['limit']+x['fee_per_share'])for x in os)]
manifest=read(S/'OUTPUT_SHA256.json');assert all(sha(p)==h for p,h in manifest.items());runtime=read(S/'RUNTIME_SOURCE_SHA256.json');assert all(sha(p)==h for p,h in runtime.items());complete=read(S/'COMPLETION.json');assert complete['passed']and complete['compute_seconds']<60 and complete['source_freeze_sha256']==sha(P/'funding/SOURCE_FREEZE.json');assert read(S/'RUNTIME_PREPARATION.json')['total_preparation_seconds']<20
comp=read(S/'ALL496_COMPARISONS.json');assert len(comp)==496;co={(x['OPEN'],x['key']):x for x in comp};assert len(co)==496
out=[];totalres=0;typed=0;denials=0
for day in ['2026-02-11','2026-06-30']:
 raw=read(S/('PREVIEWS_'+day+'.json'));s0=read(S/('S0_'+day+'.json'))['state'];proofs=read(S/('FROZEN_CORE_PROOFS_'+day+'.json'));old=read(S/('OFF_'+day+'.json'));expect=read(S/('EXPECTED_OFF_'+day+'.json'));new=read(S/('ON_'+day+'.json'));assert {k:v for k,v in old.items()if k!='final_state'}==expect
 assert len(new['attempts'])==len(old['attempts'])==len(raw)
 by={(x['sid'],x['role']):x for x in raw};keys={'B|'+x['clock']['decision_at']+'|'+x['sid']+'|'+x['role']:x for x in raw}
 om={x['key']:x for x in old['orders']};nm={x['key']:x for x in new['orders']};assert len({x['sid']for x in new['orders']})==len(new['orders'])
 for k,i in keys.items():
  c=co[day,k];assert c['old_order']==om.get(k)and c['new_order']==nm.get(k)and c['quantity_delta']==(nm[k]['quantity']if k in nm else 0)-(om[k]['quantity']if k in om else 0)
 for mode,plan in [('OFF',old),('ON',new)]:
  st=copy.deepcopy(s0);available=D(s0['available_exact']);totalfees=Z;done=set();migrations=defaultdict(list)
  for m in plan['migrations']:migrations[m['candidate']].append(m)
  checks={x['key']:x for x in plan.get('reserve_checks',[])}
  for a in plan['attempts']:
   i=by[a['sid'],a['role']];k='B|'+i['clock']['decision_at']+'|'+i['sid']+'|'+i['role'];sector=st['sector_by_sid'][i['sid']]
   for m in migrations[k]:
    for batch in m['moved']:
     lot=next(x for x in st['lots']if x['batch']==batch);assert lot['pool']=='probe'and lot['sector']==m['sector']and lot['attempt']==st['sectors'][m['sector']]['attempt'];lot['pool']='confirmed'
    st['sectors'][m['sector']]['status']=m['new_status']
   if a.get('skip'):assert i['sid']in done or i['sid']in s0['pending_sells']or any(x['stock']==i['sid']and x['qty']>0 and x['status']in('open','cancel_pending')for x in s0['orders'].values());continue
   if a.get('result')!='reserved':continue
   o=next(x for x in plan['orders']if x['key']==k);x=i['preview'];q=o['quantity'];px=D(x['price']);floor=D(x['floor']);qr=x['rule'];fs=x['schedule'];par=D(i['quote']['par_value']);paid=fee(q,px,fs,'buy',par);assert o['fee']==str(paid)and D(o['gross'])==q*px and D(o['price'])==px and D(o['floor'])==floor
   assert qr['buy_minimum']<=q<=x['maxq']<=i['cap']and(q-qr['buy_minimum'])%qr['buy_step']==0 and q*px<=D(i['budget'])and i['sid']not in done
   if i['role']=='core':
    stop=floor*D('.9995');risk=max(Z,q*(px-stop)+paid+fee(q,stop,fs,'sell',par));assert risk<=D(i['risk_budget']);assert s0['core_epoch'].get(i['sid'])!=i['epoch']
   globalr=resources(st);scr=resources(st,sector=sector);pcr=resources(st,pool=o['pool']);pending=sum(v['qty']*v['fee_per_share']for v in st['orders'].values()if v['status']in('open','cancel_pending'));nav=st['nav']-pending-float(paid);cap=q*float(px);risk=q*max(0.,float(px)-float(floor));frac=.02 if o['pool']=='probe'else(.02,.1,.2)[st['sectors'][sector]['level']]
   assert cap+float(paid)<=min(float(available-D(st['decision_nav'])*D('.1')),st['cash']-globalr[2])+1e-6
   assert scr[0]+cap<=frac*nav+1e-6 and scr[1]+risk<=.01*nav+1e-6
   held=sum(z['qty']for z in st['lots']if z['stock']==i['sid']);assert held*float(D(x['known_open']))+cap<=.1*float(D(st['decision_nav']))+1e-6
   if o['pool']=='probe':assert pcr[0]+cap<=.1*nav+1e-6 and pcr[1]+risk<=.005*nav+1e-6
   actual=plan['final_state']['orders'][k];assert actual['role']==i['role']and actual['pool']==o['pool']and actual['qty']==q and actual['attempt']==st['sectors'][sector]['attempt'];near(actual['limit'],px);near(actual['floor'],floor);near(actual['fee_per_share'],float(paid/D(q)))
   if mode=='ON':
    ck=checks[k];assert ck['quantity']==q and ck['pool']==o['pool']and ck['epoch_unchanged_without_fill'];near(ck['before']['available'],available)
    for av,bv in zip(ck['before']['resources'],globalr):near(av,bv)
    for av,bv in zip(ck['before']['sector_resources'],scr):near(av,bv)
    if i['role']=='core':assert D(ck['CORE_fee_protection_risk'])==max(Z,q*(px-floor*D('.9995'))+paid+fee(q,floor*D('.9995'),fs,'sell',par))
    totalres+=1
   st['orders'][k]=actual;st['prices'].setdefault(i['sid'],float(px));available-=q*px+paid;totalfees+=paid;done.add(i['sid'])
  for a,b in zip(resources(st),[plan['capital'],plan['nominal_risk'],plan['cash_reserve']]):near(a,b)
  assert available==D(plan['available'])and totalfees==D(plan['fees']);final=plan['final_state'];assert final['lots']==st['lots']and final['orders']==st['orders']and final['core_epoch']==s0['core_epoch'];assert final['cash']==s0['cash']and final['nav']==s0['nav']and final['prices']==st['prices'];assert final['available_exact']==s0['available_exact']
  expectedtokens=set(s0['consumed'])|{o['CP1_id']for o in plan['orders']if o['CP1_id']};assert set(final['consumed'])==expectedtokens and set(final['stock_requests'])==set(s0['stock_requests'])|{o['key']for o in plan['orders']}
 for log in new['core_confirmed_log']:
  if log['result']!='reserved':assert log['before']==log['after'];denials+=1;continue
  typed+=1;k=log['budget_order'];o=nm[k];i=keys[k];proof=proofs[i['sid']];assert o['role']=='core'and o['pool']=='confirmed'and o['CP1_id']==log['receipt_id']==proof['canonical_receipt']['receipt_id'];assert set(log['probe_failures'])and set(log['probe_failures'])<={'probe_risk','sector_capital'};assert log['before']['token_consumed']is False and log['after']['token_consumed']is True;assert log['before']['lots_quantity']==log['after']['lots_quantity'];assert log['before']['sector_state']['episode']==proof['industry_episode']and log['before']['sector_state']['attempt']==proof['industry_attempt'];assert not log['confirmed_detail']['failures']and log['shares']==o['quantity']<=log['preview_maxq'];assert not any(z['sid']==o['sid']and z['role']=='mobile'for z in new['orders'])
  bd=log['confirmed_detail'];q=o['quantity'];px=float(D(o['price']));fee0=float(D(o['fee']));sr=log['before']['sector_resources'];nav=log['before']['budget_NAV']-log['before']['pending_fees']-fee0;near(bd['budget_NAV'],nav);near(bd['capital'],q*px);near(bd['nominal_risk'],q*max(0.,px-float(D(o['floor']))));assert sr[1]+bd['nominal_risk']<=.01*nav+1e-6
 out.append({'OPEN':day,'intents':len(raw),'OFF_orders':len(old['orders']),'ON_orders':len(new['orders']),'typed_CORE_orders':sum(z['role']=='core'and z['pool']=='confirmed'for z in new['orders']),'planned_fees_OFF':old['fees'],'planned_fees_ON':new['fees'],'available_OFF':old['available'],'available_ON':new['available'],'pending_nominal_risk_OFF':old['nominal_risk'],'pending_nominal_risk_ON':new['nominal_risk']})
assert typed==6 and totalres==11 and denials==21
result={'passed':True,'scope':'Saved complete private allocation outputs and literal migrations, no rerun of planner/route/native account.','dates':out,'all_intents':496,'all_archived_OFF_fields_exact':True,'archived_OFF_field_scope':'All15 archived fields exact; archived expected output did not contain final_state. New final_state independently reconciled from S0+literal recorded migrations+orders, not claimed to match absent archived state.','new_final_states_resources_fees_cash_epoch_tokens_checked':True,'all_ON_reservations_numeric_independently_checked':11,'typed_CORE_reservations':6,'failed_typed_attempts_readonly':21,'source_freeze_sha256':complete['source_freeze_sha256'],'adapter_sha256':complete['adapter_sha256'],'runtime_source_and_final_output_hashes_checked':True,'new_native_Account_Market_Runner_init':0,'new_route_or_planner_runs':0,'new_marks_or_fills':0,'limitations':['Private reservations, not actual fills or portfolio gains.','Planned fees/risk are reserve obligations, not yet executed fee cashflow/realized risk.','Static same prefix may reserve259 chip shares versus originalMobile627 and frozenCore1706; not proof fullON path quantity or profit.'],'source_sha256':{str((S/n).resolve()):sha(S/n)for n in ['COMPLETION.json','OUTPUT_SHA256.json','RUNTIME_SOURCE_SHA256.json','run_private.py','PRIVATE_PLAN.diff','ALL496_COMPARISONS.json','ON_2026-02-11.json','ON_2026-06-30.json']},'seconds':time.monotonic()-start};(R/'SAVED_TWO_BATCHES_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
