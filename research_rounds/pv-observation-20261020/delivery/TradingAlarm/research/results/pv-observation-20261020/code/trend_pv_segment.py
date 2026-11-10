"""Causal persistent, volume-weighted segment fitting. A heuristic, not a probability."""
import numpy as np
import pandas as pd


def _moments_fit(y, w):
    x = np.arange(len(y), dtype=float)
    sums = np.cumsum(np.array([w, w*x, w*y, w*x*x, w*x*y, w*y*y]), axis=1)
    def solve(m):
        sw, sx, sy, sxx, sxy, syy = m
        denom = np.maximum(sxx-sx*sx/sw, 1e-15)
        slope = (sxy-sx*sy/sw)/denom
        intercept = (sy-slope*sx)/sw
        sse = np.maximum(syy-intercept*sy-slope*sxy, 0.)
        return slope, sse
    return sums, solve


def segment_frame(close, volume, joint=True, penalty=1., volume_lag=0):
    """Prior observations never change. Last accepted boundary is market memory only."""
    f = pd.concat([close.rename('close'), volume.rename('volume')], axis=1)
    valid = (f > 0).all(axis=1) & np.isfinite(f).all(axis=1)
    g = f[valid]
    y = np.log(g.close.to_numpy(dtype=float))
    returns = pd.Series(np.r_[np.nan, np.diff(y)], index=g.index)
    scale = returns.shift(1).rolling(21).apply(lambda a: np.sqrt(np.mean(a*a)), raw=True).to_numpy()
    relative = (g.volume / g.volume.shift(1).rolling(21).median()).shift(volume_lag)
    weights = np.sqrt(relative).clip(.25, 4).fillna(1.).to_numpy() if joint else np.ones(len(g))
    rows = np.full((len(g), 7), np.nan)
    anchor = 0
    for i in range(63, len(g)):
        start = max(anchor, i-62)
        yy = y[start:i+1]-y[i]
        w = weights[start:i+1].copy(); w /= w.mean()
        n = len(yy)
        sums, solve = _moments_fit(yy, w)
        slope, sse = solve(sums[:, -1])
        gain = 0.; did_reset = 0.
        if n >= 16 and scale[i] > 1e-12:
            cuts = np.arange(8, n-7)
            _, left_sse = solve(sums[:, cuts-1])
            right_slope, right_sse = solve(sums[:, -1, None]-sums[:, cuts-1])
            gains = (sse-left_sse-right_sse)/(scale[i]**2)-penalty*3*np.log(n)
            best = int(np.argmax(gains)); gain = float(gains[best])
            if gain > 0:
                anchor = start+int(cuts[best]); start = anchor
                slope = float(right_slope[best]); did_reset = 1.
        z = np.sqrt(21)*slope/scale[i] if scale[i] > 1e-12 else 0.
        rows[i] = [z, slope, scale[i], start, i-start+1, gain, did_reset]
    out = pd.DataFrame(rows, index=g.index, columns=['strength','slope','prior_rms','segment_start_pos','segment_length','break_gain','reset'])
    out['relative_volume_weight'] = weights
    return out.reindex(f.index)


def exposure(strength):
    held = False; previous = None; values = []
    for value in strength:
        if np.isfinite(value):
            if held and value <= 0: held = False
            elif not held and value >= 1 and (previous is None or previous < 1): held = True
            previous = value
        values.append(float(held))
    return pd.Series(values, index=strength.index, name='target')
