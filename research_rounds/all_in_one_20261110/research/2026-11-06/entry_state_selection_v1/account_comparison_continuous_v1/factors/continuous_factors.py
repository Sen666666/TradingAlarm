"""Causal theoretical-ex-price factors only. No Account/Runner or order imports."""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from bisect import bisect_right
import math
import pandas as pd

D=Decimal

class OpenFactorTimeline:
    """Build immutable factor change points using strict prior closes and action terms.
    Terms are assumed preknown; effective dates do NOT prove announcement availability.
    factor(at) is available before that date's close; no interpolation/backfill.
    """
    def __init__(self, raw, events, *, method='theoretical_ex_price', end=None):
        if method!='theoretical_ex_price': raise ValueError('Unsupported open factor method: '+method)
        f=raw.copy(deep=False)
        if 'trade_date' in f: f=f.set_index('trade_date')
        elif 'date' in f: f=f.set_index('date')
        f.index=pd.DatetimeIndex(pd.to_datetime(f.index))
        if f.empty or not f.index.is_unique or not f.index.is_monotonic_increasing:
            raise ValueError('Nonempty increasing unique raw source required')
        self.start=f.index[0]
        self.end=pd.Timestamp(end) if end is not None else f.index[-1]
        if self.end<self.start: raise ValueError('End before source')
        closes={t: v for t,v in zip(f.index,f.close) if t<=self.end}
        active={}
        for e in events:
            t=pd.Timestamp(e['effective_date'])
            if t in active: raise ValueError('Same-date actions must be aggregated upstream')
            if t==self.start and (D(str(e['cash_per_old_share']))!=0 or D(str(e['split_ratio']))!=1):
                raise ValueError('Origin action needs explicit prior state')
            if self.start<t<=self.end: active[t]=e
        days=sorted(set(closes)|set(active))
        changes=[]; audits=[]; factor=D(1); previous=None
        with localcontext() as ctx:
            ctx.prec=40;ctx.rounding=ROUND_HALF_EVEN
            for t in days:
                e=active.get(t)
                if e:
                    cash=D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share'])))
                    split=D(str(e.get('signal_split_ratio',e['split_ratio'])))
                    if not cash.is_finite() or not split.is_finite() or split<=0 or previous is None or previous<=cash:
                        raise ValueError('Invalid action reference: '+str(t))
                    prior=previous;ex=(previous-cash)/split
                    factor*=previous/ex
                    changes.append((t,float(factor)))
                    audits.append(dict(day=str(t.date()),prior_raw_reference=str(prior),
                        theoretical_ex_reference=str(ex),factor_decimal=str(factor),factor_float=float(factor),
                        missing_raw_bar=t not in closes,terms_availability='ASSUMED_PREKNOWN_NOT_PIT_VERIFIED'))
                    if t not in closes: previous=ex
                # Current close advances NEXT event reference only, after today's factor.
                if t in closes:
                    value=closes[t]
                    if pd.notna(value) and math.isfinite(float(value)):
                        value=D(str(value))
                        if value>0: previous=value
        self.change_days=tuple(x[0] for x in changes)
        self.change_values=tuple(x[1] for x in changes)
        self.action_audit=tuple(audits)

    def factor_float(self, at):
        t=pd.Timestamp(at)
        if t.tzinfo is not None: t=t.tz_convert('Asia/Shanghai').tz_localize(None)
        t=t.normalize()
        if t<self.start or t>self.end: raise ValueError('Factor query outside frozen coverage')
        i=bisect_right(self.change_days,t)-1
        return 1.0 if i<0 else self.change_values[i]

    def factor(self, at):
        """Same Decimal(str(float factor)) conversion as original Facts.factor."""
        return D(str(self.factor_float(at)))

    def at_dates(self, dates):
        return pd.Series([self.factor_float(t) for t in dates],index=dates,name='factor')

class FactorSource:
    """Thin sid->frozen timeline registry; no implicit unknown-stock fallback."""
    def __init__(self, timelines):
        self.timelines=dict(timelines)
    def factor_at(self, sid, day):
        return self.timelines[sid].factor(day)
