"""Existing UP ledger and exact native market snapshots only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import date
import sys,json,pickle,math,statistics,importlib.util,time
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'));import month_runtime as M
spec=importlib.util.spec_from_file_location('up_original_evidence_reader',W/'g-s-C-engineering-causal-readonly-20261102/extract.py');E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)
Z=D(0);MONTH=E.R;CP=W/'g-s-C-cp1-reset-capital-readonly-20261102'
def read(p):return E.read(p)
def save(n,x):M.E.IO.write_json(HERE/n,E.clean(x),encoder=M.E.encode)
def group():return dict(sale_loss=Z,sale_gain=Z,buy=Z,realized=Z,unrealized=Z,dividend=Z,net=Z,initial_nominal_risk=Z,layers=[],stocks=set())
def add(g,l,prot):
 sales=l['actual_sell_parts'];g['sale_loss']+=sum((-D(s['realized_trade_PNL'])for s in sales if D(s['realized_trade_PNL'])<0),Z);g['sale_gain']+=sum((D(s['realized_trade_PNL'])for s in sales if D(s['realized_trade_PNL'])>0),Z)
 for k,f in [('buy','buy_gross'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('dividend','booked_dividend_income'),('net','total_contribution')]:g[k]+=D(l[f])
 g['initial_nominal_risk']+=D(l['initial_qty'])*max(Z,D(prot['entry_price'])-D(prot['initial_floor_raw']));g['layers'].append(l['layer']);g['stocks'].add(l['sid'])
def main():
 start=time.perf_counter();M.guard();events=read(CP/'EVENTS.json');prot=read(W/'g-s-C-engineering-causal-readonly-20261102/ALL_PROTECTION_EVENTS.json');meta=read(MONTH/'inputs/2025_26/metadata.json');output={};source={};rs={}
 for arm in events:
  p=MONTH/'runs'/arm/'2025-07-31-CLOSE.pkl';side=read(p.with_suffix('.provenance.json'));assert E.M.P.sha(p)==side['checkpoint_sha256'];r=pickle.loads(p.read_bytes());assert r.binding()==side['binding'];rs[arm]=r;source[str(p)]=E.M.P.sha(p)
 days=rs['2025_26-C10'].inputs.days
 assert [x['F1_packet_watermarks']for x in rs['2025_26-C10'].lifecycle]==[x['F1_packet_watermarks']for x in rs['2025_26-C_BATCH20'].lifecycle]
 snaps={d:E.snapshot('2025_26-C10',d)[0]for d in days}
 h1=rs['2025_26-C10'].inputs.table('h1');h={(z['sid'],z['day']):z['score']for z in h1.to_dict('records')};sectors=rs['2025_26-C10'].inputs.m['sectors']
 industry=[];market={};proof=rs['2025_26-C10'].account.policy.proof_history
 seeds={z['policy_scope']:E.asdict(M.H.F1.loads(json.dumps(z['f1_checkpoint'])))for z in rs['2025_26-C10'].inputs.seeds.values()}
 for ix,day in enumerate(days):
  x=snaps[day];prev=snaps[days[ix-1]]['f1']if ix else seeds;obs={z['policy_scope']:z for z in rs['2025_26-C10'].inputs.market_observations(day)}
  order=sorted(sectors,key=lambda s:(-float(h[(s,day)]),s))
  queue=x['results'][-1]['projection']['C_rank_binding']['industry_order']
  for sec in sectors:
   f=x['f1'][sec];ps=prev[sec];sc=x['account']['policy']['scopes'][sec];pr=[z for z in proof if z['scope']==sec and z['context']==sc['context']and z['known']<=date.fromisoformat(day).toordinal()and z['kind']=='price_advance'];last=max(pr,key=lambda z:(z['known'],z['seq']))if pr else None
   p=f['previous_close'];pc=ps['previous_close'];ret=math.log(p/pc)if p and pc else None;frozen=ps['scale'];history=f['prior_closes'];rolling=M.H.F1.scale_from_prior(tuple(ps['prior_abs_returns']))
   row=dict(day=day,sector=sec,scope=sc,native_F1_state_fields={k:f[k]for k in ['mode','last_at','previous_close','line','anchor','frontier','credit','scale','last_failure_at']},
     latest_same_context_advance=last,advance_age_industry_observations=sc['seq']-last['seq']if last else None,
     same_context_advance_day=date.fromordinal(last['confirmed']).isoformat()if last else None,
     H1=h[(sec,day)],H1_rank90=order.index(sec)+1,actual_C_queue=queue.index(sec)+1 if sec in queue else None,
     original_breadth=obs.get(sec,{}).get('breadth'),source_price=obs.get(sec,{}).get('price_input'),
     current_logreturn=ret,prior_frozen_F1_scale=frozen,original_prior_only_rolling_scale=rolling,
     absolute_return_over_original_prior_scale=abs(ret)/rolling if ret is not None and rolling else None,
     prior21_source_return=history[-1]/history[-22]-1 if len(history)>=22 else None,
     native_failure_after_decision_not_in_features=False)
   if 'price_advance'in sc['events']:assert rolling is not None and f['scale']==rolling
   industry.append(row);market[(sec,day)]=row
 save('INDUSTRY_ASOF.json',industry)
 for arm,es in events.items():
  r=rs[arm];bysector=defaultdict(group);bybatch=defaultdict(group);byproof=defaultdict(group);pp={z['layer']:z for z in prot[arm]};facts=r.inputs.table('facts');fm={(z['sid'],z['day']):z for z in facts.to_dict('records')};cp=r.inputs.table('cp');cps={sid:g.sort_values('day').to_dict('records')for sid,g in cp.groupby('sid')};results={z['at'][:10]:z for z in r.results};funded=[]
  for e in es:
   if e['classification']['kind']!='UP_CONTINUATION':continue
   for l in e['actual_layers']:
    p=pp[l['layer']];day=e['day'];sid=e['sid'];sec=l['sector'];add(bysector[sec],l,p);add(bybatch[day],l,p);ss=market[(sec,day)];key=ss['latest_same_context_advance']['event_id']if ss['latest_same_context_advance']else 'UNKNOWN|'+sec+'|'+str(ss['scope']['context']);add(byproof[key],l,p)
    cr=e['classification']['trace'];prior=[z for z in cps[sid]if z['day']<day and z['delta_frontier']>0];prior=prior[-1]if prior else None;oldprice=fm.get((sid,'2025-06-30'));d=e['C_demand'];fprice=D(str(e['classification']['signal_close']));pprice=D(p['entry_price']);rawmark=D(d['mark'])if d else None;floor=D(d['floor'])if d else None
    future=[z for z in cps[sid]if z['day']>day];firstcold=next((z['day']for z in future if z['reset_reason']=='E0_down_reset'),None)
    funded.append(dict(event=e,layer=l,source_initial_protection=p,industry=ss,
      stock_prior_observed_frontier=prior,stock_positive_frontier_age_observations=sum(z['day']>prior['day']and z['day']<=day for z in cps[sid])if prior else None,
      stock_current_abs_return_over_native_s=abs(cr['r'])/cr['s']if cr['r']is not None and cr['s']else None,
      stock_frozen_scale_over_previous_frontier_scale=cr['scale']/prior['scale']if prior and prior['scale']else None,
      stock_since_Jun30_return=float(fprice)/oldprice['close']-1 if oldprice else None,stock_prior21_return=None,stock_prior21_missing_saved_history=True,
      decision_preview_floor_distance=(rawmark*D('1.0005')-floor)/(rawmark*D('1.0005'))if d else None,
      actual_initial_floor_distance=p['initial_distance_fraction'],actual_open_gap_from_signal_raw=(pprice/(rawmark*D('1.0005'))-1)if d else None,
      future_first_negative_reset=firstcold,future_field_evaluation_only=True))
  ranked=sorted(bybatch.items(),key=lambda v:(-v[1]['sale_loss'],v[0]));total=sum((v['sale_loss']for v in bybatch.values()),Z);cum=Z;chosen=[];reached=False
  for day,g in ranked:
   cum+=g['sale_loss'];g['cumulative_loss_share']=cum/total;g['loss_share']=g['sale_loss']/total
   if not reached:chosen.append(day)
   if cum>total/2:reached=True
  positive=sorted([z for z in funded if D(z['layer']['total_contribution'])>0],key=lambda z:(-D(z['layer']['total_contribution']),z['layer']['sid'],z['layer']['layer']));closed=[];used=set()
  for z in positive:
   if not z['layer']['remaining_qty']and z['layer']['sector']not in used:closed.append(z);used.add(z['layer']['sector'])
   if len(closed)>=3:break
  opened=next((z for z in positive if z['layer']['remaining_qty']),None)
  timing={}
  for sec in bysector:
   rr=[e for e in es if e['C_demand']and e['C_demand']['sector']==sec and e['C_demand']['max_q']>=e['C_demand']['quantity']['buy_minimum']];marketqualified=[e for e in es if e['Q']is True and e['C_demand']is not None and e['C_demand']['sector']==sec];plan=next((e for e in es if e['C_plan_q']and e['C_demand']['sector']==sec),None);fills=[l for e in es for l in e['actual_layers']if l['sector']==sec and l['role']=='mobile'and l['pool']=='confirmed'];firstfill=min(fills,key=lambda l:l['opened'])if fills else None;first=min(rr,key=lambda e:e['day'])if rr else None
   timing[sec]=dict(first_provider_minimum_valid=first['day']if first else None,first_C_positive_plan=plan['day']if plan else None,first_actual_confirmed_mobile_fill=firstfill['opened']if firstfill else None,
     first_opportunity_market=market[(sec,first['day'])]if first else None,first_funded_market=market[(sec,plan['day'])]if plan else None,
     observed_plan_lag_market_sessions=days.index(plan['day'])-days.index(first['day'])if plan and first else None,
     prewindow_opportunity_left_censored=True)
  output[arm]=dict(actual_UP_layers=len(funded),gross_actual_sale_loss=total,by_sector=dict(bysector),batches_descending=ranked,minimum_majority_batches=chosen,by_industry_proof=dict(byproof),
    funded_layers=funded,sector_timing=timing,closed_positive_controls=closed,largest_open_positive_control=opened)
  print(arm,'UP',len(funded),'loss',total,'majority',chosen,flush=True)
 save('RESULTS.json',output);save('READ_INPUT_HASHES.json',dict(E.READS,**source));save('CHECKS.json',dict(no_account_events=True,no_new_indicators=True,no_policy_implementation=True,source_guard_passed=True,seconds=time.perf_counter()-start));print('READONLY_READY',round(time.perf_counter()-start,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as ex:
  import traceback
  save('ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),account_events=0));raise
