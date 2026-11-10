"""Causal activity-weighted price-region advancement and independent survival.

Daily close locations are proxies, not actual volume-at-price or investor costs.
Market state never reads account holdings, entry prices, or profit.
"""
import numpy as np
import pandas as pd


def quantiles(y, weights):
    order = np.argsort(y, kind="stable")
    x, w = np.asarray(y)[order], np.asarray(weights)[order]
    w = w / w.sum()
    coordinates = np.cumsum(w) - .5 * w
    return np.interp([.25, .50, .75], coordinates, x)


def region_frame(close, volume, joint=True, momentum_exit=False):
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("ordered, unique dates required")
    raw = pd.concat([close.rename("close"), volume.rename("volume")], axis=1)
    valid = raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)
    data = raw.loc[valid]
    if data.empty:
        raise ValueError("no valid observations")
    y = np.log(data.close / data.close.iloc[0])
    offset = float(np.log(data.close.iloc[0]))
    sigma = y.diff().shift(1).pow(2).rolling(63).mean().pow(.5).clip(lower=1e-8)
    weights = np.sqrt(data.volume / data.volume.iloc[0]) if joint else pd.Series(1., index=data.index)
    state, floor, previous = False, np.nan, np.nan
    rows = []
    for i in range(len(data)):
        scale = sigma.iloc[i]
        if i < 41 or not np.isfinite(scale):
            rows.append([np.nan]*9+[0., 0., 0.])
            continue
        old = quantiles(y.iloc[i-41:i-20].to_numpy(), weights.iloc[i-41:i-20].to_numpy())
        new = quantiles(y.iloc[i-20:i+1].to_numpy(), weights.iloc[i-20:i+1].to_numpy())
        advance = float(np.min(new-old)/(scale*np.sqrt(21)))
        noise = float(scale*np.sqrt(5))
        entry_score = min(advance, 1+(float(y.iloc[i])-new[1])/noise)
        candidate_floor = float(new[0]-noise)
        entered, exited = False, False
        if state:
            floor = max(floor, candidate_floor)
            invalidated = advance <= 0 if momentum_exit else y.iloc[i] < floor
            if invalidated:
                state, exited = False, True
        elif entry_score > 1 and (not np.isfinite(previous) or previous <= 1):
            state, entered, floor = True, True, candidate_floor
        previous = entry_score
        rows.append([advance, entry_score, *new, *old, floor if state or exited else np.nan,
                     float(state), float(entered), float(exited)])
    columns = ["advance", "entry_score", "recent_q25", "recent_q50", "recent_q75",
               "prior_q25", "prior_q50", "prior_q75", "structure_floor",
               "target", "entered", "exited"]
    result = pd.DataFrame(rows, index=data.index, columns=columns).reindex(close.index)
    for col in columns[2:9]:
        result[col] += offset
    # Non-observations cannot create a transition; retain prior market state.
    result["target"] = result.target.ffill().fillna(0.)
    result["entered"] = result.entered.fillna(0.)
    result["exited"] = result.exited.fillna(0.)
    return result
