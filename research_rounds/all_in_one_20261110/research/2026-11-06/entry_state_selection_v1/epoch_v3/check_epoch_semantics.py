"""E3 causal state semantics only. No ranking or economic rerun."""
from pathlib import Path
import numpy as np,pandas as pd,json
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'epoch_v3';D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
c=pd.read_csv(R/'CASE_DATES.csv');ids=sorted(c.sid.unique());keys=set(zip(c.sid,c.day))
allrows=[];changes=[];stats=[]
def run(sid,stop=None):
 f=pd.read_parquet(D/(sid+'.parquet'),columns=['day','price__close','price__high','price__low','price__amount','native__i_entered','native__i_exited','native__i_target','native__i_buy','source_row_present'])
 if stop is not None:f=f[f.day<=pd.Timestamp(stop)].copy()
 C=f.price__close.to_numpy();H=f.price__high.to_numpy();L=f.price__low.to_numpy();A=f.price__amount.to_numpy();day=f.day.dt.strftime('%Y-%m-%d').to_numpy();n=len(f)
 valid=f.source_row_present.to_numpy()&np.isfinite(C)&np.isfinite(H)&np.isfinite(L)&np.isfinite(A)&(C>0)&(A>0)
 tr=np.full(n,np.nan);tr[1:]=np.maximum.reduce([H[1:]-L[1:],abs(H[1:]-C[:-1]),abs(L[1:]-C[:-1])])
 atr=pd.Series(tr).shift().rolling(20,min_periods=20).mean().to_numpy();amt=pd.Series(A).shift().rolling(20,min_periods=20).median().to_numpy()
 entered=f.native__i_entered.eq(1).to_numpy();target=f.native__i_target.eq(1).to_numpy();ibuy=f.native__i_buy.eq(True).to_numpy()
 root=None;local=None;state='UNKNOWN';setup=None;piv=[];rows=[];resets=0;usedbase=None;localnum=0
 def make(t,kind,b,s,a):
  return dict(tau=t,kind=kind,B=float(b),S=float(s),atr=float(a),Aref=float(amt[t]),peak=float(C[t]),break_tau=t if C[t]>b else None,break_C=float(C[t])if C[t]>b else None,confirmed=False)
 for t in range(n):
  transition=''
  if not valid[t]:root=None;local=None;setup=None;piv=[];state='UNKNOWN'
  elif not target[t]:
   root=None;local=None;setup=None;piv=[];state='I_INACTIVE'
  elif t>=21 and np.all(valid[t-21:t+1]):
   if entered[t]:
    root=t;resets+=1;localnum+=1;setup=None;piv=[];usedbase=None
    b=max(C[t-20:t]);local=make(t,'I_NEW',b,min(L[t-5:t])-.25*atr[t],atr[t]);state='PREBREAK'if local['break_tau']is None else 'FIRST_BREAK';transition='I_ENTER_RESET'
   elif root is not None and local is not None:
    k=t-2
    if k>=root+2 and L[k]<min(L[k-2:k])and L[k]<=min(L[k+1:k+3]):piv.append(k)
    # Old local invalidation is tested at every active/wait state before new transitions.
    broken=C[t]<local['S'] or (local['break_tau']is not None and C[t]<local['B']and A[t]>=local['Aref']and C[t]<C[t-1])
    if state!='REPAIR_WAIT' and broken:
     state='REPAIR_WAIT';setup=dict(start=t,Hfail=H[t],trough=L[t],atr=atr[t]);transition='LOCAL_FAIL'
    elif state=='REPAIR_WAIT':
     setup['trough']=min(setup['trough'],L[t]);base=None
     if len(piv)>=2:
      k1,k2=piv[-2:]
      if L[k2]>L[k1]and usedbase!=(k1,k2):
       b=max(H[k1:k2+1])
       if C[t]>b:base=(k1,k2,b)
     if base is not None:
      k1,k2,b=base;usedbase=(k1,k2);local=make(t,'NEW_BASE',b,L[k2]-.25*atr[t],atr[t]);state='FIRST_BREAK';setup=None;localnum+=1;transition='INDEPENDENT_NEW_BASE'
     elif t>setup['start']and C[t]>max(setup['Hfail'],max(C[t-2:t])):
      b=max(setup['Hfail'],max(C[t-2:t]));local=make(t,'RECLAIM',b,setup['trough']-.25*setup['atr'],setup['atr']);state='FIRST_BREAK';setup=None;localnum+=1;transition='PRESSURE_RECLAIM'
    elif state=='PREBREAK':
     if C[t]>local['B']:
      local['break_tau']=t;local['break_C']=float(C[t]);local['peak']=float(C[t]);state='FIRST_BREAK';transition='FIRST_BREAK'
    elif state=='PULLBACK_WAIT':
     setup['trough']=min(setup['trough'],L[t])
     if t>setup['start']and C[t]>max(C[t-2:t]):
      b=max(C[t-2:t]);local=make(t,'PULLBACK',b,setup['trough']-.25*setup['atr'],setup['atr']);state='FIRST_BREAK';setup=None;localnum+=1;transition='PULLBACK_RESTART'
    else:
     local['peak']=max(local['peak'],C[t])
     if C[t]<=local['peak']-local['atr']:
      state='PULLBACK_WAIT';setup=dict(start=t,trough=L[t],atr=atr[t]);transition='PULLBACK_START'
    if state in ['FIRST_BREAK','CONFIRMED']and local['break_tau']is not None and t>local['break_tau']and C[t]>local['B']and C[t]>local['break_C']:
     q=local['break_tau']
     if np.sum(A[q+1:t+1]*np.sign(np.diff(C[q:t+1])))>0:local['confirmed']=True;state='CONFIRMED'
  ready=bool(root is not None and ibuy[t]and state in ['PREBREAK','FIRST_BREAK','CONFIRMED'])
  r=dict(sid=sid,day=day[t],I_entered=bool(entered[t]),I_active=bool(target[t]),i_buy=bool(ibuy[t]),root_day=day[root]if root is not None else None,state=state,kind=local['kind']if local else None,local_tau=day[local['tau']]if local else None,first_break_day=day[local['break_tau']]if local and local['break_tau']is not None else None,B=local['B']if local else None,S=local['S']if local else None,atr=local['atr']if local else None,close=C[t],research_candidate=ready,transition=transition,local_events_in_path=localnum,I_resets_in_path=resets)
  rows.append(r)
 return rows
