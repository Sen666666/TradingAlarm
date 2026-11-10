"""Online run-length mixture with explicit neutral drift, no hindsight smoothing."""
import numpy as np
import pandas as pd
from trend_strength_model import ndtr,logsumexp

def neutral_regimes(observations,hazard=1/21):
    x=np.asarray(observations,float)
    if x.ndim==1:x=x[:,None]
    if x.ndim!=2 or x.shape[1] not in (1,2):raise ValueError('price and optional activity only')
    if not 0<hazard<1:raise ValueError('invalid hazard')
    counts=np.empty(0);sums=np.empty((0,x.shape[1]));lw=np.empty((0,2));rows=[]
    for y in x:
        if not np.isfinite(y).all():rows.append([np.nan]*8);continue
        n=np.r_[0.,counts];total=np.vstack([np.zeros(x.shape[1]),sums])
        prior=np.vstack([np.full(2,np.log(hazard*.5)),np.log1p(-hazard)+lw]) if len(counts) else np.full((1,2),np.log(.5))
        mean=total/(1+n[:,None]);variance=1+1/(1+n)
        spike=-.5*(np.log(2*np.pi)+y[0]**2)*np.ones(len(n))
        slab=-.5*(np.log(2*np.pi*variance)+(y[0]-mean[:,0])**2/variance)
        like=np.column_stack([spike,slab])
        if x.shape[1]==2:
            activity=-.5*(np.log(2*np.pi*variance)+(y[1]-mean[:,1])**2/variance)
            like+=activity[:,None]
        lw=prior+like;lw-=logsumexp(lw.ravel());weights=np.exp(lw)
        counts=n+1;sums=total+y
        p_up=ndtr(sums[:,0]/np.sqrt(1+counts));up=float(weights[:,1]@p_up);down=float(weights[:,1]@(1-p_up));neutral=float(weights[:,0].sum())
        drift=float(weights[:,1]@(sums[:,0]/(1+counts)))
        rows.append([5+5*(up-down),neutral,up,down,float(weights[0].sum()),float(weights.sum(axis=1)@counts),drift,10*up])
    return pd.DataFrame(rows,columns=['strength','neutral_probability','up_probability','down_probability','reset_probability','expected_run','drift','bullish_strength'])

def neutral_frame(signal_close,raw_close,volume,joint=True):
    frame=pd.concat([signal_close.rename('signal'),raw_close.rename('raw'),volume.rename('volume')],axis=1)
    f=frame.loc[(frame>0).all(axis=1)&np.isfinite(frame).all(axis=1)]
    returns=np.log(f.signal).diff();scale=returns.shift().rolling(21).std(ddof=1).clip(lower=1e-8)
    price=returns/scale;activity=np.log(f.raw*f.volume);prior=activity.shift()
    activity=(activity-prior.rolling(21).mean())/prior.rolling(21).std(ddof=1).clip(lower=1e-8)
    features=pd.concat([price,activity],axis=1) if joint else price.to_frame()
    result=neutral_regimes(features.to_numpy());result.index=f.index
    return result.reindex(frame.index)
