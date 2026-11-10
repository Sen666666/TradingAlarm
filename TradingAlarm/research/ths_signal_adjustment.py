"""Causal price-adjustment reconstruction for signal research, not account returns."""
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
from stock_actions import parse_ths_rights

def signal_frame(history, rights, start='2013-01-01', reference_tick=None):
    if reference_tick is not None and reference_tick<=0:raise ValueError('reference tick must be positive')
    if history['symbol']!=rights['symbol']:raise ValueError('symbol mismatch')
    if not rights.get('records'):raise ValueError('empty rights response does not certify no events')
    raw=pd.DataFrame(history['bars']);raw['date']=pd.to_datetime(raw.date);raw=raw.set_index('date').sort_index()
    raw=raw.loc[raw.index>=pd.Timestamp(start)]
    if raw.empty or raw.index.duplicated().any():raise ValueError('empty or duplicated history')
    events={}
    for row in rights['records']:
        dt=pd.to_datetime(str(row['1']),format='%Y%m%d')
        if dt<=raw.index.min() or dt>raw.index.max():continue
        event=parse_ths_rights(history['symbol'],row)
        if dt in events:raise ValueError('multiple same-date events require explicit aggregation')
        events[dt]=event
    observed=raw.index
    raw=raw.reindex(raw.index.union(pd.DatetimeIndex(sorted(events)))).sort_index()
    raw['observed_bar']=raw.index.isin(observed)
    raw['synthetic_event_bar']=~raw.observed_bar
    jumps=pd.Series(1.,index=raw.index)
    for dt,e in sorted(events.items()):
        cash=e['gross_cash_per_old_share'];shares=1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']
        prior=float(raw.loc[:dt,'close'].iloc[:-1].ffill().iloc[-1])
        if not np.isfinite(prior) or prior<=cash:raise ValueError('invalid theoretical ex-price')
        ex_price=(prior-cash)/shares
        if reference_tick is not None:
            # Optional vendor-convention sensitivity, not a dividend cash-flow change.
            exact=(Decimal(str(prior))-Decimal(str(cash)))/Decimal(str(shares))
            tick=Decimal(str(reference_tick))
            ex_price=float((exact/tick).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*tick)
            if ex_price<=0:raise ValueError('nonpositive rounded ex-price')
        jumps.loc[dt]=prior/ex_price
        if not raw.loc[dt,'observed_bar']:
            # Keep the event on its actual date. This theoretical reference is
            # signal-only and explicitly cannot be used as a transaction price.
            raw.loc[dt,['open','high','low','close']]=ex_price
            raw.loc[dt,['volume','amount']]=0.
    factor=jumps.cumprod()
    for key in ['open','high','low','close']:
        raw['signal_'+key]=raw[key]*factor
    raw['factor']=factor
    raw['bar_allows_trade']=raw.observed_bar & raw.volume.gt(0)
    raw.attrs['limitation']='Theoretical ex-price adjustment for signals only; not actual total return, not cash/share accounting. Requires complete rights source; subscription/unknown events fail closed.'
    return raw
