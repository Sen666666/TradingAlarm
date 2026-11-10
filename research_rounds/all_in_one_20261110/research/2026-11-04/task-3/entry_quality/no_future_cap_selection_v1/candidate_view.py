"""Small research candidate view. No market-cap/roster/industry/account inputs."""
import numpy as np
import pandas as pd

DATES = ['2022-01-10', '2022-01-24', '2024-09-24', '2024-10-08',
         '2026-01-15', '2026-01-20', '2026-05-15']
UNKNOWN = 'UNKNOWN_NOT_CERTIFIED'


def prior_liquidity20(bars, target_days=DATES):
    """Only lag1..20 of a valid block; no current/future amount or invalid fill."""
    g = bars.sort_values('trade_date').reset_index(drop=True)
    assert g.trade_date.is_unique
    c = g.close.to_numpy(float); a = g.amount.to_numpy(float)
    source_known = g.source.notna() & g.source.astype('string').str.strip().ne('').fillna(False)
    valid = np.isfinite(c) & (c > 0) & np.isfinite(a) & (a > 0) & source_known.to_numpy(bool)
    source = g.source.astype(str).to_numpy()
    dates = g.trade_date.to_numpy(dtype='datetime64[ns]')
    starts = np.zeros(len(g), dtype=int)
    for j in range(len(g)):
        starts[j] = (j if j == 0 or not valid[j] or not valid[j-1]
                     or source[j] != source[j-1] else starts[j-1])
    rows = []
    for day in target_days:
        t = np.datetime64(day, 'ns'); j = int(np.searchsorted(dates, t))
        r = dict(day=day, amount20_prior_native=np.nan,
                 amount20_prior_observations=0, amount20_window_start=pd.NaT,
                 amount20_window_end=pd.NaT, amount20_calendar_span_days=pd.NA,
                 amount20_status='MISSING_TARGET_BAR')
        if j < len(g) and dates[j] == t:
            if not valid[j]:
                r['amount20_status'] = 'INVALID_CURRENT_PRICE_AMOUNT'
            else:
                n = min(20, j-int(starts[j])); r['amount20_prior_observations'] = n
                r['amount20_status'] = 'INSUFFICIENT_PRIOR_VALID_BLOCK'
                if n == 20:
                    window = a[j-20:j]
                    assert np.isfinite(window).all() and (window > 0).all()
                    assert dates[j-1] < t
                    r.update(amount20_prior_native=float(np.median(window)),
                             amount20_window_start=pd.Timestamp(dates[j-20]),
                             amount20_window_end=pd.Timestamp(dates[j-1]),
                             amount20_calendar_span_days=int((dates[j-1]-dates[j-20]) / np.timedelta64(1, 'D')),
                             amount20_status='KNOWN_PRIOR20_SOURCE_OBSERVATIONS')
        rows.append(r)
    return pd.DataFrame(rows)


def candidate_view(features, liquidity):
    """Research PVR queue only. Unknown legal status never grants execution."""
    keys = ['sid', 'day']
    assert not features.duplicated(keys).any() and not liquidity.duplicated(keys).any()
    columns = keys + ['target_row_present', 'pvr_valid_observation', 'pvr_status',
                      'score', 'current_close_qfq', 'raw_close', 'current_amount_passthrough',
                      'source', 'current_block_observations_through_t']
    out = features[columns].copy().merge(liquidity, on=keys, validate='one_to_one')
    assert len(out) == len(features)
    source_known = out.source.notna() & out.source.astype('string').str.strip().ne('').fillna(False)
    out['research_no_cap_pool'] = (out.target_row_present.eq(True) & source_known
        & out.pvr_valid_observation.eq(True) & out.pvr_status.eq('KNOWN')
        & np.isfinite(out.score))
    for field in ['historical_listing_identity', 'historical_ST', 'historical_halt',
                  'historical_limit_state', 'executable_eligibility']:
        out[field] = UNKNOWN
    out['amount20_unit'] = 'TUSHARE_NATIVE_AMOUNT_PASSTHROUGH_NOT_CERTIFIED_CNY_CAPACITY'
    out['amount20_window_basis'] = '20_PRIOR_VALID_STOCK_OBSERVATIONS_NOT_CERTIFIED_EXCHANGE_SESSIONS'
    out['queue_layer'] = 'PRICE_SCORE_RESEARCH_ONLY'
    out['no_cap_PVR_rank'] = pd.Series(pd.NA, index=out.index, dtype='Int64')
    for _, g in out.loc[out.research_no_cap_pool].groupby('day', sort=False):
        ix = g.sort_values(['score', 'sid'], ascending=[False, True]).index
        out.loc[ix, 'no_cap_PVR_rank'] = np.arange(1, len(ix)+1)
    return out.sort_values(keys).reset_index(drop=True)
