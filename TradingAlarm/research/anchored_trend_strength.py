"""Anchored sequential experts; experimental relative weights, not calibrated probabilities."""
import numpy as np
import pandas as pd
from geometric_strength import fit_endpoint

def anchored_strength_frame(price,volume,neutral=False):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.price.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)]
    n=3 if neutral else 2;weights=np.ones(n)/n;pred=None;variance=None;rows=np.full((len(f),4),np.nan)
    for i in range(21,len(f)):
        if pred is not None:
            prior=(1-1/21)*weights+1/(21*n)
            logw=np.log(prior)-.5*(y[i]-pred)**2/max(variance,1e-12)
            weights=np.exp(logw-logw.max());weights/=weights.sum()
        window=y[i-20:i+1];vol=v[i-20:i+1]
        linear,_=fit_endpoint(window,vol,degree=1);quad,acc=fit_endpoint(window,vol,degree=2)
        velocities=np.array([linear,quad]+([0.] if neutral else []))
        pred=y[i]+np.array([linear,quad+.5*acc]+([0.] if neutral else []))
        scale=np.sqrt(np.mean(r[i-20:i+1]**2));variance=scale**2
        score=5+5*np.tanh(np.sqrt(5)*float(weights@velocities)/scale) if scale>1e-12 else 5.
        rows[i]=[score,weights[0],weights[1],weights[2] if neutral else 0.]
    return pd.DataFrame(rows,index=f.index,columns=['strength','linear_weight','quadratic_weight','neutral_weight']).reindex(price.index)
