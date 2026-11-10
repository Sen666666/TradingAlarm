"""Identical frozen market facts with array lookups and cached next sessions."""
from common import *
from bisect import bisect_right
from datetime import time
from decimal import Decimal as D
from market_rules import market_identity_on,RuleUnavailable

class FastMarket(native.FrozenMarket):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.arr={};self.sessions_set={m:set(x) for m,x in self.sessions.items()};self.session_days={m:[x.date() for x in xs] for m,xs in self.sessions.items()};self.cache_at=None;self.window_identity_checks=0;self.mark_identity_checks=0;self.mark_verified=set();self.window_verified=set()
  for sid,f in self.raw.items():
   assert self.lines[sid].market=='A'
   v=f.volume.to_numpy(float);ok=f.valid_price.to_numpy(bool)&f.observed_bar.to_numpy(bool)
   self.arr[sid]=dict(days=f.index.as_unit('ns').asi8//86400000000000,open=f.open.to_numpy(float),high=f.high.to_numpy(float),low=f.low.to_numpy(float),close=f.close.to_numpy(float),volume=v,valid=f.valid_price.to_numpy(bool),good=np.flatnonzero(ok),positive=np.flatnonzero(np.isfinite(v)&(v>0)),close_time=time.fromisoformat(self.bundle.series[sid].record['close_available_time']))
 def _cache(self,at):
  if self.cache_at!=at:self.cache_at=at;self.mc={};self.qc={};self.wc={};self.fc={};self.qrc={}
 def lag(self,market,at,count):
  if count==0:return at
  j=bisect_right(self.session_days[market],at.date())+count-1
  if j>=len(self.sessions[market]):raise RuleUnavailable('Calendar does not cover settlement')
  return self.sessions[market][j]
 def quantity(self,sid,at):
  self._cache(at)
  if sid not in self.qrc:self.qrc[sid]=super().quantity(sid,at)
  return self.qrc[sid]
 def fees(self,sid,at):
  self._cache(at)
  if sid not in self.fc:self.fc[sid]=super().fees(sid,at)
  return self.fc[sid]
 def latest_mark(self,sid,at):
  self._cache(at)
  if sid in self.mc:return self.mc[sid]
  self.source_available(sid,at);a=self.arr[sid];day=pd.Timestamp(at.date()).value//86400000000000;i=np.searchsorted(a['days'][a['good']],day,side='right')-1
  if i<0:return super().latest_mark(sid,at)
  p=a['good'][i];d=pd.Timestamp(int(a['days'][p])*86400000000000).date();known=datetime.combine(d,a['close_time'],native.TZ)
  if known>at or any(d.isoformat()<e['effective_date']<=at.date().isoformat() for e in self.actions.get(sid,())):m=super().latest_mark(sid,at)
  else:m=ledger.Mark(D(str(a['close'][p])),known,self.rate('CNY',at),self.bundle.series[sid].record['raw']['sha256'])
  if sid not in self.mark_verified:
   assert m==super().latest_mark(sid,at),(sid,at,'mark identity');self.mark_identity_checks+=1;self.mark_verified.add(sid)
  self.mc[sid]=m;return m
 def quote(self,sid,at):
  self._cache(at)
  if sid not in self.qc:self.qc[sid]=super().quotes(at,[sid]).get(sid)
  return self.qc[sid]
 def window(self,sid,at,side,cost_multiplier):
  self._cache(at);key=(sid,side,cost_multiplier)
  if key in self.wc:return self.wc[key]
  self.wc[key]=None;market=self.lines[sid].market
  if at not in self.sessions_set[market]:return None
  try:self.source_available(sid,at)
  except RuleUnavailable:return None
  a=self.arr[sid];day=pd.Timestamp(at.date()).value//86400000000000;p=np.searchsorted(a['days'],day)
  if p>=len(a['days']) or a['days'][p]!=day or not a['valid'][p] or not np.isfinite(a['volume'][p]) or a['volume'][p]<=0:return None
  j=np.searchsorted(a['positive'],p)
  if j<20:return None
  try:
   market_identity_on(self.rules,sid,at.date(),self.protocol['approved_proxy_ids']);availability=self._version('availability_versions',sid,at);buy,sell=availability.get('buy_allowed'),availability.get('sell_allowed');policy=self.protocol['daily_execution'][market]
   assert policy['price_limit_policy']=='conservative_hl_proxy'
   if policy['reject_flat_day'] and a['high'][p]<=a['low'][p]:buy=sell=False
   prior=a['volume'][a['positive'][j-20:j]];capacity=int(min(prior.mean()*float(self.protocol['participation_rate']),a['volume'][p]));slip=D(policy['slippage_bps'])/10000
   if cost_multiplier==2 and policy['stress_slippage']:slip*=2
   op=D(str(a['open'][p]));price=op*(1+slip if side=='buy' else 1-slip)
   w=ledger.FillWindow(f'{sid}:{at.isoformat()}:{side}',sid,at,op,price,self.rate('CNY',at),self.quantity(sid,at),self.fees(sid,at),capacity,True,buy,sell,self.lag(market,at,self.protocol['sellable_lag_sessions'][market]),self.lag(market,at,self.protocol['settlement_lag_sessions'][market]),self.bundle.series[sid].record['raw']['sha256'],'explicit_daily_bar_proxy_past20_capacity_same_day_hlv_postcheck',self.rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
  except RuleUnavailable:return None
  if key not in self.window_verified:
   assert w==super().window(sid,at,side,cost_multiplier),(sid,at,'window identity');self.window_identity_checks+=1;self.window_verified.add(key)
  self.wc[key]=w;return w
