"""Price ordering consistency, not slope magnitude or a significance statistic."""
import numpy as np
import pandas as pd

def order_balance(prices,volume=None):
    y=np.asarray(prices,float);n=len(y);i,j=np.triu_indices(n,1)
    point=np.exp2(np.arange(1-n,1)/5.)
    if volume is not None:
        v=np.asarray(volume,float);point*=np.clip(np.sqrt(v/np.median(v)),.25,4)
    weights=point[i]*point[j]
    return float(np.sum(weights*np.sign(y[j]-y[i]))/weights.sum())

def order_frame(close,volume,joint=True):
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    balance=pd.Series(np.nan,index=f.index)
    # Match baseline warmup even though pair ordering needs only21closes.
    for k in range(21,len(f)):
        w=f.iloc[k-20:k+1]
        balance.iloc[k]=order_balance(w.close.to_numpy(),w.volume.to_numpy() if joint else None)
    return pd.DataFrame(dict(balance=balance,strength=5+5*np.tanh(np.sqrt(5)*balance))).reindex(close.index)
