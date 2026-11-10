"""Continuous clock-gated research OPEN proxy; original CLOSE and account methods."""
from copy import copy
from collections.abc import Mapping
from decimal import Decimal as D
from datetime import datetime,time
import numpy as np,pandas as pd

class OpenQuotesOnly(Mapping):
    """Native opening can see only the current raw open, never a full OHLCV row."""
    def __init__(self,market):self.market=market;self.cache={}
    def __iter__(self):return iter(self.market._raw_source)
    def __len__(self):return len(self.market._raw_source)
    def __getitem__(self,sid):
        m=self.market;assert m.phase=='OPEN'
        if sid not in self.cache:
            f=m._raw_source[sid];d=pd.Timestamp(m.phase_at.date())
            self.cache[sid]=pd.DataFrame({'open':[f.loc[d,'open']]},index=pd.DatetimeIndex([d])) if d in f.index else pd.DataFrame({'open':[]},index=pd.DatetimeIndex([]))
        return self.cache[sid]

class ClockFacts:
    def __init__(self,original,market,factors):self.original=original;self.market=market;self.factors=factors
    def __getattr__(self,key):return getattr(self.original,key)
    def row(self,sid,at):
        assert self.market.phase=='CLOSE' and at==self.market.phase_at,('signal row outside close',sid,at)
        return self.original.row(sid,at)
    def floor(self,*args,**kwargs):
        assert self.market.phase=='CLOSE'
        return self.original.floor(*args,**kwargs)
    def packet(self,*args,**kwargs):
        assert self.market.phase=='CLOSE'
        return self.original.packet(*args,**kwargs)
    def factor(self,sid,at):
        assert at==self.market.phase_at,('wrong factor clock',sid,at,self.market.phase_at)
        if self.market.phase=='CLOSE':return self.original.factor(sid,at)
        return self.factors.factor_at(sid,at.date().isoformat())

def attach(original,facts,factors,ledger):
    base=type(original);RuleUnavailable=original.window.__func__.__globals__['RuleUnavailable']
    class ContinuousMarket(base):
        def set_phase(self,at,phase):
            assert phase in ('ACTION','OPEN','CLOSE')
            self.phase_at=at;self.phase=phase;self.cache_at=None;self.open_marks={};self.open_windows={}
            self.raw=OpenQuotesOnly(self) if phase=='OPEN' else ({} if phase=='ACTION' else self._raw_source)
        def latest_mark(self,sid,at):
            assert at==self.phase_at,('mark clock mismatch',at,self.phase_at)
            if self.phase=='CLOSE':return base.latest_mark(self,sid,at)
            if sid in self.open_marks:return self.open_marks[sid]
            self.source_available(sid,at);f=self._raw_source[sid];day=pd.Timestamp(at.date());record=self.bundle.series[sid].record;src=record['raw']['sha256']
            if self.phase=='OPEN' and day in f.index and np.isfinite(f.loc[day,'open']) and f.loc[day,'open']>0:
                price=D(str(f.loc[day,'open']));known=at;src+=':known_open'
            else:
                ar=self.arr[sid];dv=day.value//86400000000000
                valid=ar['good'];j=np.searchsorted(ar['days'][valid],dv,side='left')-1
                if j<0:raise RuleUnavailable('No prior valid observed mark: '+sid)
                k=valid[j];md=pd.Timestamp(int(ar['days'][k])*86400000000000).date()
                price=D(str(ar['close'][k]));known=datetime.combine(md,ar['close_time'],at.tzinfo)
                for e in sorted(self.actions.get(sid,[]),key=lambda e:e['effective_date']):
                    if md.isoformat()<e['effective_date']<=day.date().isoformat():
                        price=(price-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
                        src+=':derived_ex_reference:'+e['effective_date']+':'+e['source_id']
                assert price>0 and known<=at
            mark=ledger.Mark(price,known,self.rate('CNY',at),src);self.open_marks[sid]=mark;return mark
        def window(self,sid,at,side,cost_multiplier):
            assert self.phase=='OPEN' and at==self.phase_at
            key=(sid,side,cost_multiplier)
            if key in self.open_windows:return self.open_windows[key]
            self.open_windows[key]=None
            market=self.lines[sid].market
            if at not in self.sessions_set[market]:return None
            try:
                self.source_available(sid,at)
                ar=self.arr[sid];day=pd.Timestamp(at.date()).value//86400000000000;p=np.searchsorted(ar['days'],day)
                if p>=len(ar['days']) or ar['days'][p]!=day or not np.isfinite(ar['open'][p]) or ar['open'][p]<=0:
                    self.exec_counts['missing_open']+=1;return None
                j=np.searchsorted(ar['positive'],p)
                if j<20:self.exec_counts['insufficient_prior_volume']+=1;return None
                prior=ar['volume'][ar['positive'][j-20:j]];capacity=int(prior.mean()*float(self.protocol['participation_rate']))
                availability=self._version('availability_versions',sid,at);q=self.quantity(sid,at);fees=self.fees(sid,at)
                op=D(str(ar['open'][p]));slip=D(self.protocol['daily_execution'][market]['slippage_bps'])/D(10000)
                if cost_multiplier==2 and self.protocol['daily_execution'][market]['stress_slippage']:slip*=2
                px=op*(1+slip if side=='buy' else 1-slip)
                w=ledger.FillWindow(f'{sid}:{at.isoformat()}:{side}',sid,at,op,px,self.rate('CNY',at),q,fees,capacity,True,availability.get('buy_allowed'),availability.get('sell_allowed'),self.lag(market,at,self.protocol['sellable_lag_sessions'][market]),self.lag(market,at,self.protocol['settlement_lag_sessions'][market]),self.bundle.series[sid].record['raw']['sha256'],'CAUSAL_OPEN_PROXY_PRIOR20_ONLY_TRADABILITY_UNKNOWN',self.rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
                w.validate();self.open_windows[key]=w;self.exec_counts['proxy_windows']+=1
                self.exec_rows.append(dict(sid=sid,at=at,side=side,raw_open=op,price=px,capacity=capacity,prior_volume_last=str(pd.Timestamp(int(ar['days'][ar['positive'][j-1]])*86400000000000).date()),unknown_tradability=True))
                return w
            except RuleUnavailable as e:
                self.exec_counts['rule_unavailable']+=1;self.exec_rows.append(dict(sid=sid,at=at,side=side,result='RULE_UNAVAILABLE',reason=str(e)));return None
    from collections import Counter
    m=copy(original);m.__class__=ContinuousMarket;m._raw_source=original.raw;m.raw=original.raw;m.phase=None;m.phase_at=None;m.exec_counts=Counter();m.exec_rows=[];m.cache_at=None;m.mark_verified=set();m.window_verified=set()
    # Existing immutable dated arrays/price sources are shared read-only; all public OPEN rows are one-column gated.
    f=ClockFacts(facts,m,factors);facts.market=m
    return m,f
