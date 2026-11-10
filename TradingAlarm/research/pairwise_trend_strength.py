"""Causal weighted median pairwise slope; fixed geometry replacement, no fitted thresholds."""
import numpy as np
import pandas as pd

def pair_slope(logprices,volume=None,recency=True):
    y=np.asarray(logprices,float);n=len(y);i,j=np.triu_indices(n,1)
    point=np.exp2(np.arange(1-n,1)/5.) if recency else np.ones(n)
    if volume is not None:
        v=np.asarray(volume,float);point*=np.clip(np.sqrt(v/np.median(v)),.25,4)
    slopes=(y[j]-y[i])/(j-i);weights=point[i]*point[j];order=np.argsort(slopes,kind='stable');s=slopes[order];c=np.cumsum(weights[order]);k=np.searchsorted(c,c[-1]/2)
    # Midpoint at an exact half preserves sign symmetry for tied mass.
    return float((s[k]+s[k+1])/2 if k+1<len(s) and np.isclose(c[k],c[-1]/2,rtol=1e-13,atol=0) else s[k])

def pairwise_frame(close,volume,joint=True,recency=True):
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)];y=np.log(f.close.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)];rows=np.full((len(f),3),np.nan)
    for i in range(21,len(f)):
        slope=pair_slope(y[i-20:i+1],v[i-20:i+1] if joint else None,recency=recency);rms=float(np.sqrt(np.mean(r[i-20:i+1]**2)));score=5+5*np.tanh(np.sqrt(5)*slope/rms) if rms>1e-12 else 5.
        rows[i]=score,slope,rms
    return pd.DataFrame(rows,index=f.index,columns=['strength','velocity','path_rms']).reindex(close.index)
