"""Original S1 qualification, original stock RS, one externally fixed pool.

The original S1 grouping branch consumes original S1 qualification.
The one externally fixed scope is an allocation identity, not a market trend.
"""
from sec_common import *
from dataclasses import replace
import types
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'));sys.path.append(str(PREV/'code'))
import sector_stock_admission as adm
import current_fixed_pool as pool
import finance_ladder as fl
CURRENT={};CACHE={};SCOPE=None;SIGNALS={};BUY={};REFERENCE={};Q_CHECKS=0

def original_eligibility(s,sectors,clock,variant):return CURRENT[s.security_id]
_decide=types.FunctionType(adm.decide.__code__,dict(adm.decide.__globals__,eligibility=original_eligibility),'fixed_scope_original_capacity',adm.decide.__defaults__,adm.decide.__closure__);_decide.__kwdefaults__=adm.decide.__kwdefaults__

def configure(scope,signals,reference):
 global SCOPE,SIGNALS,BUY,REFERENCE
 SCOPE=scope;SIGNALS=signals;REFERENCE=reference;BUY=collections_buy(signals);CACHE.clear()
def collections_buy(signals):
 from collections import defaultdict
 r=defaultdict(set)
 for sid,f in signals.items():
  for d in f.index[f.IX.astype(bool)]:r[str(d.date())].add(sid)
 return r

def decide(*,evidence,lines,historical,clock,variant,sectors,entry_mode,**kw):
 global CURRENT,Q_CHECKS
 group,policy=entry_mode.split('_');key=(clock.decision_at,policy)
 if len(CACHE)>2:CACHE.clear()
 if key not in CACHE:
  ss={x.sector_id:x for x in sectors};hh={x.security_id:x for x in historical};stocks={};elig={};day=str(clock.session_date)
  for l in lines:
   h=hh[l.security_id];f=SIGNALS[l.security_id];pos=f.index.searchsorted(day,side='right')-1
   if policy=='I' and h.trend_up.read(clock) is not None:
    fact=replace(h.trend_up,value=bool(f.i_target.iloc[pos]));h=replace(h,trend_up=fact)
   s=pool.build_security(l,h,evidence);allowed=s.buy_allowed.read(clock,for_execution=True);fresh=l.security_id in BUY.get(day,set());value=None if allowed is None else bool(allowed and fresh);s=replace(s,buy_allowed=adm.Fact(value,clock.decision_at,clock.decision_at,source_id='same_original_IX_buy_event'))
   e=adm.eligibility(s,ss,clock,'S1');stocks[l.security_id]=s;elig[l.security_id]=e
   if policy=='IX' and START<=day<=END:
    assert (e.q is True)==(day in REFERENCE.get(l.security_id,set())),(l.security_id,day,e);Q_CHECKS+=1
  CACHE[key]=(stocks,ss,elig)
 stocks,ss,elig=CACHE[key];ids=SCOPE['groups'][group];gid=GROUPS[group][1];CURRENT={s:replace(elig[s],sector_id=gid) for s in ids};selected=[replace(stocks[s],sector_id=replace(stocks[s].sector_id,value=gid)) for s in ids]
 if group=='DRUG':
  # This single namespace is already selected externally. Its rank/trend
  # only keep S1's one-pool capacity branch; q above remains the real
  # original member-industry q and never reads these identity constants.
  template=next(iter(ss.values()));allocation_scope=replace(template,sector_id=gid,trend_up=adm.Fact(True,clock.decision_at,clock.decision_at,source_id='external_fixed_scope_identity_only'),rank=adm.Rank(0.,clock.decision_at,clock.decision_at))
 else:allocation_scope=ss[gid]
 d=_decide(clock=clock,variant='S1',securities=tuple(selected),sectors=(allocation_scope,),**kw)
 return pool.CurrentPoolDecision(evidence,d)

def quotes(self,at,ids=None):
 q=fl.quotes(self,at,ids)
 if isinstance(q,fl.LazyQuotes):return GroupQuotes(q)
 return {s:remap(s,x) for s,x in q.items()}
def remap(s,q):return replace(q,sector_id=GROUPS['DRUG'][1]) if s in SCOPE['groups']['DRUG'] else q
class GroupQuotes(dict):
 def __init__(self,underlying):super().__init__();self.underlying=underlying
 def materialize(self,s):
  if dict.__contains__(self,s):return
  q=self.underlying.get(s)
  if q is not None:dict.__setitem__(self,s,remap(s,q))
 def get(self,s,default=None):self.materialize(s);return dict.get(self,s,default)
 def __contains__(self,s):self.materialize(s);return dict.__contains__(self,s)
 def __missing__(self,s):self.materialize(s);return dict.__getitem__(self,s)
