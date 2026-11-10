"""Single frozen event/risk design; read-only inputs; no account or parameter search."""
from pathlib import Path
import json, hashlib, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality')
ROOT=BASE/'daily_signal_cache_pilot20_v1/full_universe_v1'
OUT=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
PR=BASE/'pvr_contribution_attribution_v1'
H1=OUT.parent/'h1_failure_mechanism_v1'
COL=['day','source_row_present','price__open','price__high','price__low','price__close','price__amount','native__e0_ready','native__g_ready','native__i_target','native__i_buy','pvr__score']
case=pd.concat([pd.read_csv(PR/'EARLY_MISS_FRESH_BREAK_EXAMPLES.csv')[['sid','day']],pd.read_csv(PR/'SUPPORT_BENEFIT_HARM_CASES.csv')[['sid','day']],pd.read_csv(H1/'JAN15_ADDED_REMOVED_EXPLANATION.csv')[['sid']].assign(day='2026-01-15'),pd.read_csv(H1/'ORIGINAL_H1_DAILY_DECOMPOSITION.csv').rename(columns={'symbol':'sid'})[['sid','day']]]).drop_duplicates()
case=case[~case.sid.astype(str).str.startswith('URFI')]
case_days={sid:set(g.day) for sid,g in case.groupby('sid')}
ids=sorted(set(case.sid))
out_rows=[]; event_rows=[]; detail=[]; tech=[]
def evaluate(sid):
 f=pq.read_table(ROOT/'artifacts'/(sid+'.parquet'),columns=COL).to_pandas()
 days=f.day.dt.strftime('%Y-%m-%d').to_numpy();n=len(f)
 C=f.price__close.to_numpy(); O=f.price__open.to_numpy(); H=f.price__high.to_numpy(); L=f.price__low.to_numpy(); A=f.price__amount.to_numpy()
 valid=f.source_row_present.to_numpy()&np.isfinite(C)&(C>0)&np.isfinite(O)&np.isfinite(H)&np.isfinite(L)&np.isfinite(A)&(A>0)
 tr=np.full(n,np.nan); tr[1:]=np.maximum.reduce([H[1:]-L[1:],np.abs(H[1:]-C[:-1]),np.abs(L[1:]-C[:-1])])
 buy=(f.native__e0_ready.eq(1)&f.native__g_ready.eq(True)&f.native__i_target.eq(1)&f.native__i_buy.eq(True)).to_numpy()
 pvr=f.pvr__score.to_numpy()
 live=None; cool=-1; events=[]; rows=[]; lastgood=-1
 for t in range(n):
  day=days[t];candidate=False; new=False;failed=False; why='';r={}
  if not valid[t]:
   if live is not None: live['unknown_at']=t;events.append(live);live=None
   cool=t+5;continue
  if live is not None:
   # Everything used here is known at this close. Test old event before any new birth.
   b=live['B']; a=live['atr']; prev_below=(t>0 and valid[t-1] and C[t-1]<b)
   if C[t]<b-a or (C[t]<b and prev_below) or (C[t]<b and A[t]>=live['Aref'] and t>0 and C[t]<C[t-1]):
    live['failure_at']=t
    live['failure_reason']='hard1ATR' if C[t]<b-a else ('two_below' if prev_below else 'amount_rejection')
    events.append(live);live=None;cool=t+5;failed=True;why='FAIL'
  if live is None and not failed and t>=21 and t>cool and np.all(valid[t-21:t+1]):
   b=float(np.max(C[t-20:t]));a=float(np.mean(tr[t-20:t]));lo=float(np.min(C[t-20:t])); ar=float(np.median(A[t-20:t]))
   if C[t]>b and a>0 and b>lo and b-a>0:
    live=dict(sid=sid,tau=t,tau_day=day,B=b,atr=a,W=b-lo,Aref=ar,A_tau=float(A[t]),C_tau=float(C[t]),state='PROBE',failure_at=None,unknown_at=None,confirm_at=None,first_signal=None,first_open=None,opportunities=[],W_ATR=(b-lo)/a,base_last5_low_vs_prior15=float(np.min(L[t-5:t])/np.min(L[t-20:t-5])-1),base_amount5_vs15=float(np.median(A[t-5:t])/np.median(A[t-20:t-5])),base_signed_amount_share=float(np.sum(A[t-20:t]*np.sign(np.diff(C[t-21:t])))/np.sum(A[t-20:t])))
    new=True
  if live is not None:
   b=live['B'];a=live['atr'];tau=live['tau'];S=b-a;T=b+live['W'];pcap=(T+2*S)/3
   if t>tau and live['state']=='PROBE' and C[t]>b:
    retest=L[t]<=b+.5*a and A[t]<=live['A_tau']
    commitment=C[t]>live['C_tau'] and np.sum(A[tau+1:t+1]*np.sign(np.diff(C[tau:t+1])))>0
    if retest or commitment:live['state']='CONFIRMED';live['confirm_at']=t
   rr=(T-C[t])/(C[t]-S) if C[t]>S else np.nan
   candidate=bool(buy[t] and C[t]>b and C[t]<=pcap and np.isfinite(pvr[t]))
   proxy_ok=bool(candidate and t+1<n and valid[t+1] and S<O[t+1]<=pcap)
   if candidate:
    live['opportunities'].append(t)
    if live['first_signal'] is None:live['first_signal']=t
    if proxy_ok and live['first_open'] is None:live['first_open']=t+1;live['entry_state']=live['state'];live['entry_signal']=t
   why='READY' if candidate else ('not_i_buy' if not buy[t] else ('below_B' if C[t]<=b else 'insufficient_headroom'))
   r=dict(sid=sid,day=day,event_tau=live['tau_day'],age=t-tau,state=live['state'],close=C[t],B=b,ATR=a,S=S,T=T,Pcap=pcap,RR=rr,amount_ratio=A[t]/live['Aref'],i_buy=bool(buy[t]),candidate=candidate,next_open=O[t+1] if t+1<n else np.nan,next_open_pass=proxy_ok,reason=why,W_ATR=live['W_ATR'])
  elif failed:
   e=events[-1];r=dict(sid=sid,day=day,event_tau=e['tau_day'],state='FAIL',close=C[t],B=e['B'],ATR=e['atr'],i_buy=bool(buy[t]),candidate=False,reason=e['failure_reason'])
  else:r=dict(sid=sid,day=day,state='NO_EVENT',close=C[t],i_buy=bool(buy[t]),candidate=False,reason='cooldown' if t<=cool else 'no_new_break')
  if day in case_days[sid]:out_rows.append(r)
  if day>='2023-11-01':detail.append(r)
 if live is not None:events.append(live)
 for e in events:
  tau=e['tau'];x={k:v for k,v in e.items() if k not in ['opportunities']};x['opportunity_count']=len(e['opportunities']);x['left_initialization_excluded']=tau<60;x['year']=int(days[tau][:4]);x['failure_day']=days[e['failure_at']] if e['failure_at'] is not None else None;x['confirm_day']=days[e['confirm_at']] if e['confirm_at'] is not None else None
  ent=e['first_open'];x['entry_day']=days[ent] if ent is not None else None
  # Full common-date paths. No skipping missing dates or last bars.
  for tag,anchor,origin in [('birth',C[tau],tau),('entry',O[ent] if ent is not None else np.nan,ent)]:
   for h in [20,60]:
    ok=origin is not None and origin+h<n and np.all(valid[origin:origin+h+1])
    p=C[origin+1:origin+h+1] if ok else np.array([])
    x[f'{tag}_ret{h}']=float(p[-1]/anchor-1) if ok else np.nan
    x[f'{tag}_mfe{h}']=float(max(0,np.max(p)/anchor-1)) if ok else np.nan
    x[f'{tag}_mae{h}']=float(min(0,np.min(p)/anchor-1)) if ok else np.nan
  if ent is not None:
   end=ent+60; fi=e['failure_at'];ex=fi+1 if fi is not None and fi+1>ent and fi+1<=end else end
   ok=ex<n and np.all(valid[ent:ex+1])
   ep=O[ex] if fi is not None and ex==fi+1 else C[ex] if ex<n else np.nan
   x['failure_proxy_return']=float(ep/O[ent]-1) if ok else np.nan;x['proxy_exit_day']=days[ex] if ok else None;x['proxy_exit_reason']='failure_next_open' if fi is not None and ex==fi+1 else 'terminal60'
   x['entry_gap']=float(O[ent]/C[ent-1]-1);x['entry_flat_ohlc']=bool(O[ent]==H[ent]==L[ent]==C[ent]);x['stop_risk_frac']=float((O[ent]-(e['B']-e['atr']))/O[ent]);x['proxy_loss_R']=min(0,x['failure_proxy_return'])/x['stop_risk_frac'] if ok else np.nan
  event_rows.append(x)
