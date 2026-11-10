"""Frozen 13-case boundary behavior. No orders, fill calls, or new profit ledger."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
import sys,json,math,time,hashlib,importlib.util,bisect
import pandas as pd
import numpy as np

T=time.monotonic();O=Path(__file__).resolve().parent;W=O.parents[1];ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);x=importlib.util.module_from_spec(spec);sys.modules[name]=x;spec.loader.exec_module(x);return x
freeze=json.loads((O/'CASE_FREEZE.json').read_text());assert all(sha(p)==h for p,h in freeze['sha256'].items());assert not (O/'RESULTS.csv').exists()
cases=pd.read_csv(O/'FROZEN_CASES.csv');ids=set(cases.old);assert len(cases)==13
B5=RR/'pv-strength-b5-20261025/code';sys.path.insert(0,str(B5));E=module('boundary_original_event_kernel',B5/'evidence.py')
H=module('boundary_original_market_helpers',RR/'s-entry-mechanism-audit-20261029/code/audit.py');_,m,_,_=H.context(ids,False)
sys.path.insert(0,str(O.parent));from minimal_boundary import BoundaryState
snap=H.SNAP;PH=RR/'ph1-cross-sector-20261028';proof=json.loads((PH/'event-validation.json').read_text());rec={x['symbol']:x for x in proof['records'] if x['sector']=='TECH'};assert proof['passed']
fcols=['close','segment_id','e0_target','e0_ready','i_target','i_floor','i_buy']
history={};evs={};scales={};bars={};ident={};checks=dict(original_event_rows_exact=0,warning_sigma_manual_exact=0,warning_sigma_physical_prefix_exact=0,causal_close_exact=0,original_floor_steps_exact=0)
def original_with_sigma(b):
 captured={};old=sys.getprofile()
 def take(frame,event,arg):
  if event=='return' and frame.f_code is E._event_facts.__code__:
   captured.update(sigma=pd.Series(frame.f_locals['sigma'].copy(),index=frame.f_locals['d'].index))
 try:sys.setprofile(take);out=E._event_facts(b)[0]
 finally:sys.setprofile(old)
 return out,captured['sigma']
for s in sorted(ids):
 fp=snap/'facts'/f'{s}.parquet';sp=snap/'signals'/f'{s}.parquet';ep=PH/'events/TECH'/f'{s}.parquet'
 for p,hh in [(fp,rec[s]['inputs'][str(fp)]),(sp,rec[s]['inputs'][str(sp)]),(ep,rec[s]['output_sha256'])]:assert sha(p)==hh;ident[str(p)]=hh
 f=pd.read_parquet(fp,columns=fcols);raw=pd.read_parquet(sp,columns=['volume']);ev=pd.read_parquet(ep,columns=['event','close','segment_id']);assert f.index.equals(ev.index);evs[s]=ev;history[s]=f;sig=[];stockbars={}
 for seg,g in f.groupby('segment_id',sort=False):
  b=g[['close']].join(raw,how='left');out,ss=original_with_sigma(b);np.testing.assert_array_equal(out.event.to_numpy(float),ev.loc[g.index,'event'].to_numpy(float));checks['original_event_rows_exact']+=len(g);sig.append(ss);stockbars[int(seg)]=b
 scales[s]=pd.concat(sig);bars[s]=stockbars
source_paths=[W/'act-loss-facts-20261030/actual-cycles.csv',W/'act-loss-facts-20261030/actual-holding-close-paths.csv',W/'down-event-transfer-exposure-20261030/all-holding-exposure-before-labels.csv',O.parent/'minimal_boundary.py',B5/'evidence.py',B5/'arithmetic.py',Path(__file__)]
ident.update({str(p):sha(p) for p in source_paths})
save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),case_freeze_sha=sha(O/'CASE_FREEZE.json'),sigma_from_original_function_return_frame=True,before_boundary_behavior=True,sha256=ident))
ac=pd.read_csv(source_paths[0],float_precision='round_trip',usecols=['cycle_id','entry_at','exit_at','exit_request','initial_floor_causal','buy_gross','buy_fees','exit_shares'])
ac=ac[ac.cycle_id.isin(cases.cycle_id)].set_index('cycle_id')
pathcols=['day','shares','net_liquidation_pnl','net_liquidation_return','cycle_id','old_floor_causal','new_floor_causal','causal_close','ACT_on','I_active']
paths=pd.read_csv(source_paths[1],float_precision='round_trip',usecols=pathcols);paths=paths[paths.cycle_id.isin(cases.cycle_id)]
excols=['date','cycle_id','event','e0_I_active','ACT_on','old_sell_pending','old_buy_pending','old_signal']
ex=pd.read_csv(source_paths[2],usecols=excols);ex=ex[ex.cycle_id.isin(cases.cycle_id)]
out=[];trace=[];execution=[];wall_load=time.monotonic()-T

def next_execution(s,c,day,q):
 tm=H.at(day,dt(15,10));entry=datetime.fromisoformat(c.entry_at);mature=m.lag('A',entry,m.protocol['sellable_lag_sessions']['A']);quote=m.quote(s,tm)
 nexti=bisect.bisect_right(m.sessions['A'],tm);nextopen=m.sessions['A'][nexti] if nexti<len(m.sessions['A']) else None
 base=dict(next_market_open=str(nextopen) if nextopen else None,next_legal_execution=None,proxy_quantity=None,full_quantity_proxy=None,execution_status='unknown',execution_checks=[])
 if quote is None:base['execution_status']='decision_quote_unknown';return base
 end=datetime.fromisoformat(c.exit_at)
 for op in m.sessions['A'][nexti:]:
  if op>end:break
  why=None;win=m.window(s,op,'sell',1)
  changes=[a for a in m.actions.get(s,[]) if day<a['effective_date']<=str(op.date()) and str(a.get('ratio','1')) not in ['1','1.0']]
  if changes:why='corporate_action_lot_quantity_requires_original_lot_record'
  elif op<mature:why='original_shares_not_T1_mature'
  elif win is None:why='original_daily_execution_proxy_unavailable'
  elif win.market_open is not True or win.sell_allowed is not True:why='market_or_sell_not_allowed'
  else:
   submitted=win.quantity.sell_floor(q,q);quantity=min(submitted,q,win.capacity_shares)//win.quantity.fill_step*win.quantity.fill_step
   if quantity<=0:why='quantity_or_capacity_unavailable'
   else:base.update(next_legal_execution=str(op),proxy_quantity=quantity,full_quantity_proxy=quantity==q,execution_status='original_daily_proxy_available');base['execution_checks'].append(dict(at=str(op),reason='available',capacity=win.capacity_shares,T1_mature=True));return base
  base['execution_checks'].append(dict(at=str(op),reason=why))
 base['execution_status']='no_identified_executable_window_before_original_exit';return base

for rr in cases.itertuples(index=False):
 cid=rr.cycle_id;s=rr.old;c=ac.loc[cid];g=paths[paths.cycle_id.eq(cid)].sort_values('day');eg=ex[ex.cycle_id.eq(cid)].set_index('date');first=None if pd.isna(rr.date) else rr.date;unknown=list(eg.index[eg.event.isna()]);unknown_before=[d for d in unknown if first and d<first]
 observable=eg[eg.old_signal];assert (None if observable.empty else observable.index.min())==first
 P=sigma=B=None;sigma_status='no_known_warning';warning_floor=None;kernel_meta={}
 if first:
  f=history[s];assert pd.Timestamp(first) in f.index;fr=f.loc[first];P=float(fr.close);warning_floor=float(g[g.day.eq(first)].iloc[0].old_floor_causal);ss=scales[s];sigma=float(ss.loc[pd.Timestamp(first)]) if pd.Timestamp(first) in ss.index else math.nan
  seg=int(fr.segment_id);b=bars[s][seg];d=b[b.gt(0).all(axis=1)&np.isfinite(b).all(axis=1)];j=d.index.get_loc(pd.Timestamp(first));returns=[math.nan]+[E.log_ratio(float(d.close.iloc[k]),float(d.close.iloc[k-1])) for k in range(1,len(d))]
  if j>=64 and math.isfinite(sigma):
   manual=max(math.sqrt(math.fsum(x*x for x in returns[j-63:j])/63),1e-8);assert sigma==manual;checks['warning_sigma_manual_exact']+=1
   _,prefix_sigma=original_with_sigma(b.loc[:first]);assert float(prefix_sigma.loc[pd.Timestamp(first)])==sigma;checks['warning_sigma_physical_prefix_exact']+=1;sigma_status='original_kernel_RMS63_exact';B=P*math.exp(-math.sqrt(5)*sigma)
   kernel_meta=dict(valid_event_index=j,prior_return_dates=[str(d.index[j-63].date()),str(d.index[j-1].date())],tau_return_excluded=True)
  else:sigma_status='unknown_original_preparation_or_scale';sigma=None
 st=BoundaryState(float(c.initial_floor_causal));trigger=None;handoff=None;behavior_unknown=[];warn_observed=False
 for r in g.itertuples(index=False):
  day=r.day;er=eg.loc[day];f=history[s];native=bool(pd.Timestamp(day) in f.index);price=float(r.causal_close) if native else None
  if native:assert price==float(f.loc[pd.Timestamp(day),'close']);checks['causal_close_exact']+=1
  assert st.e0_floor==float(r.old_floor_causal),(cid,day,'original floor state mismatch');checks['original_floor_steps_exact']+=1
  original_exit=(day==c.exit_request[:10]) or not bool(r.ACT_on) or not bool(r.I_active)
  known_event=pd.notna(er.event);event=int(er.event) if known_event else 0
  if event==-1 and not st.warning_seen and not bool(er.old_signal):event=0
  if event==-1 and not st.warning_seen:assert first==day;warn_observed=True
  newfloor=float(r.new_floor_causal) if pd.notna(r.new_floor_causal) else None;update=newfloor if newfloor is not None and newfloor!=st.e0_floor and not original_exit else None
  if update is not None and (not known_event or event!=1):behavior_unknown.append(day+':floor_update_event_identity_unknown');break
  state=st.step(close=price,event=event,sigma=sigma if day==first else None,updated_e0_floor=update,original_exit=original_exit)
  state.update(cycle_id=cid,day=day,native_close_known=native,event_known=known_event,event_observed=None if not known_event else int(er.event),raw_old_signal=bool(er.old_signal));trace.append(state)
  if st.handed_off and handoff is None:handoff=day
  if st.exit_locked:
   if st.exit_reason=='warning_boundary':trigger=day
   break
 assert not first or warn_observed or behavior_unknown,(cid,'first warning not consumed')
 trigrow=g[g.day.eq(trigger)].iloc[0] if trigger else None;cost_return=None;pnl=None;dd=None;pk=None;execution_info={}
 if trigger:
  past=g[g.day.le(trigger)];peak_return=max(0.,float(past.net_liquidation_return.max()));cost_return=float(trigrow.net_liquidation_return);pnl=float(trigrow.net_liquidation_pnl);dd=(1+cost_return)/(1+peak_return)-1;pk=peak_return
  execution_info=next_execution(s,c,trigger,int(trigrow.shares));execution.append(dict(cycle_id=cid,trigger=trigger,**execution_info))
 firstlevels={str(n):next(iter(g.loc[g.net_liquidation_return.le(-n/100),'day']),None) for n in [10,20,30]}
 reason='新增边界触发' if trigger else '记录/状态未知，停止相应判定' if behavior_unknown else '无已知合规负警报，新增层未启用' if not first else '原floor安全接管；无独占新增退出' if handoff else '截至原退出未穿新增边界，原退出优先'
 result=dict(cycle_id=cid,symbol=s,name=rr.name,role=rr.role,entry=c.entry_at,first_known_warning=first,P=P,sigma=sigma,sigma_status=sigma_status,B=B,warning_old_floor=warning_floor,new_trigger=trigger,trigger_cost_net_liquidation_return=cost_return,trigger_cost_net_liquidation_pnl=pnl,known_peak_net_liquidation_return=pk,trigger_drawdown_from_known_peak=dd,next_market_open=execution_info.get('next_market_open'),next_legal_execution=execution_info.get('next_legal_execution'),execution_status=execution_info.get('execution_status'),proxy_quantity=execution_info.get('proxy_quantity'),full_quantity_proxy=execution_info.get('full_quantity_proxy'),original_exit_request=c.exit_request,original_exit=c.exit_at,earlier_decision=bool(trigger and trigger<c.exit_request[:10]),earlier_executable=bool(execution_info.get('next_legal_execution') and execution_info['next_legal_execution']<c.exit_at),handoff=handoff,handoff_before_original_exit=bool(handoff and handoff<c.exit_request[:10]),unknown_event_days=json.dumps(unknown),unknown_before_first=json.dumps(unknown_before),behavior_unknown=json.dumps(behavior_unknown),**{'first_minus'+n:day for n,day in firstlevels.items()},**{'trigger_before_minus'+n:(None if not trigger or not day else trigger<day) for n,day in firstlevels.items()},reason=reason,kernel_meta=json.dumps(kernel_meta))
 out.append(result);print(json.dumps(dict(case=cid,warning=first,trigger=trigger,handoff=handoff,status=reason),ensure_ascii=False),flush=True)
pd.DataFrame(out).to_csv(O/'RESULTS.csv',index=False);pd.DataFrame(trace).to_csv(O/'STATE_TRACE.csv',index=False);save(O/'EXECUTION_CHECKS.json',execution)
assert all(sha(p)==h for p,h in ident.items());assert all(sha(p)==h for p,h in freeze['sha256'].items())
save(O/'VERIFICATION.json',dict(passed=True,cases=len(cases),stocks=len(ids),warnings=sum(x['first_known_warning'] is not None for x in out),new_trigger_cases=sum(x['new_trigger'] is not None for x in out),handoff_cases=sum(x['handoff'] is not None for x in out),unknown_cases=sum(bool(json.loads(x['behavior_unknown'])) for x in out),cases_with_missing_prior_events=sum(bool(json.loads(x['unknown_before_first'])) for x in out),checks=checks,original_sigma_formula='max(sqrt(fsum(previous63 valid C/V log returns squared)/63),1e-8); excludes tau',sigma_from_unmodified_original_kernel=True,original_sigma_only_selected_stocks=True,parameter_changes=0,new_economic_ledgers=0,combination_replays=0,source_hashes_unchanged=True,load_seconds=wall_load,total_seconds=time.monotonic()-T))
print(json.dumps(dict(stage='completed',seconds=time.monotonic()-T,checks=checks),ensure_ascii=False))
