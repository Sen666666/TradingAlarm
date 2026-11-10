import pandas as pd,numpy as np,json,math
from pathlib import Path
manifest={x['symbol']:x for x in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
cases=[('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('688582.SH','2024-07-29'),('000506.SZ','2024-10-15'),('600606.SH','2022-03-22'),('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('601607.SH','2022-03-24'),('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('002317.SZ','2022-10-14'),('002131.SZ','2024-10-24'),('600839.SH','2024-10-18'),('600396.SH','2026-03-16'),('002716.SZ','2026-01-15'),('001896.SZ','2026-02-25'),('000338.SZ','2026-01-15')]
def rsi(a,s,n=14):
 out=np.full(len(a),np.nan);U=D=0;run=0;gains=[];losses=[];last=np.nan;seg=None
 for i,(p,ss) in enumerate(zip(a,s)):
  if ss!=seg or not math.isfinite(p) or p<=0:
   U=D=0;run=0;gains=[];losses=[];last=np.nan;seg=ss
  if not math.isfinite(p) or p<=0:continue
  if math.isfinite(last):
   up=max(p-last,0);dn=max(last-p,0);run+=1
   if run<=n:
    gains.append(up);losses.append(dn)
    if run==n:U=sum(gains)/n;D=sum(losses)/n
   else:U=(n-1)/n*U+up/n;D=(n-1)/n*D+dn/n
   if run>=n:out[i]=100*U/(U+D) if U+D>0 else 50
  last=p
 return out
out=[]
for sid,day in cases:
 f=pd.read_parquet(manifest[sid]['refs']['facts'],columns=['close','segment_id']);a=f.close.to_numpy();s=f.segment_id.to_numpy();z=rsi(a,s)
 loc=f.index.get_loc(pd.Timestamp(day));p=rsi(a[:loc+1],s[:loc+1]);assert np.array_equal(z[:loc+1],p,equal_nan=True)
 cp=pd.read_parquet(manifest[sid]['refs']['CP1'],columns=['r','m']);U=D=0.;prev=None
 for rr,mm,ss in zip(cp.r.iloc[:loc+1],cp.m.iloc[:loc+1],s[:loc+1]):
  if prev is None or prev!=ss:U=D=0.;prev=ss
  if not (np.isfinite(rr) and np.isfinite(mm) and mm>0):U=D=0.;continue
  U=20/21*U+mm*max(rr,0)/21;D=20/21*D+mm*max(-rr,0)/21
 q=100*U/(U+D) if U+D>0 else 50
 out.append(dict(sid=sid,signal_day=day,standard_Wilder_RSI14=z[loc],weighted_log_Q21=q))
print('STANDARD_RSI14_DIAGNOSTIC_ONLY_NO_SECOND_STRATEGY',json.dumps(out),flush=True)
print('EDGE_CHECKS',rsi(np.arange(20,dtype=float)+1,np.zeros(20))[-1],rsi(np.arange(20,0,-1,dtype=float),np.zeros(20))[-1],rsi(np.ones(20),np.zeros(20))[-1])