for sid in ids:
 rows=run(sid);allrows.extend(rows);changes.extend(r for r in rows if r['transition']);stats.append(dict(sid=sid,I_resets=rows[-1]['I_resets_in_path'],local_events=rows[-1]['local_events_in_path']))
pd.DataFrame(allrows).to_csv(O/'DAILY_STATES.csv',index=False)
pd.DataFrame([r for r in allrows if(r['sid'],r['day'])in keys]).to_csv(O/'KNOWN_CASE_DAYS.csv',index=False)
pd.DataFrame(changes).to_csv(O/'EVENT_TRANSITIONS.csv',index=False)
pd.DataFrame(stats).to_csv(O/'RESET_COUNTS.csv',index=False)
checks=[]
for sid in ['300085.SZ','300666.SZ','301252.SZ','002889.SZ']:
 full=[r for r in allrows if r['sid']==sid]
 for cut in ['2024-02-23','2024-03-19','2024-09-19','2026-01-15']:
  part=run(sid,cut);old=[r for r in full if r['day']<=cut]
  # CSV/NaN identity is normalized for a complete prefix comparison.
  a=pd.DataFrame(part);b=pd.DataFrame(old);checks.append(dict(sid=sid,cutoff=cut,rows=len(part),equal=a.equals(b)))
pd.DataFrame(checks).to_csv(O/'PREFIX_CHECKS.csv',index=False)
print(pd.DataFrame(checks).to_string(index=False));print(pd.DataFrame([r for r in allrows if(r['sid'],r['day'])in keys and r['day']in ['2024-01-19','2024-02-23','2024-03-19','2024-09-19','2024-09-20','2026-01-05','2026-01-15']]).to_string(index=False))
(O/'COMPLETION.json').write_text(json.dumps(dict(status='COMPLETE_BOUNDED_SEMANTICS_ONLY_NOT_ECONOMIC_VALIDATION',stocks=len(ids),daily_rows=len(allrows),prefix_checks=len(checks),prefix_pass=all(r['equal']for r in checks),account_runs=0,rankings_run=0,parameter_searches=0),indent=2))
