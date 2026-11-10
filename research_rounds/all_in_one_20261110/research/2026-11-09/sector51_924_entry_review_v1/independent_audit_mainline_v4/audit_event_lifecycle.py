"""Independent M4 actual event identity/spend and economic-SEED audit. No strategy imports."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
exec(compile((O/'reconcile_actual_ledger.py').read_text().split('for row in ledger:')[0],str(O/'reconcile_actual_ledger.py'),'exec'),globals())
plans=read(run/'EVENT_REQUEST_PLANS.json');logs=read(run/'EVENT_LOG.json');registry=read(run/'EVENT_REGISTRY.json');diag=read(run/'SEED_COMMISSION_DIAGNOSTIC.json');risk=read(run/'SEED_FLOOR_RISK.json');refs=read(run/'REFERENCE_DAILY.json');rqd=byday(plans);checks=Counter();errors=[];Z=D(0)
def ck(label,ok,ctx=None):
 checks[label]+=1
 if not ok:errors.append(dict(check=label,context=ctx))
def rawrow(s,dt):
 if s not in raw:raw[s]=pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')))
 return raw[s].loc[pd.Timestamp(dt)]
def surplus(s,dt,q,C):
 venue=version(rules['venue_versions'][s],dt)['venue'];cs=version(rules['fee_versions'][venue],dt)['schedule']['components'];total=Z
 for side,p in [('buy',C*D('1.0005')),('sell',C*D('.9995'))]:
  for c in cs:
   if c['name']!='net_brokerage' or c.get('side','both') not in ('both',side):continue
   proportional=q*p*D(c['rate']);total+=max(Z,D(c.get('minimum_local','0'))-proportional)
 return total
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');ids=sorted(mapping);K=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet')[ids];Q=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet')[ids];pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv[pv.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=K.index,columns=ids);K=K&pv.ge(0);Q=Q&K;cal=K.index;source_states={}
for sec in sectors:
 ss=[s for s in ids if mapping[s]==sec];N=len(ss);n=Q[ss].sum(axis=1);known=K[ss].sum(axis=1);u=N-known;paired=K[ss]&K[ss].shift(3,fill_value=False);J=paired.sum(axis=1);diff=(paired&Q[ss]&~Q[ss].shift(3,fill_value=False)).sum(axis=1)-(paired&~Q[ss]&Q[ss].shift(3,fill_value=False)).sum(axis=1);lo=(n>=3)&(((3*n>=N)&(J>0)&(diff>0))|(2*n>=N));hi=(n+u>=3)&(((3*(n+u)>=N)&((diff>0)|(J==0)))|(2*(n+u)>=N));state=pd.Series(-1,index=cal);state[~hi]=0;state[lo]=1;source_states[sec]=state
created={};running_spend=defaultdict(lambda:Z);attempted={};consume_records=[];first_day=ledger[0]['day'];last_day=ledger[-1]['day'];sources={(x['day'],x['sector51']):x for x in sector_daily}
for row in logs:
 eid=row['event_id'];day0=row['day'];act=row['event'];ck('certified_event_log_day',day0 in ld,[eid,day0]);
 if act in ['NEW_FALSE_TRUE_EVENT','COLD_EVENT_INITIALIZED']:
  ck('event_id_unique',eid not in created,eid);created[eid]=row;birth=row['birth_day'];sec=row['sector51'];t=pd.Timestamp(birth);st=source_states[sec];pos=st.index.get_loc(t);ck('source_actual_adjacent_FALSE_TRUE_birth',pos>0 and int(st.iloc[pos-1])==0 and int(st.at[t])==1,eid);ck('event_id_encodes_birth',eid==sec+'|'+birth,eid)
  if act=='COLD_EVENT_INITIALIZED':
   ck('cold_at_account_start_only',day0==first_day and birth<first_day,eid);ck('cold_full_known_TRUE_chain',(st.loc[birth:first_day]==1).all(),eid);expected_nav=D(1200000);ck('cold_anchor_label',row['budget_anchor']=='INITIAL_ACCOUNT_OPEN_ONCE',eid)
  else:expected_nav=D(ld[day0]['NAV']);ck('new_event_same_close_birth',birth==day0,eid)
  ck('event_birth_NAV_exact',D(row['birth_NAV'])==expected_nav,eid);ck('event_2pct_birth_cap',D(row['capital_cap'])==D('.02')*expected_nav,eid)
 else:ck('event_log_has_prior_birth',eid in created,[eid,act])
 if eid in created:
  for f in ['sector51','birth_day','budget_anchor','birth_NAV','capital_cap']:ck('immutable_'+f,row[f]==created[eid][f],[eid,day0,act])
 if act=='PRIORITY_REAL_OPEN_ATTEMPT':
  ck('once_priority_never_daily_refresh',eid not in attempted,eid);attempted[eid]=row
  old=[r for r in plans if r.get('event_id')==eid and r['sid']==row['sid'] and r['day']<day0 and r.get('priority_candidate')];ck('priority_has_prior_structural_plan',bool(old),[eid,day0,row['sid']]);z=rawrow(row['sid'],day0);ck('priority_OPEN_quote_factor_known',pd.notna(z.raw_open) and z.raw_open>0 and pd.notna(z.adjustment_factor) and z.adjustment_factor>0,[eid,day0]);ck('priority_flag_logged_true',row['priority_attempted'] is True,eid)
 if act=='ACTUAL_SEED_CAPITAL_CONSUMED':
  related=[o for o in orders if o['day']==day0 and o['sid']==row['sid'] and o['side']=='BUY_SEED' and o.get('event_id')==eid and o['allocation_phase'] in ['EVENT','RESIDUAL']];ck('event_consumption_actual_buy_unique',len(related)==1,[eid,day0,row['sid']]);cost=-D(related[0]['cash_delta']) if related else Z;ck('consumption_equals_all_in_actual',D(row['actual_cost'])==cost,[eid,day0,row['sid']]);ck('spend_before_exact',D(row['spent_before'])==running_spend[eid],[eid,day0]);running_spend[eid]+=cost;ck('spend_after_exact',D(row['spent_after'])==running_spend[eid]==D(row['spent']),[eid,day0]);ck('event_never_over_budget',running_spend[eid]<=D(row['capital_cap']),[eid,day0]);consume_records.append((day0,row['sid'],eid))
 else:ck('no_debit_or_refund_without_fill',D(row['spent'])==running_spend[eid],[eid,day0,act])
for eid,e in registry.items():
 ck('registry_birth_exists',eid in created,eid);ck('registry_spent_from_actual_buys',D(e['spent'])==running_spend[eid],eid);ck('registry_priority_from_actual_attempt',e['priority_attempted']==(eid in attempted),eid)
 reserved=sum((D(r['all_in_cost']) for r in plans if r['day']==last_day and r.get('event_id')==eid and r['allocation_phase'] in ['EVENT','RESIDUAL']),Z);ck('registry_final_reservation_exact',D(e['reserved'])==reserved,eid)
for order in orders:
 if order['side']!='BUY_SEED':continue
 s=order['sid'];t=order['day'];pd0=order['plan_day'];eid=order.get('event_id');q=order['qty'];C=D(str(rawrow(s,pd0).raw_close));when=str(cal[cal.get_loc(pd.Timestamp(pd0))+1].date());qr=version(rules['quantity_versions'][s],when)['rule'];planned=[r for r in plans if r['day']==pd0 and r['sid']==s and r['kind']=='SEED'];ck('actual_seed_prior_plan_unique',len(planned)==1,[t,s]);pp=planned[0] if planned else {};ck('seed_frozen_identity_phase',eid==pp.get('event_id') and order['allocation_phase']==pp.get('allocation_phase'),[t,s]);ck('seed_exact_frozen_economic_q',q==order['frozen_econ_q']==pp.get('econ_q')==pp.get('reference_q'),[t,s]);ck('seed_CLOSE_economic_minimum',surplus(s,when,q,C)<=D('.001')*q*C,[t,s]);prev=q-qr['buy_step'];ck('seed_PREVIOUS_legal_q_fails',prev<qr['buy_minimum'] or surplus(s,when,prev,C)>D('.001')*prev*C,[t,s]);closecost=q*C*D('1.0005')+fee(s,when,q,C*D('1.0005'),'buy');ck('seed_CLOSE_reservation_dated_fee',D(order['close_estimated_all_in'])==closecost,[t,s]);ck('seed_OPEN_minus_CLOSE_exact',D(order['open_minus_close_cost'])==-D(order['cash_delta'])-closecost,[t,s]);ck('strict_prior_CLOSE_before_OPEN',pd0<t,[t,s]);ck('event_debit_mutually_exclusive_with_mature',((t,s,eid) in consume_records)==(order['allocation_phase'] in ['EVENT','RESIDUAL']),[t,s]);
 if order['allocation_phase']=='EVENT':ck('priority_event_only_first_OPEN_batch',attempted[eid]['day']==t,[t,s])
 dd=next(x for x in diag if x['day']==t and x['sid']==s);Copen=D(str(rawrow(s,t).raw_open));extra=surplus(s,t,q,Copen);ck('OPEN_actual_fee_excess_diagnostic_only',D(dd['open_surcharge'])==extra and D(dd['excess'])==max(Z,extra-D('.001')*q*Copen) and dd['not_an_OPEN_gate'] is True,[t,s])
for dt,rows in byday(refs).items():
 er=sum((D(r['all_in_cost']) for r in plans if r['day']==dt and r['allocation_phase']=='EVENT'),Z)
 for r in rows:
  sec=r['sector51'];per=sum((D(p['all_in_cost']) for p in plans if p['day']==dt and p['allocation_phase']=='EVENT' and p['sector51']==sec),Z);ck('event_real_reservation_deducted_B',D(r['budget'])==D(r['budget_before_event'])-er,[dt,sec]);ck('reference_event_reserved_per_sector',D(r['event_reserved'])==per,[dt,sec]);ck('reference_total_T_no_double_allocate',D(r['T'])==D(r['T_mature_residual'])+per,[dt,sec])
report=dict(status='PASS' if not errors else 'FAIL',run=str(run),checks=dict(checks),check_count=sum(checks.values()),errors=errors,error_count=len(errors),events=len(created),priority_attempts=len(attempted),event_or_residual_actual_spend=str(sum(running_spend.values(),Z)),seed_buys=sum(o['side']=='BUY_SEED' for o in orders),seed_OPEN_fee_ratio_exceeded=sum(D(x['excess'])>0 for x in diag),historical_strategy_runs=0)
(O/(run.name+'_EVENT_LIFECYCLE_AUDIT.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['checks','errors']},ensure_ascii=False));print(json.dumps(errors[:15],ensure_ascii=False))
