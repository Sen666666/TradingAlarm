"""Causal adaptive path baseline. Inspired by KAMA, log/volume score is our experiment."""
import numpy as np
import pandas as pd

def path_efficiency_frame(price,volume,joint=False,fixed=False):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.price.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)];rows=np.full((len(f),4),np.nan)
    baseline=None
    for i in range(9,len(f)):
        if baseline is None:baseline=float(y[:10].mean());continue
        changes=r[i-9:i+1];w=np.clip(np.sqrt(v[i-9:i+1]/np.median(v[i-9:i+1])),.25,4) if joint else np.ones(10)
        total=float(np.sum(w*np.abs(changes)));eff=abs(float(w@changes))/total if total>1e-12 else 0.
        alpha=2/22 if fixed else (eff*(2/3-2/31)+2/31)**2
        baseline+=alpha*(y[i]-baseline)
        if i>=21:
            rms=np.sqrt(np.mean(r[i-20:i+1]**2));score=5+5*np.tanh((y[i]-baseline)/rms) if rms>1e-12 else 5.
            rows[i]=[score,baseline,eff,alpha]
    return pd.DataFrame(rows,index=f.index,columns=['strength','log_baseline','efficiency','alpha']).reindex(price.index)
