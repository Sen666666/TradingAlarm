"""One frozen bounded body-pressure substitution. No policy or economics."""
import numpy as np
import pandas as pd
def candidate_score(f, original_score):
    old = original_score(f)
    z = old.copy()
    open_ok = f.open.gt(0) & np.isfinite(f.open)
    d = np.log(f.close / f.open).where(open_ok)
    n = np.log(f.open / f.close.shift()).where(open_ok & old.r.notna())
    q = old.r / old.scale
    v = np.tanh(d / old.scale)
    new = np.tanh(q + .5 * old.b * v)
    link = np.tanh(q + .5 * old.b * np.tanh(q))
    weights = .9 ** np.arange(20, -1, -1)
    weights /= weights.sum()
    # old.r/scale are NaN at original invalid/reset/warmup rows, so new
    # cannot bridge them. Missing open adds UNKNOWN, never an invented bar.
    En = new.rolling(21, min_periods=21).apply(lambda x: np.dot(weights, x), raw=True)
    z["n"] = n
    z["d"] = d
    z["q"] = q
    z["v"] = v
    z["open_known"] = open_ok
    z["e_new"] = new
    z["e_link"] = link
    z["amount_new_minus_price"] = new - old.u
    z["compression_bridge_delta"] = link - old.e
    z["body_information_delta"] = new - link
    z["E_new"] = En
    z["score_new"] = 50 + 50 * np.tanh(2 * En)
    return z
