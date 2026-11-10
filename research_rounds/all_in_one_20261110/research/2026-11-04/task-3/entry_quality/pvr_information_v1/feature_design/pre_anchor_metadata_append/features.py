"""Finite causal PVR-information features. No files, accounts, labels or execution.

All rolling calculations use the ORIGINAL PVR observation/block clock, including
its positive-finite amount requirement. The 21/.9 sign summary is signed,
not an absolute persistence strength. No combined eligibility gate is defined.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

ORIGINAL_PVR_SOURCE_SHA256 = '9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
PVR_COLUMNS = ('r', 'scale', 'amount_ref', 'u', 'b', 'e', 'E', 'score')
FEATURE_COLUMNS = ('sign_persistence21_w09', 'logreturn_std20',
                   'close_gap_prior_high20', 'breakout_prior_high20',
                   'close_location_in_day_range', 'return5', 'return20',
                   'positive_effective_observations21_w09')
POSITIVE_MASK_COLUMNS = ('price_eligible', 'observed_bar', 'is_observed_bar')
NEGATIVE_MASK_COLUMNS = ('source_invalid', 'synthetic_event_bar')


def original_observation_clock(signal: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Exact original score mask/reset: invalid rows restart full preparation."""
    valid = (signal.close.gt(0) & np.isfinite(signal.close)
             & signal.amount.gt(0) & np.isfinite(signal.amount))
    for name in POSITIVE_MASK_COLUMNS:
        if name in signal:
            valid &= signal[name].fillna(False).astype(bool)
    for name in NEGATIVE_MASK_COLUMNS:
        if name in signal:
            valid &= ~signal[name].fillna(True).astype(bool)
    segment = signal.segment_id
    block = ((~valid) | (~valid.shift(fill_value=False))
             | segment.ne(segment.shift())).cumsum()
    return valid.astype(bool), block


def original_pvr(signal: pd.DataFrame) -> pd.DataFrame:
    """Original source formula, same scalar operations, weights and min_periods.

    Input validation and explicit segment identity are owned by compute_features.
    """
    out = pd.DataFrame(index=signal.index, columns=list(PVR_COLUMNS), dtype=float)
    valid, block = original_observation_clock(signal)
    weights = .9 ** np.arange(20, -1, -1)
    weights /= weights.sum()
    for _, group in signal.loc[valid].groupby(block[valid], sort=False):
        r = np.log(group.close).diff()
        scale = r.abs().shift().rolling(63, min_periods=63).median().mul(1.4826).clip(lower=1e-8)
        amount_ref = group.amount.shift().rolling(21, min_periods=21).median()
        u = np.tanh(r / scale)
        b = np.tanh(np.log(group.amount / amount_ref))
        e = u * (1 + .5 * u.abs() * b)
        E = e.rolling(21, min_periods=21).apply(lambda x: np.dot(weights, x), raw=True)
        out.loc[group.index] = pd.DataFrame(
            dict(r=r, scale=scale, amount_ref=amount_ref, u=u, b=b, e=e,
                 E=E, score=50 + 50 * np.tanh(2 * E)), index=group.index)
    return out


def positive_effective_observations21_w09(e: pd.Series) -> pd.Series:
    """Lplus=(sum p)^2/sum(p^2), p=w*max(e,0), full21 required.

    An effective positive-observation count, never duration or probability.
    No positive denominator gives UNKNOWN; do not impute zero or divide by21.
    """
    weights = .9 ** np.arange(20, -1, -1)
    weights /= weights.sum()

    def effective(values):
        p = weights * np.maximum(values, 0.)
        denominator = np.dot(p, p)
        if not np.isfinite(denominator) or denominator <= 0:
            return np.nan
        return float(p.sum() ** 2 / denominator)

    return e.rolling(21, min_periods=21).apply(effective, raw=True)


