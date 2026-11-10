"""Volume-clock pairwise slope ablation; not a fitted stochastic-volatility model."""
import numpy as np
import pandas as pd

def clock_slope(logprices,volume):
 y=np.asarray(logprices,float);v=np.asarray(volume,float);n=len(y)
 if n<2 or len(v)!=n or not np.isfinite(y).all() or not np.isfinite(v).all() or (v<=0).any():raise ValueError('Finite prices and positive volume required')
 scaled=v/v.max()
 if (scaled<=0).any():raise ValueError('Volume dynamic range exceeds numerical precision')
 steps=scaled/scaled.mean();i,j=np.triu_indices(n,1)
 # Direct positive interval sums avoid cancellation of two large cumulative clocks.
 intervals=np.concatenate([np.cumsum(steps[a+1:]) for a in range(n-1)])
 point=np.exp2(np.arange(1-n,1)/5.)*np.clip(np.sqrt(scaled/np.median(scaled)),.25,4)
 slopes=(y[j]-y[i])/intervals;weights=point[i]*point[j];order=np.argsort(slopes,kind='stable');s=slopes[order];c=np.cumsum(weights[order]);k=np.searchsorted(c,c[-1]/2)
 return float((s[k]+s[k+1])/2 if k+1<len(s) and np.isclose(c[k],c[-1]/2,rtol=1e-13,atol=0) else s[k])

def volume_clock_frame(close,volume):
 f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)];y=np.log(f.close.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)];rows=np.full((len(f),3),np.nan)
 for i in range(21,len(f)):
  slope=clock_slope(y[i-20:i+1],v[i-20:i+1]);rms=float(np.sqrt(np.mean(r[i-20:i+1]**2)));score=5+5*np.tanh(np.sqrt(5)*slope/rms) if rms>1e-12 else 5.
  rows[i]=score,slope,rms
 return pd.DataFrame(rows,index=f.index,columns=['strength','velocity','path_rms']).reindex(close.index)
