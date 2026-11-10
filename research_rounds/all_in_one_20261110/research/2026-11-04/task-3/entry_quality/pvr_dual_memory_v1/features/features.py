"""Original scalar e, then two disjoint finite memory windows. No scores/ranks."""
import numpy as np
import pandas as pd

E_COLUMNS = ('r', 'scale', 'amount_ref', 'u', 'b', 'e')


def calculate(signal, valid, block):
    if not signal.index.equals(valid.index) or not signal.index.equals(block.index):
        raise ValueError('Original observation clock must align exactly')
    if not signal.index.is_unique or not signal.index.is_monotonic_increasing or signal.segment_id.isna().any():
        raise ValueError('Ordered unique source dates and known segments required')
    out = pd.DataFrame(index=signal.index, columns=list(E_COLUMNS), dtype=float)
    out['source_segment'] = signal.segment_id
    out['pvr_valid_observation'] = valid.astype(bool)
    out['pvr_clock_block'] = block.astype('int64')
    out['pvr_block_observation'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    out['E_fast'] = np.nan
    out['E_slow'] = np.nan
    out['fast_known_count5'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    out['slow_known_count58'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    out['e_known_count63'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    out['observation_count63'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    for name in ['fast_start_day', 'fast_end_day', 'slow_start_day', 'slow_end_day']:
        out[name] = pd.Series(pd.NaT, index=signal.index, dtype='datetime64[ns]')
    out['dual_memory_status'] = pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION', index=signal.index, dtype='string')
    out['fast_status'] = pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION', index=signal.index, dtype='string')
    out['slow_status'] = pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION', index=signal.index, dtype='string')
    out.loc[valid, 'dual_memory_status'] = 'WARMUP_FEWER_THAN63_FINITE_E_IN_BLOCK'
    out.loc[valid, 'fast_status'] = 'WARMUP_FEWER_THAN5_FINITE_E_IN_BLOCK'
    out.loc[valid, 'slow_status'] = 'WARMUP_FEWER_THAN58_FINITE_LAG5_TO62_E_IN_BLOCK'
    weights = .8 ** np.arange(4, -1, -1)
    denominator = weights.sum()
    for _, group in signal.loc[valid].groupby(block[valid], sort=False):
        idx = group.index
        # These six scalar operations are copied without rearrangement from
        # pvr_information_v1/feature_design/features.py::original_pvr.
        r = np.log(group.close).diff()
        scale = r.abs().shift().rolling(63, min_periods=63).median().mul(1.4826).clip(lower=1e-8)
        amount_ref = group.amount.shift().rolling(21, min_periods=21).median()
        u = np.tanh(r / scale)
        b = np.tanh(np.log(group.amount / amount_ref))
        e = u * (1 + .5 * u.abs() * b)
        out.loc[idx, list(E_COLUMNS)] = pd.DataFrame(dict(r=r, scale=scale, amount_ref=amount_ref, u=u, b=b, e=e), index=idx)
        out.loc[idx, 'pvr_block_observation'] = np.arange(len(group))
        out.loc[idx, 'fast_known_count5'] = e.rolling(5, min_periods=1).count().astype('int64')
        out.loc[idx, 'slow_known_count58'] = e.shift(5).rolling(58, min_periods=1).count().astype('int64')
        out.loc[idx, 'e_known_count63'] = e.rolling(63, min_periods=1).count().astype('int64')
        out.loc[idx, 'observation_count63'] = np.minimum(np.arange(len(group)) + 1, 63)
        if len(group) >= 5:
            fast_windows = np.lib.stride_tricks.sliding_window_view(e.to_numpy(float), 5)
            fast_targets = idx[4:]
            fast = (fast_windows * weights).sum(axis=1) / denominator
            fast_known = np.isfinite(fast_windows).all(axis=1) & np.isfinite(fast)
            out.loc[fast_targets, 'E_fast'] = np.where(fast_known, fast, np.nan)
            out.loc[fast_targets[fast_known], 'fast_status'] = 'KNOWN'
            dates = idx.to_numpy(dtype='datetime64[ns]')
            out.loc[fast_targets, 'fast_start_day'] = dates[:-4]
            out.loc[fast_targets, 'fast_end_day'] = dates[4:]
        if len(group) < 63:
            continue
        windows = np.lib.stride_tricks.sliding_window_view(e.to_numpy(float), 63)
        targets = idx[62:]
        slow = windows[:, :58].mean(axis=1)
        slow_known = np.isfinite(windows[:, :58]).all(axis=1) & np.isfinite(slow)
        out.loc[targets, 'E_slow'] = np.where(slow_known, slow, np.nan)
        out.loc[targets[slow_known], 'slow_status'] = 'KNOWN'
        joint_known = slow_known & out.loc[targets, 'fast_status'].eq('KNOWN').to_numpy()
        out.loc[targets[joint_known], 'dual_memory_status'] = 'KNOWN'
        j = np.arange(62, len(group))
        dates = idx.to_numpy(dtype='datetime64[ns]')
        for field, offset in [('slow_start_day', -62), ('slow_end_day', -5)]:
            out.loc[targets, field] = dates[j + offset]
    return out
