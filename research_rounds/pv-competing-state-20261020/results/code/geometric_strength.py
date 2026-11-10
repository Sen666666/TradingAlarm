"""Causal endpoint geometry of a price-volume trajectory; no return-trained parameters."""
import numpy as np
import pandas as pd

def strength_exposure(strength,exit_threshold=5.):
    """Frozen hysteresis: upward crossing of unit velocity, exit at zero."""
    threshold=5+5*np.tanh(1)
    held=False;previous=None;values=[]
    for value in strength:
        if np.isfinite(value):
            if held and value<=exit_threshold:held=False
            elif not held and value>=threshold and (previous is None or previous<threshold):held=True
            previous=value
        values.append(float(held))
    return pd.Series(values,index=strength.index,name='exposure')

def fit_endpoint(log_prices,volume=None,degree=2):
    y=np.asarray(log_prices,float);n=len(y);time=np.arange(1-n,1,dtype=float)
    design=np.column_stack([np.ones(n),time,.5*time*time])
    if degree not in (1,2):raise ValueError('degree must be 1 or 2')
    design=design[:,:degree+1]
    weights=np.exp2(time/5)
    if volume is not None:
        v=np.asarray(volume,float)
        weights*=np.clip(np.sqrt(v/np.median(v)),.25,4)
    # Relative levels prevent unit-dependent numerical cancellation.
    beta=np.linalg.lstsq(design*np.sqrt(weights[:,None]),(y-y[-1])*np.sqrt(weights),rcond=None)[0]
    return beta[1],beta[2] if degree==2 else 0.

def geometric_frame(signal_close,raw_close,volume,joint=True,degree=2):
    frame=pd.concat([signal_close.rename('signal'),raw_close.rename('raw'),volume.rename('volume')],axis=1)
    f=frame.loc[(frame>0).all(axis=1)&np.isfinite(frame).all(axis=1)]
    logp=np.log(f.signal.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(logp)]
    rows=np.full((len(f),4),np.nan)
    for i in range(21,len(f)):
        velocity,acceleration=fit_endpoint(logp[i-20:i+1],v[i-20:i+1] if joint else None,degree=degree)
        scale=float(np.sqrt(np.mean(r[i-20:i+1]**2)))
        score=5+5*np.tanh(np.sqrt(5)*velocity/scale) if scale>1e-12 else 5.
        rows[i]=[score,velocity,acceleration,scale]
    return pd.DataFrame(rows,index=f.index,columns=['strength','velocity','acceleration','path_rms']).reindex(frame.index)
