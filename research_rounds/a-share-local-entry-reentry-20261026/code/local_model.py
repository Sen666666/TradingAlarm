"""Pure OHLCV local receipts; frozen E0 remains an external background."""
import math
import numpy as np
import pandas as pd

def receipts(f):
 n=len(f);c=f.close.to_numpy(float);h=f.high.to_numpy(float);l=f.low.to_numpy(float);v=f.volume.to_numpy(float);seg=f.segment_id.to_numpy();e0=f.e0_target.to_numpy(bool);ready=f.e0_ready.to_numpy(bool)
 out=pd.DataFrame(index=f.index)
 out['receipt']=False;out['anchor_pos']=-1;out['local_floor']=np.nan;out['credit']=np.nan;out['sigma_anchor']=np.nan;out['volume_baseline']=np.nan;out['amplifier']=np.nan;out['rest']=False
 for _,positions in f.groupby('segment_id',sort=False).indices.items():
  p=np.asarray(positions);cc=c[p];vv=v[p];r=pd.Series(np.r_[np.nan,np.diff(np.log(cc))]);sig=np.sqrt(r.pow(2).shift().rolling(63,min_periods=63).mean()).clip(lower=1e-8).to_numpy();vol=pd.Series(vv).shift().rolling(21,min_periods=21).median().to_numpy()
  for k in range(4,len(p)):
   t=p[k]
   if not ready[t] or not e0[t]:continue
   rest=bool(np.any(cc[k-3:k]<=cc[k-4:k-1]));out.iat[t,out.columns.get_loc('rest')]=rest
   if not rest:continue
   j=k-3+int(np.argmin(cc[k-3:k]));a=p[j]
   if not np.isfinite(sig[j]) or not np.isfinite(vol[j]) or vol[j]<=0:continue
   amp=float(np.clip(math.sqrt(float(vv[j+1:k+1].mean())/vol[j]),.5,2.))
   credit=math.log(cc[k]/cc[j])*amp/sig[j]
   floor=float(l[p[j:k+1]].min())
   for key,value in [('anchor_pos',a),('local_floor',floor),('credit',credit),('sigma_anchor',sig[j]),('volume_baseline',vol[j]),('amplifier',amp)]:out.iat[t,out.columns.get_loc(key)]=value
   if c[t]>h[p[k-1]] and credit>=1:out.iat[t,out.columns.get_loc('receipt')]=True
 out['anchor_day']=[str(f.index[int(p)].date()) if p>=0 else '' for p in out.anchor_pos]
 return out

def shadow(f,r,local_stop=True):
 """Signal-only one-participation sketch, not an executed portfolio."""
 active=False;local=math.nan;segment=None;rows=[]
 for i,(day,x) in enumerate(f.iterrows()):
  entered=exited=False;reason='';handoff=False
  if x.segment_id!=segment:active=False;local=math.nan;segment=x.segment_id
  if active:
   floor=max(float(x.e0_floor),local) if local_stop else float(x.e0_floor)
   if not x.e0_target or float(x.close)<=floor:active=False;exited=True;reason='structure' if not x.e0_target else 'local'
  if not active and not exited and bool(r.receipt.iloc[i]):active=True;entered=True;local=float(r.local_floor.iloc[i])
  floor=max(float(x.e0_floor),local) if active and local_stop else float(x.e0_floor) if active else math.nan
  if active:handoff=bool(float(x.e0_floor)>=local)
  rows.append(dict(target=active,entered=entered,exited=exited,floor=floor,local_at_entry=local if active else math.nan,handoff=handoff,exit_reason=reason))
 return pd.DataFrame(rows,index=f.index)
