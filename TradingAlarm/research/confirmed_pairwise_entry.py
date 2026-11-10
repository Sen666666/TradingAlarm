"""Fixed prior-path entry confirmation, no forward labels or parameter search."""
import numpy as np
import pandas as pd
from pairwise_trend_strength import pair_slope, pairwise_frame

def confirmed_exposure(score, prior_velocity):
    upper=5+5*np.tanh(1);held=False;previous=None;result=[]
    for value,prior in zip(score,prior_velocity.reindex(score.index)):
        if np.isfinite(value):
            if held and value<=5:held=False
            elif not held and value>=upper and (previous is None or previous<upper):
                held=bool(np.isfinite(prior) and prior>0)
            previous=value
        result.append(float(held))
    return pd.Series(result,index=score.index,name='exposure')

def confirmed_frame(close,volume):
    frame=pairwise_frame(close,volume)
    obs=pd.concat([close.rename('close'),volume.rename('volume')],axis=1)
    obs=obs.loc[(obs>0).all(axis=1)&np.isfinite(obs).all(axis=1)]
    prior=pd.Series(np.nan,index=obs.index)
    for i in range(21,len(obs)):
        window=obs.iloc[i-20:i-1] # Same 21-close window, final two closes removed.
        prior.iloc[i]=pair_slope(np.log(window.close.to_numpy()),window.volume.to_numpy())
    frame['prior_velocity']=prior.reindex(frame.index)
    frame['target']=confirmed_exposure(frame.strength,frame.prior_velocity)
    return frame
