"""Fixed13 causal input/partial-action adapter. No strategy PnL or account backtest."""
import role_adapter as M
from pathlib import Path
from datetime import datetime,time as dt
import json,gzip,time,hashlib,bisect,math
from decimal import Decimal as D
from collections import Counter
import pandas as pd
import numpy as np
O=M.O/'history13-no-returns';W=M.O.parent;RR=M.RR;t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(M.E.native.encoded(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
cases=pd.read_csv(O/'FROZEN_CASES.csv');assert len(cases)==13;ids=set(cases.old);H=M.load('partial_history_market',RR/'s-entry-mechanism-audit-20261029/code/audit.py');bundle,market,frames,days=H.context(ids,True);facts=M.E.Facts(bundle,market);arith=M.load('partial_history_arithmetic',RR/'pv-strength-b5-20261025/code/arithmetic.py');proof=json.loads((RR/'ph1-cross-sector-20261028/event-validation.json').read_text());records={r['symbol']:r for r in proof['records'] if r['sector']=='TECH'};assert proof['passed']
B=RR/'pvr-local-finite-capital-20261029/baseline/accounts-v2';obj=json.loads((B/'I__S0_base.json').read_text());audit=obj['audit_log'];fillrows=[r for r in audit if r['kind']=='fill'];contracts={r['order_id']:r for r in audit if r['kind']=='entry_contract'};reserves={r['order_id']:r for r in audit if r['kind']=='reserve'};rootdaily={};rootq={};act={r['at'][:10]:r for r in audit if r['kind']=='risk_checkpoint'}
for filename,target in [('daily',rootdaily),('decisions',rootq)]:
 with gzip.open(B/f'{filename}.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account']=='I__S0_base':target[x['at'][:10]]=x
actual=pd.read_csv(W/'act-loss-facts-20261030/actual-cycles.csv',dtype=str,usecols=['cycle_id','entry_at','exit_at','exit_request','initial_shares','exit_shares','initial_floor_causal']).set_index('cycle_id');events={};signals={};epochs={};valid={};sources={};sigma_checks=[];checks=Counter();rows=[];actions=[];case_results=[];applications=[];traces=[]
for sid in sorted(ids):
 f=frames[sid];ep=RR/f'ph1-cross-sector-20261028/events/TECH/{sid}.parquet';sp=H.SNAP/'signals'/f'{sid}.parquet';fp=H.SNAP/'facts'/f'{sid}.parquet';e=pd.read_parquet(ep);sg=pd.read_parquet(sp,columns=['volume','observed_bar','source_invalid','synthetic_event_bar']);rec=records[sid]
 for p,h in [(ep,rec['output_sha256']),(fp,rec['inputs'][str(fp)]),(sp,rec['inputs'][str(sp)])]:assert sha(p)==h;sources[str(p)]=h
 assert f.index.equals(e.index) and f.close.equals(e.close) and f.segment_id.equals(e.segment_id);events[sid]=e;signals[sid]=sg
 known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);prior=on.groupby(f.segment_id).shift(fill_value=False);labels=pd.Series(None,index=f.index,dtype=object)
 for day in f.index[on&~prior]:labels.loc[day]=f'{sid}|source={int(f.loc[day,"segment_id"])}|E0={day.date()}'
 epochs[sid]=labels.groupby(f.segment_id).ffill().where(on,None)
 v=f[['close','segment_id']].join(sg[['volume']]);v=v[v[['close','volume']].gt(0).all(axis=1)&np.isfinite(v[['close','volume']]).all(axis=1)];valid[sid]={int(k):g for k,g in v.groupby('segment_id')}
 for ref in [bundle.series[sid].record['raw'],bundle.series[sid].record['adjustment']['actions']]:assert sha(ref['path'])==ref['sha256'];sources[ref['path']]=ref['sha256']
for p in [Path(__file__),M.O/'role_adapter.py',M.O/'restore_reservation_kernel.py',O/'PROTOCOL.txt',O/'FROZEN_CASES.csv',B/'I__S0_base.json',B/'daily.jsonl.gz',B/'decisions.jsonl.gz',W/'rearm-risk-boundary-design-20261030/risk_boundary_v2.py']:sources[str(p)]=sha(p)
save(O/'INPUT_FREEZE.json',dict(before_adaptation=True,identities=13,sha256=sources))
def clock(day):
 at=H.at(day,dt(15,10));return M.A.Clock(at,market.sessions['A'][bisect.bisect_right(market.sessions['A'],at)],at.date())
def sigma_at(sid,d,seg):
 g=valid[sid][seg];q=g[g.index<d].close.tail(64).to_numpy(float)
 if len(q)<64:return None
 def calc(v):
  r=[arith.log_ratio(v[i],v[i-1]) for i in range(1,64)];return max(math.sqrt(math.fsum(z*z for z in r)/63),1e-8)
 value=calc(q);assert value==calc(g.loc[:d][g.loc[:d].index<d].close.tail(64).to_numpy(float));sigma_checks.append(dict(symbol=sid,confirmed_day=str(d.date()),sigma=value,previous_returns=63,current_return_excluded=True,prefix_exact=True));return value
for case in cases.itertuples(index=False):
 cid=case.cycle_id;sid=case.old;meta=actual.loc[cid];entry=datetime.fromisoformat(meta.entry_at);end=datetime.fromisoformat(meta.exit_at);original_request=meta.exit_request[:10];entryrow=next(r for r in fillrows if r['receipt']['security_id']==sid and r['receipt']['side']=='buy' and r['receipt']['at']==meta.entry_at);contract=contracts[entryrow['order_id']];reserve=reserves[entryrow['order_id']];decision=datetime.fromisoformat(contract['decision_at']);f=frames[sid];ep=events[sid];sg=signals[sid];decisionday=pd.Timestamp(decision.date());group=epochs[sid].loc[decisionday];assert group is not None;seg0=int(f.loc[decisionday,'segment_id']);initial=D(reserve['gross_budget_cny'])+D(reserve['fee_reserved_cny']);a=M.RoleAccount(initial_cash=initial,context=lambda *_:group,fractional_split_policy=market.protocol['fractional_split_policy']);a.facts=facts;a.current_nav=D(contract['nav']);cl=clock(decisionday);quote=market.quote(sid,decision);ok,_=a.reserve_budget(quote=quote,clock=cl,gross_budget_cny=D(reserve['gross_budget_cny']),target_shares_cap=int(reserve['target_shares']));assert ok;window=market.window(sid,entry,'buy',D(1));receipt=a.fill_buy(sid,window);assert receipt is not None and receipt.shares==int(meta.initial_shares) and str(receipt.gross_cny)==entryrow['receipt']['gross_cny'] and str(receipt.fees_cny)==entryrow['receipt']['fees_cny'];checks['original_entry_exact']+=1;a.settle_due(entry)
 initialK=a.roles[sid]['K'];initialR=a.roles[sid]['R'];unknown=[];request_unknown=False;stop=None;first_app=None;core_days=0;ca_count=0;legal_failures=[];full_exit_date=None;source_dates=[d for d in days if entry.date()<=d.date()<=end.date()];sells=[];applied=set();role_arms=[];role_handoffs=[];played_until=None
 for d in source_dates:
  day=str(d.date());cl=clock(d)
  for action in market.actions.get(sid,[]):
   if action['effective_date']!=day or day in applied or day==str(entry.date()):continue
   old=a.quantity(sid);H.action(a,market,sid,action);applied.add(day);ca_count+=1;a.check_roles();actions.append(dict(cycle_id=cid,date=day,actual_before=old,local_after=a.quantity(sid),core=a.roles[sid]['K'],risk=a.roles[sid]['R'],cap=a.roles[sid]['cap'],cash_per_old_share=action['cash_per_old_share'],ratio=action['split_ratio'],paid_at=action.get('paid_at'),conditional_local_execution=True));checks['company_action_role_conservation']+=1
  if day!=str(entry.date()):
   op=H.at(day,dt(9,30));H.pay(a,market,op)
   if sid in a.exits:
    w=market.window(sid,op,'sell',D(1));out=a.fill_exit(sid,w) if w else None
    if out:sells.append(dict(cycle_id=cid,at=str(op),shares=out.shares,purpose=a.role_events[-1]['action'],remaining=a.quantity(sid),core=a.roles[sid]['K'] if sid in a.roles else 0,risk=a.roles[sid]['R'] if sid in a.roles else 0,fee=str(out.fees_cny),conditional_daily_bar_proxy=True));checks['partial_or_full_execution']+=1
    else:legal_failures.append(dict(day=day,reason='no_legal_fill_from_original_window'))
   H.pay(a,market,op)
  if not a.quantity(sid):full_exit_date=day;played_until=day;break
  H.pay(a,market,cl.decision_at);a.expire_day_buys(cl.decision_at);native=d in f.index;observed=bool(d in sg.index and sg.loc[d,'observed_bar'] and not sg.loc[d,'source_invalid'] and not sg.loc[d,'synthetic_event_bar']);eknown=d in ep.index;price=factor=floor=None;event=None
  if native:
   r=f.loc[d]
   if int(r.segment_id)!=seg0:unknown.append(dict(day=day,reason='source_changed_cannot_assert_frozen_unit'));stop='source_unit_unknown';break
   floor=float(r.i_floor) if np.isfinite(r.i_floor) else None
   if observed:
    price=float(r.raw_close);factor=float(r.factor);assert math.isclose(price*factor,float(r.close),rel_tol=64*np.finfo(float).eps,abs_tol=0);checks['economic_unit_exact_precision']+=1
  if eknown:
   event=int(ep.loc[d,'event']);piv=ep.loc[d,'pivot_date'];assert pd.isna(piv) or str(piv)[:10]<=day;checks['native_confirmation_not_backdated']+=1
  if not(native and observed and eknown):unknown.append(dict(day=day,reason='price_or_native_event_unknown'))
  original_full=day==original_request or not bool(act[day]['on']) or (native and not bool(f.loc[d,'i_target']));prev=a.roles[sid]['controller'];before_episodes=prev.episodes if prev else 0;prevphase=prev.phase if prev else None;quote=market.quote(sid,cl.decision_at)
  if quote is None:unknown.append(dict(day=day,reason='original_exit_quote_unknown'));stop='quote_interface_unknown';break
  sig=sigma_at(sid,d,seg0) if event==-1 else None;eid=f'{sid}|source={seg0}|confirmed={day}|native_event=-1' if event==-1 else None;diag=a.close_risk(sid,cl,quote,price,negative_id=eid,sigma=sig,floor=floor,factor=factor,full_exit=original_full,event_known=eknown,floor_known=native and floor is not None);rstate=a.roles[sid];controller=rstate['controller']
  if controller and controller.episodes>before_episodes:role_arms.append(day)
  if prevphase=='PROTECTED' and controller and controller.phase=='OBSERVING':role_handoffs.append(day)
  # Verify real I/Q against original ACT's complete eligibility snapshot. No new qualification system.
  _,stocks,sectors=facts.packet(cl.decision_at,'I');stock=next(s for s in stocks if s.security_id==sid);a.risk_state=dict(on=bool(act[day]['on']));stock=M.E.risk_policy.override(a,(stock,),cl,'ACT20_BREAK',M.A.Fact)[0];elig=M.A.eligibility(stock,{s.sector_id:s for s in sectors},cl,'S0');qtrue=elig.q is True;assert qtrue==(sid in rootq[day]['eligible']),(cid,day,'Q snapshot mismatch',elig,rootq[day]['eligible']);checks['Q_against_original_snapshot']+=1;ibuy=bool(native and f.loc[d,'i_buy']);flat=rstate['risk_flat_at'];fresh=bool(flat and cl.decision_at>flat and ibuy and qtrue and not original_full and sid not in a.exits and rstate['R']<rstate['cap'])
  row=dict(cycle_id=cid,date=day,physical=a.quantity(sid),core=rstate['K'],risk=rstate['R'],risk_reference=rstate['cap'],raw_i_buy=ibuy,q=elig.q,q_reasons=elig.reasons,original_ACT_on=bool(act[day]['on']),original_full_exit=original_full,negative_event=event,diagnostic=diag,recovery_application=fresh)
  rows.append(row);core_days+=rstate['K']>0;played_until=day
  if fresh:
   root=rootdaily[day];first_app=day;applications.append(dict(cycle_id=cid,at=str(cl.decision_at),symbol=sid,market_structure=epochs[sid].loc[d],entry_structure=group,new_I_receipt=f'{sid}|source={seg0}|I={day}',raw_i_buy=True,Q=True,risk_flat_at=str(flat),risk_reference=rstate['cap'],missing_risk_shares=rstate['cap']-rstate['R'],original_snapshot_nav=root['nav'],original_snapshot_available=root['available'],original_snapshot_reserved=root['order_reserved'],original_snapshot_positions=root['positions'],original_new_order_cap=str(D('.15')*D(root['nav'])),allocation='UNKNOWN_CHANGED_CASH_AND_CANDIDATE_MEMORY',submitted=False,restored_shares=None,do_not_treat_original_snapshot_as_new_account=True));stop='first_restore_allocation_unknown';break
  a.check_roles()
 else:stop='original_scope_end_with_responsibility' if a.quantity(sid) else 'original_full_exit_completed'
 if full_exit_date:stop='original_full_exit_completed'
 # Core continuity outside the actionable prefix is a conditional rule bound, not a manufactured trade.
 result=dict(cycle_id=cid,symbol=sid,name=case.name,entry=str(entry),entry_structure=group,initial_actual_shares=int(meta.initial_shares),initial_core=initialK,initial_risk=initialR,arm_dates=role_arms,handoff_dates=role_handoffs,risk_trim_requests=[str(r['at']) for r in a.role_events if r['kind']=='risk_trim_request'],risk_proxy_sales=[r for r in sells if r['purpose']=='risk_trim'],first_restore_application=first_app,actual_restore_submitted=False,actual_restore_quantity=None if first_app else 0,actionable_prefix_end=played_until,stop=stop,original_exit=str(end),conditional_full_exit=full_exit_date,core_nonzero_observations_before_stop=core_days,core_never_removed_by_risk_trim=True,core_conditional_structure_endpoint=str(end),company_actions_before_stop=ca_count,unknown=unknown,failed_execution_windows=legal_failures,cumulative_fees_to_stop=str(a.fees_cny),same_structure_fee_group=group,post_restore_fees_unknown=bool(first_app));case_results.append(result);traces.append(dict(cycle_id=cid,role_events=a.role_events,original_ledger_audit=a.audit_log,physical_shares_at_stop=a.quantity(sid),core_at_stop=a.roles[sid]['K'] if sid in a.roles else 0,risk_at_stop=a.roles[sid]['R'] if sid in a.roles else 0));print(dict(cycle_id=cid,trim=result['risk_proxy_sales'],restore=first_app,stop=stop,unknown=len(unknown)),flush=True)
assert len(case_results)==13 and all(sha(p)==h for p,h in sources.items())
save(O/'CASE_RESULTS.json',case_results);pd.DataFrame([{**r,'risk_proxy_sales':json.dumps(r['risk_proxy_sales'],ensure_ascii=False),'unknown':json.dumps(r['unknown'],ensure_ascii=False),'arm_dates':json.dumps(r['arm_dates']),'handoff_dates':json.dumps(r['handoff_dates'])} for r in case_results]).to_csv(O/'CASE_RESULTS.csv',index=False);save(O/'RESTORE_APPLICATIONS.json',applications);save(O/'EXECUTION_TRACES.json',traces);save(O/'ROW_CHECKS.json',rows);save(O/'CORPORATE_ACTION_CHECKS.json',actions);save(O/'SIGMA_PREFIX_CHECKS.json',sigma_checks);save(O/'VERIFICATION.json',dict(passed=True,cases=13,checks=dict(checks),restore_applications=len(applications),restore_execution_unsupported=len(applications),unknown_cycles=sum(bool(r['unknown']) for r in case_results),unknown_rows=sum(len(r['unknown']) for r in case_results),no_returns_computed=True,no_new_account_replay=True,seconds=time.monotonic()-t0));print('DONE',dict(checks),time.monotonic()-t0,flush=True)
