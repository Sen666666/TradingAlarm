"""Isolated OPEN-only execution proxy. No original source writes; no live orders."""
from copy import copy
from types import SimpleNamespace
from decimal import Decimal as D
from datetime import datetime,time
import numpy as np,pandas as pd

MODES=('OPEN_PROXY','UNKNOWN_NO_FILL')

def freeze_open_inputs(original_market, original_facts, signal_at, open_at, needed):
    """Freeze prior factors and derive action transforms without today's HLCV.
    Action announcement availability is unverified and explicitly hypothetical.
    """
    factors={};action_audit=[]
    day=pd.Timestamp(open_at.date())
    for sid in needed:
        prior=original_facts.factor(sid,signal_at)
        factors[sid]=prior
        events=[e for e in original_market.actions.get(sid,[]) if signal_at.date().isoformat()<e['effective_date']<=open_at.date().isoformat()]
        if events:
            method=original_market.bundle.series[sid].record['adjustment']['method']
            assert method=='theoretical_ex_price',('unsupported action factor method',sid,method)
            f=original_market.raw[sid];p=f.loc[f.index<day,'close'];p=p[np.isfinite(p)&p.gt(0)]
            assert len(p),('no prior action reference',sid)
            close=D(str(p.iloc[-1]));value=prior
            for e in sorted(events,key=lambda e:e['effective_date']):
                cash=D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share'])))
                split=D(str(e.get('signal_split_ratio',e['split_ratio'])))
                assert close>cash and split>0
                ex=(close-cash)/split;value*=close/ex;close=ex
            factors[sid]=D(str(float(value)))
            action_audit.append(dict(sid=sid,prior_factor=str(prior),derived_open_factor=str(factors[sid]),events=events,availability='ANNOUNCEMENT_TIME_UNKNOWN_ASSUMED_PREKNOWN_RESEARCH_TERMS'))
    return factors,action_audit

class OpenFacts:
    def __init__(self, factors, original):
        self.factors=factors;self.structure_lookup=original.structure_lookup
    def factor(self,sid,at):return self.factors[sid]
    def row(self,*args,**kwargs):raise AssertionError('OPEN must not read current/full signal row')
    def floor(self,*args,**kwargs):raise AssertionError('OPEN must use frozen position/intention floor')

def build_market(original,ledger,open_at,mode,variant='MASKED'):
    assert mode in MODES and variant in ('MASKED','POISONED')
    base=type(original)
    RuleUnavailable=original.window.__func__.__globals__['RuleUnavailable']
    class OpenOnlyMarket(base):
        def latest_mark(self,sid,at):
            assert at>=self.open_at
            self.source_available(sid,self.open_at)
            key=(sid,at)
            if key in self.open_mark_cache:return self.open_mark_cache[key]
            f=self.raw[sid];day=pd.Timestamp(self.open_at.date());source=self.bundle.series[sid].record['raw']['sha256']
            if day in f.index and np.isfinite(f.loc[day,'open']) and f.loc[day,'open']>0:
                result=ledger.Mark(D(str(f.loc[day,'open'])),self.open_at,self.rate('CNY',at),source+':known-open-proxy')
            else:
                past=f[f.index<day]
                valid=past['valid_price'].eq(True)&past['observed_bar'].eq(True)&np.isfinite(past.close)&past.close.gt(0)
                past=past[valid];assert len(past),('no prior mark',sid)
                markday=past.index[-1];price=D(str(past.close.iloc[-1]))
                for e in sorted(self.actions.get(sid,[]),key=lambda e:e['effective_date']):
                    if markday.date().isoformat()<e['effective_date']<=self.open_at.date().isoformat():
                        price=(price-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
                known=datetime.combine(markday.date(),time.fromisoformat(self.bundle.series[sid].record['close_available_time']),self.open_at.tzinfo)
                assert price>0 and known<self.open_at
                result=ledger.Mark(price,known,self.rate('CNY',at),source+':prior-observed-mark')
            self.open_mark_cache[key]=result;return result
        def window(self,sid,at,side,cost_multiplier):
            assert at==self.open_at
            if at not in self.sessions_set[self.lines[sid].market]:return None
            try:
                self.source_available(sid,at)
                return self._open_window(sid,at,side,cost_multiplier)
            except RuleUnavailable as error:
                self.execution_audit.append(dict(sid=sid,side=side,at=at,result='RULE_UNAVAILABLE',reason=str(error)))
                return None
        def _open_window(self,sid,at,side,cost_multiplier):
            assert at==self.open_at,'Bounded adapter only admits one OPEN'
            key=(sid,side,cost_multiplier)
            if key in self.open_window_cache:return self.open_window_cache[key]
            day=pd.Timestamp(at.date());f=self.raw[sid]
            if day not in f.index or not np.isfinite(f.loc[day,'open']) or f.loc[day,'open']<=0:return None
            prior=f.loc[f.index<day,'volume'];prior=prior[np.isfinite(prior)&prior.gt(0)].tail(20)
            if len(prior)!=20:return None
            qrule=self.quantity(sid,at);fees=self.fees(sid,at)
            availability=self._version('availability_versions',sid,at)
            buy,sell=availability.get('buy_allowed'),availability.get('sell_allowed')
            if self.execution_mode=='UNKNOWN_NO_FILL':buy=sell=None
            cap=int(prior.mean()*float(self.protocol['participation_rate']))
            op=D(str(f.loc[day,'open']));slip=D(self.protocol['daily_execution']['A']['slippage_bps'])/D(10000)
            if cost_multiplier==2 and self.protocol['daily_execution']['A']['stress_slippage']:slip*=2
            price=op*(1+slip if side=='buy' else 1-slip)
            w=ledger.FillWindow(f'{sid}:{at.isoformat()}:{side}',sid,at,op,price,self.rate('CNY',at),qrule,fees,cap,True,buy,sell,self.lag('A',at,self.protocol['sellable_lag_sessions']['A']),self.lag('A',at,self.protocol['settlement_lag_sessions']['A']),self.bundle.series[sid].record['raw']['sha256'],self.execution_mode+'_ONLY_O_AND_PRIOR_VOLUME_TRADABILITY_UNKNOWN',self.rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
            w.validate();self.open_window_cache[key]=w
            self.execution_audit.append(dict(sid=sid,side=side,at=at,open=op,capacity=cap,buy_allowed=buy,sell_allowed=sell,volume_source_last=str(prior.index[-1].date()),volume_observations=len(prior),historical_execution_status='UNKNOWN',assumption=self.execution_mode))
            return w
    m=copy(original);m.__class__=OpenOnlyMarket;m.open_at=open_at;m.execution_mode=mode
    m.open_window_cache={};m.open_mark_cache={};m.execution_audit=[]
    m.cache_at=None;m._fx_cache={};m.mark_verified=set();m.window_verified=set()
    m.raw={};day=pd.Timestamp(open_at.date())
    for sid,f in original.raw.items():
        g=f.loc[:day].copy()
        if day in g.index:
            for c in ('high','low','close','volume','amount'):
                if c in g.columns:g.loc[day,c]=np.nan if variant=='MASKED' else (1e30 if c!='low' else -1e30)
            for c in ('valid_price','price_eligible','volume_eligible','observed_bar','is_observed_bar'):
                if c in g.columns:g.loc[day,c]=variant=='POISONED'
        m.raw[sid]=g
    m.arr={}  # Any accidentally inherited fast array path fails instead of leaking.
    return m