for sid in ids:
 evaluate(sid)
pd.DataFrame(out_rows).to_csv(OUT/'CASE_DATES.csv',index=False)
pd.DataFrame(detail).to_csv(OUT/'CASE_DAILY_PATHS.csv',index=False)
ev=pd.DataFrame(event_rows);ev.to_csv(OUT/'CASE_ALL_EVENTS.csv',index=False)
summary=[]
for y,g in ev[~ev.left_initialization_excluded].groupby('year'):
 q=g[g.entry_day.notna()];big=g.birth_mfe60.ge(.3)&g.birth_ret60.ge(.2);bigq=q.birth_mfe60.ge(.3)&q.birth_ret60.ge(.2)
 summary.append(dict(year=int(y),named_stock_events=len(g),admitted_events=len(q),big_birth_events=int(big.sum()),big_birth_with_entry=int(bigq.sum()),complete_entry60=int(q.entry_ret60.notna().sum()),entry60_mean=q.entry_ret60.mean(),entry60_median=q.entry_ret60.median(),failure_exit_proxy_mean=q.failure_proxy_return.mean(),entry60_mae_mean=q.entry_mae60.mean(),post_failure_later_big=int((q.proxy_exit_reason.eq('failure_next_open')&bigq).sum())))
pd.DataFrame(summary).to_csv(OUT/'NAMED_CASE_ANNUAL_DIAGNOSTIC.csv',index=False)
(OUT/'COMPLETION.json').write_text(json.dumps(dict(status='COMPLETE_BOUNDED_CASE_EXECUTION_NO_WHOLE_MARKET_PERFORMANCE_CLAIM',stocks=len(ids),case_rows=len(out_rows),events=len(ev),account_runs=0,parameter_searches=0,original_signal_reruns=0,source_cache_unmodified=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
print(pd.DataFrame(summary).to_string(index=False))
print('EXPLICIT CASE DATES')
print(pd.DataFrame(out_rows).to_string(index=False))