def compute_features(signal: pd.DataFrame) -> pd.DataFrame:
    """Return original PVR + exactly eight authorized features, on same index.

    UNKNOWN uses NaN / nullable boolean NA and a per-feature status. WARMUP is
    per formula; it is never converted to zero/False or a new permission gate.
    signal.close/high/low must be the same causal signal-price coordinate;
    raw_* and adjustment_factor are not mixed into any numerical feature.
    All current-row features become known only after that CLOSE.
    """
    required = {'close', 'high', 'low', 'amount', 'segment_id'}
    if not required <= set(signal.columns):
        raise ValueError('Missing input columns: ' + ','.join(sorted(required-set(signal.columns))))
    if not signal.columns.is_unique:
        raise ValueError('Unique columns required')
    if not isinstance(signal.index, pd.DatetimeIndex):
        raise ValueError('DatetimeIndex required')
    if signal.index.hasnans or not signal.index.is_unique or not signal.index.is_monotonic_increasing:
        raise ValueError('Ordered unique observation dates required')
    if not signal.index.normalize().is_unique:
        raise ValueError('At most one observation per day required')
    if signal.segment_id.isna().any():
        raise ValueError('Explicit nonmissing source segment required')
    for name in ['close', 'high', 'low', 'amount']:
        if not pd.api.types.is_numeric_dtype(signal[name]):
            raise ValueError('Numeric input required: ' + name)
    valid, block = original_observation_clock(signal)
    out = original_pvr(signal)
    out['source_segment'] = signal.segment_id.copy()
    out['pvr_valid_observation'] = valid
    out['pvr_clock_block'] = block.astype('int64')
    out['pvr_block_observation'] = pd.Series(pd.NA, index=signal.index, dtype='Int64')
    out['pvr_status'] = pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION', index=signal.index, dtype='string')
    out.loc[valid, 'pvr_status'] = 'WARMUP'
    out.loc[np.isfinite(out.score), 'pvr_status'] = 'KNOWN'
    for name in FEATURE_COLUMNS:
        if name == 'breakout_prior_high20':
            out[name] = pd.Series(pd.NA, index=signal.index, dtype='boolean')
        else:
            out[name] = np.nan
        out[name + '_status'] = pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION', index=signal.index, dtype='string')
        out.loc[valid, name + '_status'] = 'WARMUP'
    weights = .9 ** np.arange(20, -1, -1)
    weights /= weights.sum()
    for _, group in signal.loc[valid].groupby(block[valid], sort=False):
        idx = group.index
        out.loc[idx, 'pvr_block_observation'] = np.arange(len(group))
        r = out.loc[idx, 'r']
        values = {
            'sign_persistence21_w09': np.sign(r).rolling(21, min_periods=21).apply(lambda x: np.dot(weights, x), raw=True),
            'logreturn_std20': r.rolling(20, min_periods=20).std(ddof=0),
            'return5': group.close / group.close.shift(5) - 1,
            'return20': group.close / group.close.shift(20) - 1,
            'positive_effective_observations21_w09': positive_effective_observations21_w09(out.loc[idx, 'e']),
        }
        prior_high = group.close.shift().rolling(20, min_periods=20).max()
        values['close_gap_prior_high20'] = group.close / prior_high - 1
        for name, value in values.items():
            out.loc[idx, name] = value
            out.loc[value.index[np.isfinite(value)], name + '_status'] = 'KNOWN'
            needed = {'sign_persistence21_w09': 21, 'logreturn_std20': 20,
                      'return5': 5, 'return20': 20, 'close_gap_prior_high20': 20}.get(name)
            if needed is not None:
                window_present = pd.Series(np.arange(len(group)) >= needed, index=idx)
                numeric_unknown = window_present & ~np.isfinite(value)
                out.loc[idx[numeric_unknown], name + '_status'] = 'UNKNOWN_NUMERICAL_RESULT'
        # Full original e window with zero positive mass is explicitly unknown.
        full_e_window = out.loc[idx, 'e'].rolling(21, min_periods=21).count().eq(21)
        no_positive_mass = full_e_window & out.loc[idx, 'positive_effective_observations21_w09'].isna()
        out.loc[idx[no_positive_mass], 'positive_effective_observations21_w09_status'] = 'UNKNOWN_NONPOSITIVE_OR_NONFINITE_EFFECTIVE_DENOMINATOR'
        known_high = np.isfinite(prior_high)
        out.loc[idx[known_high], 'breakout_prior_high20'] = group.close.loc[known_high].gt(prior_high.loc[known_high]).astype('boolean')
        out.loc[idx[known_high], 'breakout_prior_high20_status'] = 'KNOWN'
        high, low, close = group.high, group.low, group.close
        geometry_known = (np.isfinite(high) & np.isfinite(low) & high.gt(0)
                          & low.gt(0) & high.ge(close) & low.le(close) & high.ge(low))
        nonzero = geometry_known & high.gt(low)
        out.loc[idx, 'close_location_in_day_range_status'] = 'UNKNOWN_OHLC_RANGE'
        out.loc[idx[geometry_known & high.eq(low)], 'close_location_in_day_range_status'] = 'UNKNOWN_ZERO_RANGE'
        out.loc[idx[nonzero], 'close_location_in_day_range'] = (close.loc[nonzero]-low.loc[nonzero])/(high.loc[nonzero]-low.loc[nonzero])
        out.loc[idx[nonzero], 'close_location_in_day_range_status'] = 'KNOWN'
    out.attrs = {
        'clock': 'exact original PVR positive finite close+amount, original optional validity masks; invalid row/source change restarts',
        'price_coordinate': 'causal signal close/high/low; raw_* ignored',
        'pvr_source_sha256': ORIGINAL_PVR_SOURCE_SHA256,
        'breakout_definition': 'current close > max(previous20 closes), excluding current; no first-ever/age state',
        'no_future_labels': True,
    }
    return out
