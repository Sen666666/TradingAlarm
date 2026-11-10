"""One pure static quantity pass over existing reviewed JSON, no trading imports."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import date,datetime
from collections import Counter,defaultdict
import ast,json,hashlib,time,statistics
from quantity_core import pure_quantity,maximum_quantity
O=Path(__file__).resolve().parent;T=O.parents[1];Q=T/'loss_correction/entry_risk_commitment_review';M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def encoded(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {k:encoded(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [encoded(v)for v in x]
 return x
RULES=M/'pvr-act-comparison-20261027/execution-rules-v2.json'
PROXY=M/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json'
RULE_FN=M/'rs-h1-execution-20261025/code/market_rules.py'
def properties():
 checks=[]
 def ck(name,test):assert test,name;checks.append(name)
 ck('core_factor_unknown_bypass',pure_quantity('core',13,100,100,None,None,['factor'])['qnew']==13)
 ck('risk0_no_new',pure_quantity('mobile',1000,100,100,D(0),D(1))['qnew']==0)
 ck('negative_width_no_new',pure_quantity('mobile',1000,100,100,D(1000),D(-1))['qnew']==0)
 ck('actualq_smaller_than_plan_not_refrozen',pure_quantity('mobile',100,100,100,D(1000),D(1))['qnew']==100)
 ck('wider_gap_same_R_reduces',pure_quantity('mobile',1000,100,100,D(500),D(1))['qnew']==500 and pure_quantity('mobile',1000,100,100,D(500),D(2))['qnew']==200)
 ck('exact_tie_accepted',pure_quantity('mobile',1000,100,100,D(300),D(1))['qnew']==300)
 ck('STAR_min200_step1',pure_quantity('mobile',422,200,1,D(211),D(1))['qnew']==211)
 ck('STAR_below_min_disappears',pure_quantity('mobile',422,200,1,D(199),D(1))['qnew']==0)
 ck('BJ_min100_step1',pure_quantity('mobile',333,100,1,D(222),D(1))['qnew']==222)
 ck('partial_actual_is_not_new_lot',pure_quantity('mobile',150,100,100,D(10000),D(1))==dict(qnew=100,qbase=100,status='KNOWN_PRIMARY_FIXED_PRICE',reasons=[]))
 cases=0
 for minimum,step in [(100,100),(200,1),(100,1)]:
  for cap in [0,99,100,150,199,200,201,333,422]:
   for width in [D('.01'),D('1'),D('2.5')]:
    last=-1
    for R in [D('.1'),D('100'),D('200'),D('500'),D('1000')]:
     z=pure_quantity('mobile',cap,minimum,step,R,width);legal=[0]+[q for q in range(minimum,cap+1,step)if D(q)*width<=R];assert z['qnew']==max(legal);assert 0<=z['qnew']<=cap and z['qnew']>=last;last=z['qnew'];cases+=1
 ck('finite_exhaustive_and_monotone_405_cases',cases==405)
 return dict(passed=True,checks=checks,exhaustive_cases=cases)
def main():
 assert not (O/'DONE.json').exists(),'single completed screen already exists'
 freeze=read(O/'FREEZE.json');assert all(sha(p)==h for p,h in freeze['sources'].items()),'screen source/input changed'
 started=time.monotonic();prop=properties();save('PROPERTIES.json',prop)
 ruledata=read(RULES);protocol=read(PROXY);approved=protocol['approved_proxy_ids']
 class RuleUnavailable(ValueError):pass
 nodes=[n for n in ast.parse(RULE_FN.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in {'day','version_on'}];env=dict(date=date,datetime=datetime,RuleUnavailable=RuleUnavailable);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(RULE_FN)+'::pure-version-only','exec'),env);version_on=env['version_on']
 allrows=[];allsummary={};fixedtail=[];unknowns=[]
 for window,total in [('2022_2024',2265),('strong',1171)]:
  entries=read(Q/(window+'_ENTRIES.json'));orders=read(Q/(window+'_ORDERS.json'));control=read(Q/(window+'_ORIGINAL_FIXED_TAIL_CONTROLS.json'));assert len(entries)==len(orders)==total
  byorder={x['budget_order']:x for x in orders};assert len(byorder)==len(entries);assert all(len(x['layer_ids'])==1 for x in orders),'multi-fill order requires explicitly separate method; no silent layer risk reset'
  tailids={m['layer']for x in control for m in x['matched_No60']};rows=[]
  for e in entries:
   order=byorder[e['budget_order']];q0=e['actual_fill_quantity'];assert q0==order['actual_total_filled_shares'];assert e['layer']in order['layer_ids'];assert e['frozen_intent']['cap']==order['frozen_cap']
   p=D(e['actual_execution_price']);assert p==D(e['actual_raw_open'])*D('1.0005')
   fd=D(e['signal_factor']);ff=D(e['fill_factor']);F=D(e['frozen_initial_adjusted_floor'])/ff
   ref=D(e['signal_close_raw'])*D('1.0005');Fdec=D(e['frozen_initial_adjusted_floor'])/fd;plan_cap=order['frozen_cap'];R=D(plan_cap)*max(D(0),ref-Fdec)
   why=list(e['reference_unknown_reasons']);assert e['role']=='core' or (fd==ff and e['signal_source_segment']==e['fill_source_segment'])or why
   rule=version_on(ruledata['quantity_versions'][e['sid']],e['opened'][:10],approved);v=rule['rule'];minimum=v['buy_minimum'];step=v['buy_step']
   if not why:assert R==D(e['frozen_order_full_plan_reference_risk'])==D(order['planned_reference_nominal_risk'])
   z=pure_quantity(e['role'],q0,minimum,step,R,p-F,why);qnew=z['qnew'];base=z['qbase'];assert 0<=qnew<=q0
   if z['status']=='KNOWN_PRIMARY_FIXED_PRICE':
    assert D(e['actual_raw_open'])>F,'original preview protection not satisfied'
    assert qnew==0 or(qnew>=minimum and(qnew-minimum)%step==0)
    assert D(qnew)*(p-F)<=R
    if qnew and qnew+step<=q0:assert D(qnew+step)*(p-F)>R
   gross0=D(q0)*p;A=D(q0)*max(D(0),p-F);newA=D(qnew)*max(D(0),p-F)
   row=dict(window=window,layer=e['layer'],budget_order=e['budget_order'],sid=e['sid'],role=e['role'],pool=e['pool_at_fill'],action=e['action'],decision_at=e['decision_at'],opened=e['opened'],original_risk_reference_class=e['risk_reference_class'],fixed_original_tail_match=e['layer']in tailids,source_segment=e['signal_source_segment'],signal_factor=str(fd),fill_factor=str(ff),frozen_adjusted_floor=e['frozen_initial_adjusted_floor'],floor_raw=str(F),original_plan_cap_S=plan_cap,original_plan_reference_nominal_R_CNY=str(R),R_applies_only_mobile=e['role']=='mobile',existing_core_allin_risk_budget=e['existing_core_allin_risk_budget'],original_reported_reference_R=e['frozen_order_full_plan_reference_risk'],q0_actual=q0,qbase_legal_new_order=base,qnew=qnew,execution_price=str(p),rule_id=v['rule_id'],buy_minimum=minimum,buy_step=step,fill_step=v['fill_step'],dated_rule_source=rule['source_id'],dated_rule_from=rule['from'],dated_rule_to=rule['to'],status=z['status'],unknown_reasons=z['reasons'],original_q_new_order_legal=(q0>=minimum and(q0-minimum)%step==0),quantity_reduced=qnew<q0,known_risk_reduced=(base is not None and qnew<base),known_minunit_disappears=(z['status']=='KNOWN_PRIMARY_FIXED_PRICE'and base>0 and qnew==0),original_fixed_price_gross=str(gross0),new_fixed_price_gross=str(D(qnew)*p),fixed_price_gross_delta=str(D(q0-qnew)*p),known_risk_only_gross_delta=str(D(base-qnew)*p)if base is not None else None,legal_projection_gross_delta=str(D(q0-base)*p)if base is not None else None,original_actual_nominal_risk=str(A),new_fixed_price_nominal_risk=str(newA),fixed_price_nominal_risk_delta=str(A-newA),original_buy_fee_UNSCALED=e['buy_fee'],original_lifetime_net_ASSOCIATION_ONLY=e['net'],original_strict_realized_ASSOCIATION_ONLY=e['strict_realized'],original_open_unrealized_ASSOCIATION_ONLY=e['open_unrealized'],original_dividend_AR_ASSOCIATION_ONLY=e['recognized_dividend_AR'],CA_calendar='Independent ENTRY_RISK_ACTION_INTERVAL_AUDIT bound; no CA share-cap/R transformation supported')
   rows.append(row)
   if z['status']=='UNKNOWN_NO_NEW_MOBILE':unknowns.append(row)
  def agg(rr):
   numeric=['original_fixed_price_gross','new_fixed_price_gross','fixed_price_gross_delta','known_risk_only_gross_delta','legal_projection_gross_delta','original_actual_nominal_risk','new_fixed_price_nominal_risk','fixed_price_nominal_risk_delta','original_buy_fee_UNSCALED','original_lifetime_net_ASSOCIATION_ONLY','original_strict_realized_ASSOCIATION_ONLY','original_open_unrealized_ASSOCIATION_ONLY','original_dividend_AR_ASSOCIATION_ONLY']
   a=dict(orders=len(rr),stocks=len({r['sid']for r in rr}),q0_actual_sum=sum(r['q0_actual']for r in rr),qnew_sum=sum(r['qnew']for r in rr),quantity_reduced=sum(r['quantity_reduced']for r in rr),known_risk_reduced=sum(r['known_risk_reduced']for r in rr),known_minunit_disappears=sum(r['known_minunit_disappears']for r in rr),unknown_no_new_mobile=sum(r['status']=='UNKNOWN_NO_NEW_MOBILE'for r in rr),original_q_not_new_order_legal=sum(not r['original_q_new_order_legal']for r in rr),statuses=dict(Counter(r['status']for r in rr)))
   for k in numeric:a[k]=str(sum((D(r[k])for r in rr if r[k]is not None),D(0)))
   a['original_gross_of_changed_orders']=str(sum((D(r['original_fixed_price_gross'])for r in rr if r['quantity_reduced']),D(0)))
   a['original_net_of_changed_orders_ASSOCIATION_ONLY']=str(sum((D(r['original_lifetime_net_ASSOCIATION_ONLY'])for r in rr if r['quantity_reduced']),D(0)))
   a['original_gross_of_known_minunit_disappeared']=str(sum((D(r['original_fixed_price_gross'])for r in rr if r['known_minunit_disappears']),D(0)))
   ratios=[r['qnew']/r['q0_actual']for r in rr if r['known_risk_reduced']];a['known_shrunk_qty_ratio_median']=statistics.median(ratios)if ratios else None
   return a
  groups={'ALL':agg(rows),'CORE':agg([r for r in rows if r['role']=='core']),'MOBILE_KNOWN':agg([r for r in rows if r['status']=='KNOWN_PRIMARY_FIXED_PRICE']),'MOBILE_UNKNOWN':agg([r for r in rows if r['status']=='UNKNOWN_NO_NEW_MOBILE']),'FIXED_ORIGINAL_PVR_TAIL_EXACT_MATCH':agg([r for r in rows if r['fixed_original_tail_match']])}
  for field in ['action','pool','role','original_risk_reference_class','rule_id']:
   for key in sorted({r[field]for r in rows}):groups[field+'='+key]=agg([r for r in rows if r[field]==key])
  for period in sorted({r['opened'][:4]+'Q'+str((int(r['opened'][5:7])-1)//3+1)for r in rows}):groups['quarter='+period]=agg([r for r in rows if r['opened'][:4]+'Q'+str((int(r['opened'][5:7])-1)//3+1)==period])
  if window=='2022_2024':
   for key,pred in [('2024pre924',lambda r:'2024-01-01'<=r['opened'][:10]<'2024-09-24'),('2024_rebound_sixclose',lambda r:'2024-09-24'<=r['opened'][:10]<='2024-10-08'),('2024postOct8_303',lambda r:r['opened'][:10]>'2024-10-08')]:groups[key]=agg([r for r in rows if pred(r)])
   assert groups['2024postOct8_303']['orders']==303
  fixedtail.append(dict(window=window,original_cohort=len(control),exact_No60_matched=len(tailids),unmatched_original=sum(not x['matched_No60']for x in control),matched_summary=groups['FIXED_ORIGINAL_PVR_TAIL_EXACT_MATCH'],controls_preserved_unmodified_source=str(Q/(window+'_ORIGINAL_FIXED_TAIL_CONTROLS.json'))))
  save(window+'_ROWS.json',rows);save(window+'_SUMMARY.json',groups);allsummary[window]=groups;allrows+=rows
 assert len(allrows)==3436;assert len(unknowns)==13;assert all(r['qnew']==r['q0_actual']for r in allrows if r['role']=='core')
 save('UNKNOWN_NO_NEW_MOBILE.json',unknowns);save('FIXED_ORIGINAL_TAIL_COHORTS.json',fixedtail);save('SUMMARY.json',allsummary)
 save('DONE.json',dict(status='PURE_QUANTITY_SCREEN_COMPLETE_NOT_ECONOMIC',orders=len(allrows),unknown_mobile=len(unknowns),core_factor_change_bypass=sum(r['signal_factor']!=r['fill_factor']for r in allrows if r['role']=='core'),seconds=time.monotonic()-started,new_account_objects=0,new_order_or_fill_events=0,new_PnL_NAV=0,quantity_solver='exact AST LR.maximum_quantity',single_pass=True,decimal_context=str(getcontext()),sources_post_exact=all(sha(p)==h for p,h in freeze['sources'].items()),CA_calendar_coverage='independent receipt bound; not recomputed by quantity screen',CA_transformation_supported=False))
 print(json.dumps({k:{g:v for g,v in s.items()if g in ['MOBILE_KNOWN','MOBILE_UNKNOWN','CORE','FIXED_ORIGINAL_PVR_TAIL_EXACT_MATCH','2024postOct8_303']}for k,s in allsummary.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
