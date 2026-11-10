"""Causal retained signed price displacement, volume weights; heuristic, not probability."""
import numpy as np
import pandas as pd

def retained_frame(close,volume,joint=True,window=63,half_life=21):
    if not close.index.is_unique or not close.index.is_monotonic_increasing:raise ValueError('Ordered unique index required')
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1)
    valid=(f>0).all(axis=1)&np.isfinite(f).all(axis=1);g=f.loc[valid]
    y=np.log(g.close.to_numpy());r=np.r_[np.nan,np.diff(y)]
    q=(g.volume/g.volume.shift(1).rolling(21).median()).clip(.25,4).to_numpy() if joint else np.ones(len(g))
    rows=np.full((len(g),5),np.nan)
    for t in range(window,len(g)):
        ids=np.arange(t-window+1,t+1);move=r[ids];direction=np.sign(move)
        retained=direction*np.minimum(np.abs(move),np.maximum(0,direction*(y[t]-y[ids-1])))
        weights=np.exp2(-(t-ids)/half_life)*np.sqrt(q[ids])
        if not np.isfinite(weights).all():continue
        sigma=np.sqrt(np.mean(move**2));den=sigma*np.sqrt(np.sum(weights**2))
        positive=np.sum(weights*np.maximum(retained,0));negative=np.sum(weights*np.minimum(retained,0))
        score=(positive+negative)/den if den>1e-12 else 0.
        rows[t]=[score,positive,negative,den,np.sum(weights*np.abs(retained))]
    result=pd.DataFrame(rows,index=g.index,columns=['strength','positive_retained','negative_retained','normalizer','retained_mass']).reindex(close.index)
    return result

def exposure(strength):
    held=False;prev=np.nan;out=[]
    for s in strength:
        if np.isfinite(s):
            if held and s<=0:held=False
            elif not held and s>1 and (not np.isfinite(prev) or prev<=1):held=True
            prev=s
        out.append(float(held))
    return pd.Series(out,index=strength.index,name='target')
