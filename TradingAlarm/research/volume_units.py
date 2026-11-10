"""Causal volume expressed in the share units at the beginning of the series."""
import numpy as np
import pandas as pd

def split_consistent_volume(volume,splits):
    if not volume.index.is_unique or not volume.index.is_monotonic_increasing:raise ValueError('ordered unique dates required')
    result=volume.astype(float).copy()
    if result.empty:return result
    for event in splits:
        date=pd.Timestamp(event['date']);ratio=float(event['ratio'])
        if not np.isfinite(ratio) or ratio<=0:raise ValueError('invalid split ratio')
        if date<result.index[0] or date>result.index[-1]:continue
        result.loc[result.index>=date]/=ratio
    return result
