"""Signal-only stock adapter. No account wealth or executable-return claims."""
import numpy as np
import pandas as pd


def retired_signal_frame(history, factors):
    if history['symbol'] != factors['symbol']:
        raise ValueError('factor/history symbol mismatch')
    bars = pd.DataFrame(history['rows']).copy()
    events = pd.DataFrame(factors['rows']).copy()
    if bars.empty or events.empty:
        raise ValueError('empty history or factors: cannot assume no corporate actions')
    bars['date'] = pd.to_datetime(bars['date'])
    events['date'] = pd.to_datetime(events['dividOperateDate'])
    if bars.date.duplicated().any() or events.date.duplicated().any():
        raise ValueError('duplicate dates')
    for key in ['open', 'high', 'low', 'close', 'volume', 'amount']:
        bars[key] = pd.to_numeric(bars[key], errors='raise')
    events['factor'] = pd.to_numeric(events.backAdjustFactor, errors='raise')
    if (~np.isfinite(events.factor) | (events.factor <= 0)).any():
        raise ValueError('invalid adjustment factor')
    result = pd.merge_asof(bars.sort_values('date'), events[['date', 'factor']].sort_values('date'),
                           on='date', direction='backward').set_index('date')
    if result.factor.isna().any():
        raise ValueError('no historical factor anchor; never backfill a future event')
    for key in ['open', 'high', 'low', 'close']:
        result['signal_' + key] = result[key] * result.factor
    result['bar_allows_trade'] = result.tradestatus.eq('1') & result.volume.gt(0)
    result.attrs['limitation'] = 'Provider-revised factors are for price signals only, not cash/share accounting; price limits and other execution gates not applied.'
    return result


def stock_features(frame):
    """At-close features; orders must use these only at a later tradable open."""
    close = frame.signal_close
    high, low = frame.signal_high, frame.signal_low
    out = pd.DataFrame(index=frame.index)
    out['sma200'] = close.rolling(200, min_periods=200).mean()
    out['breakout55'] = high.shift(1).rolling(55, min_periods=55).max()
    true_range = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    out['atr20'] = true_range.rolling(20, min_periods=20).mean()
    out['momentum126_21'] = close.shift(21).div(close.shift(126)).sub(1)
    out['momentum252_21'] = close.shift(21).div(close.shift(252)).sub(1)
    out['turnover60'] = frame.amount.rolling(60, min_periods=60).mean()
    out['entry_signal'] = (close > out.sma200) & (close > out.breakout55)
    below = close < out.sma200
    out['exit_signal'] = below & below.shift(1, fill_value=False)
    out['warmup_ready'] = out[['sma200','atr20','momentum126_21','momentum252_21','turnover60']].notna().all(axis=1)
    return out
