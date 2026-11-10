"""Causal, account-independent local structures. All constants frozen before money runs."""
import numpy as np,pandas as pd

def compute(f,g,version):
 f=f.reindex(g.index);n=len(f);c=f.close.to_numpy(float);h=f.high.to_numpy(float);l=f.low.to_numpy(float);a=f.amount.to_numpy(float)
 valid=np.isfinite(c+h+l+a)&(l>0)&(a>0)
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).to_numpy(bool)
 seg=g.segment_id.to_numpy();target=g.e0_target.fillna(False).to_numpy(bool);ready=g.g_ready.fillna(False).to_numpy(bool);grade=g.g_grade.to_numpy(float);floor=g.e0_floor.to_numpy(float)
 tr=np.maximum(h-l,np.maximum(abs(h-np.r_[np.nan,c[:-1]]),abs(l-np.r_[np.nan,c[:-1]])))
 atr=pd.Series(tr).shift().rolling(20).mean().to_numpy();ref=pd.Series(a).shift().rolling(21).median().to_numpy()
 out=[];last=-1;start=0
 for t in range(n):
  if not valid[t] or (t and seg[t]!=seg[t-1]):start=t+int(not valid[t]);last=t
  base=dict(event=False,kind='',floor=np.nan,anchor='',atr=atr[t],amount_ratio=a[t]/ref[t] if ref[t]>0 else np.nan)
  if t-start<22 or not valid[t] or not target[t] or not ready[t] or grade[t]<2 or not np.isfinite(floor[t]) or atr[t]<=0:out.append(base);continue
  # Entire 10-bar setup must belong to a surviving E0 up structure.
  if not target[t-10:t+1].all():out.append(base);continue
  ret=c[max(0,t-2):t+1]-c[max(0,t-3):t]
  amounts=a[t-2:t+1];direction=(amounts*(ret>0)).sum()/amounts.sum()
  # Either immediate amount confirmation or three-day positive price/amount recovery.
  impulse=(c[t]>c[t-1] and a[t]>=ref[t]) or (c[t]-c[t-3]>=atr[t] and direction>=.6)
  candidates=[]
  if version in ['PB','BOTH']:
   # Latest occurrence of the highest previous-20 close; never a future pivot.
   lo=t-20;p=lo+len(c[lo:t])-1-np.argmax(c[lo:t][::-1]);age=t-p
   if 3<=age<=15 and p>last and (c[p]-min(l[p+1:t]))>=atr[t] and c[t]>max(h[t-3:t]) and impulse:
    candidates.append(('PB',p,max(floor[t],min(l[p+1:t]))))
  if version in ['BOX','BOTH']:
   s=t-10;high=max(h[s:t]);low=min(l[s:t]);downs=int(np.sum(c[s:t]<c[s-1:t-1]))
   if s>last and high-low<=4*atr[t] and abs(c[t-1]-c[s])<=atr[t] and downs>=3 and c[t]>high and impulse:
    candidates.append(('BOX',s,max(floor[t],low)))
  for kind,anchor,stop in candidates:
   if 0<c[t]-stop<=3*atr[t]:
    base.update(event=True,kind=kind,floor=stop,anchor=str(g.index[anchor].date()));last=t;break
  out.append(base)
 return pd.DataFrame(out,index=g.index,columns=["event","kind","floor","anchor","atr","amount_ratio"]).astype({"event":bool,"kind":object,"floor":float,"anchor":object,"atr":float,"amount_ratio":float})
