"""Causal one-knot price-path fit with fixed complexity penalty; no significance claim."""
import numpy as np
import pandas as pd

def segment_fit(y,volume=None):
    y=np.asarray(y,float);n=len(y);x=np.arange(n,dtype=float);y=y-y[-1]
    w=np.ones(n) if volume is None else np.clip(np.sqrt(np.asarray(volume,float)/np.median(volume)),.25,4)
    scale=max(float(np.mean(np.diff(y)**2)),1e-24);floor=max(scale*1e-12,1e-24)
    candidates=[(None,np.column_stack([np.ones(n),x]),2)]
    # At least five observations on each side, sharing the knot observation.
    candidates += [(k,np.column_stack([np.ones(n),x,np.maximum(x-k,0)]),4) for k in range(4,n-4)]
    best=None
    for knot,design,complexity in candidates:
        beta=np.linalg.lstsq(design*np.sqrt(w[:,None]),y*np.sqrt(w),rcond=None)[0]
        mse=float(np.sum(w*(y-design@beta)**2)/w.sum())
        criterion=n*np.log(max(mse,floor))+complexity*np.log(n)
        if best is None or criterion<best[0]:best=(criterion,knot,beta,mse)
    _,knot,beta,mse=best
    return dict(velocity=float(beta[1]+(beta[2] if knot is not None else 0)),knot=-1 if knot is None else knot,mse=mse)

def segmented_frame(close,volume,joint=True):
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.close.to_numpy());v=f.volume.to_numpy();returns=np.r_[np.nan,np.diff(y)];rows=np.full((len(f),4),np.nan)
    for i in range(21,len(f)):
        fit=segment_fit(y[i-20:i+1],v[i-20:i+1] if joint else None);rms=float(np.sqrt(np.mean(returns[i-20:i+1]**2)))
        score=5+5*np.tanh(np.sqrt(5)*fit['velocity']/rms) if rms>1e-12 else 5.
        rows[i]=[score,fit['velocity'],fit['knot'],rms]
    return pd.DataFrame(rows,index=f.index,columns=['strength','velocity','knot','rms']).reindex(close.index)
