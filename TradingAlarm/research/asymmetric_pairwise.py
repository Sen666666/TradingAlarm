"""Uniform-window trend entry and recency-weighted trend exit, fixed thresholds."""
import numpy as np
import pandas as pd
from pairwise_trend_strength import pairwise_frame

def asymmetric_exposure(slow,fast,require_crossing=True):
    upper=5+5*np.tanh(1);held=False;previous=None;values=[]
    for s,f in zip(slow,fast.reindex(slow.index)):
        if np.isfinite(s) and np.isfinite(f):
            if held and f<=5:held=False
            elif not held and f>5 and s>=upper and (not require_crossing or previous is None or previous<upper):held=True
            previous=s
        values.append(float(held))
    return pd.Series(values,index=slow.index,name='exposure')

def asymmetric_frame(close,volume,require_crossing=True):
    slow=pairwise_frame(close,volume,recency=False).strength
    fast=pairwise_frame(close,volume,recency=True).strength
    return pd.DataFrame(dict(slow=slow,fast=fast,target=asymmetric_exposure(slow,fast,require_crossing=require_crossing)))
