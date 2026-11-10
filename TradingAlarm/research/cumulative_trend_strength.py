"""Two capped one-sided likelihood accumulators; descriptive, not probabilities.
CUSUM recursion structure: NIST Dataplot cusum reference. Cap and volume
tempering are research modifications, fixed before outcomes.
"""
import numpy as np
import pandas as pd
MU=1/np.sqrt(5)
CAP=np.log(19)


def accumulate(observations,weights=None):
    x=np.asarray(observations,float);w=np.ones(len(x)) if weights is None else np.asarray(weights,float)
    if len(w)!=len(x):raise ValueError('length mismatch')
    up=down=0.;rows=[]
    for value,weight in zip(x,w):
        if not np.isfinite(value) or not np.isfinite(weight):rows.append([np.nan]*3);continue
        if weight<=0:raise ValueError('weight must be positive')
        up=float(np.clip(up+weight*(MU*value-.5*MU**2),0,CAP))
        down=float(np.clip(down+weight*(-MU*value-.5*MU**2),0,CAP))
        rows.append([5+5*np.tanh(up-down),up,down])
    return pd.DataFrame(rows,columns=['strength','up_evidence','down_evidence'])


def cumulative_frame(price,volume,joint=False):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    r=np.log(f.price).diff();scale=np.sqrt(r.shift().pow(2).rolling(21).mean()).clip(lower=1e-8)
    w=np.sqrt(f.volume/f.volume.shift().rolling(21).median()).clip(.25,4) if joint else None
    result=accumulate((r/scale).to_numpy(),w.to_numpy() if joint else None);result.index=f.index
    return result.reindex(price.index)
