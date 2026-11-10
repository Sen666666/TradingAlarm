import json
from pathlib import Path
import numpy as np
import pandas as pd
from pairwise_trend_strength import pairwise_frame
from pair_order_strength import order_frame
from geometric_strength import strength_exposure

def balance_exposure(balance,threshold):
    held=False;previous=None;values=[]
    for x in balance:
        if np.isfinite(x):
            if held and x<=0:held=False
            elif not held and x>=threshold and (previous is None or previous<threshold):held=True
            previous=x
        values.append(float(held))
    return pd.Series(values,index=balance.index,name='exposure')

def reset_signal(close,volume,name):
    if name=='reset_pairwise_volume':
        s=pairwise_frame(close,volume).strength.loc['2022-01-01':]
        exposure=strength_exposure(s)
    else:
        b=order_frame(close,volume).balance.loc['2022-01-01':]
        q=1/np.sqrt(5)
        if name=='calibrated_pair_order_volume':
            q=json.loads((Path(__file__).resolve().parent/'results/strength-calibrated-order/calibration.json').read_text())['threshold']
        exposure=balance_exposure(b,q)
    return exposure.reindex(close.index).fillna(0)
