"""Pure current-CLOSE confirmation flags; no I/O, trading or account mutation."""
import numpy as np
import pandas as pd

PARAMS = dict(ma=60, ma_lag=5, bb=20, bb_k=2.0, bb_ddof=0,
              ema_span=10, ema_lag=3, ema_adjust=False, ema_min_periods=10,
              weak_multiplier=0.5, strong_multiplier=1.0,
              bb_rule='fresh_cross', coordinate_rtol=1e-10,
              coordinate_atol=1e-10)


def compute_flags(frame, *, price_observed, debug=False):
    """Use the supplied native observation index, preserving every input slot.

    price_observed must be explicit, aligned, and derived from original
    price_eligible & observed_bar & ~synthetic_event_bar evidence. No ffill,
    market-calendar reindex, dropna compression or holding-derived segment.
    Unknown values break feature continuity; the next valid run rewarms.
    """
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert price_observed.index.equals(frame.index)
    for col in ['close', 'segment_id', 'raw_close', 'factor']:
        assert col in frame
    n = len(frame)
    c = pd.to_numeric(frame.close, errors='coerce').to_numpy(float)
    raw = pd.to_numeric(frame.raw_close, errors='coerce').to_numpy(float)
    fac = pd.to_numeric(frame.factor, errors='coerce').to_numpy(float)
    seg = frame.segment_id.to_numpy()
    obs = price_observed.fillna(False).to_numpy(bool)
    valid = (obs & np.isfinite(c) & (c > 0) & np.isfinite(raw) & (raw > 0)
             & np.isfinite(fac) & (fac > 0) & pd.notna(seg)
             & np.isclose(c, raw * fac, rtol=PARAMS['coordinate_rtol'],
                          atol=PARAMS['coordinate_atol']))
    ak = np.zeros(n, bool); bk = np.zeros(n, bool)
    av = np.zeros(n, bool); bv = np.zeros(n, bool)
    dbg = {k: np.full(n, np.nan) for k in ['MA60', 'MA60_lag5', 'BB_upper',
                                           'EMA10', 'EMA10_lag3']}
    i = 0
    while i < n:
        if not valid[i]:
            i += 1
            continue
        j = i + 1
        while j < n and valid[j] and seg[j] == seg[i]:
            j += 1
        s = pd.Series(c[i:j])
        ma = s.rolling(60, min_periods=60).mean(); ml = ma.shift(5)
        mid = s.rolling(20, min_periods=20).mean()
        upper = mid + 2.0 * s.rolling(20, min_periods=20).std(ddof=0)
        ema = s.ewm(span=10, adjust=False, min_periods=10).mean()
        el = ema.shift(3)
        a_known = ma.notna() & ml.notna()
        b_known = upper.notna() & upper.shift().notna() & ema.notna() & el.notna()
        ak[i:j] = a_known; bk[i:j] = b_known
        av[i:j] = (s >= ma) & (ma > ml) & a_known
        bv[i:j] = ((s > upper) & (s.shift() <= upper.shift())
                    & (ema > el) & b_known)
        if debug:
            for k, v in [('MA60', ma), ('MA60_lag5', ml), ('BB_upper', upper),
                         ('EMA10', ema), ('EMA10_lag3', el)]:
                dbg[k][i:j] = v
        i = j
    a = pd.array(av, dtype='boolean'); a[~ak] = pd.NA
    b = pd.array(bv, dtype='boolean'); b[~bk] = pd.NA
    out = pd.DataFrame(dict(price_known=valid, A_known=ak, B_known=bk,
                            A=a, B=b, m_A_ONLY=np.where(av, 1.0, 0.5),
                            m_A_OR_B=np.where(av | bv, 1.0, 0.5)), index=frame.index)
    if debug:
        for k, v in dbg.items():
            out[k] = v
    return out
