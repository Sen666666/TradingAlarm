"""Native state classification: long only when up is uniquely most likely."""
import numpy as np
import pandas as pd

def map_state_exposure(frame):
    weights=frame[['down_weight','neutral_weight','up_weight']]
    valid=np.isfinite(weights).all(axis=1)
    up=weights.up_weight.gt(weights.down_weight)&weights.up_weight.gt(weights.neutral_weight)
    return up.astype(float).where(valid).ffill().fillna(0).rename('exposure')
