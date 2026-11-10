"""Original admission kernel with per-account causal entry/rank substitutions."""
from dataclasses import replace
import types,math
import sector_stock_admission as admission
import current_fixed_pool as pool

BUY={};BOARD=None;_datekey=None;_facts={};_elig={};_mode='A';_banned_stocks=set();_banned_sectors=set();_row=None
def configure(buy,board):
 global BUY,BOARD,_datekey
 BUY=buy;BOARD=board;_datekey=None
def set_account(mode,banned_stocks=(),banned_sectors=()):
 global _mode,_banned_stocks,_banned_sectors
 _mode=mode;_banned_stocks=set(banned_stocks);_banned_sectors=set(banned_sectors)
def _and(*values):return None if any(v is None for v in values) else all(values)
def facts(inputs,clock,mode):
 return market_facts(inputs.evidence,inputs.lines,inputs.historical,inputs.sectors,clock,mode)
def market_facts(evidence,lines,historical,sectors,clock,mode):
 global _datekey,_facts,_elig,_row
 key=(clock.decision_at,id(historical),id(sectors))
 if key!=_datekey:_datekey=key;_facts={};_elig={};_row=BOARD.at(clock.session_date)
 kind='dual' if mode in ['B','D'] else 'old'
 if kind not in _facts:
  fixed={x.security_id:x for x in lines};dynamic={x.security_id:x for x in historical};assert fixed.keys()==dynamic.keys()
  sec={x.sector_id:x for x in sectors};stocks={sid:pool.build_security(fixed[sid],dynamic[sid],evidence) for sid in sorted(fixed)}
  if kind=='dual':
   for sid,s in stocks.items():
    score=_row.get(sid,'rank')
    if math.isfinite(score):stocks[sid]=replace(s,rank=admission.Rank(score,clock.decision_at,clock.decision_at))
   for sid,s in sec.items():
    score=_row.get(sid,'rank')
    if math.isfinite(score):sec[sid]=replace(s,rank=admission.Rank(score,clock.decision_at,clock.decision_at))
  _facts[kind]=(stocks,sec)
 return (*_facts[kind],_row)
def eligibility(s,sectors,clock,variant):
 kind='dual' if _mode in ['B','D'] else 'old';k=(kind,s.security_id,variant)
 sector=s.sector_id.read(clock);banned=s.security_id in _banned_stocks or sector in _banned_sectors
 if k not in _elig or banned:
  market=s.buy_allowed.read(clock,for_execution=True);fresh=s.security_id in BUY.get(clock.session_date.isoformat(),set())
  values=[market,fresh]
  if kind=='dual':values += [_row.allowed(s.security_id),_row.allowed(sector)]
  if banned:values.append(False)
  fact=admission.Fact(_and(*values),clock.decision_at,clock.decision_at,source_id='ABCD:causal-entry-computation-current-pool-assumption')
  answer=admission.eligibility(replace(s,buy_allowed=fact),sectors,clock,variant)
  if banned:return answer
  _elig[k]=answer
 return _elig[k]
_globals=dict(admission.decide.__globals__,eligibility=eligibility)
_decide=types.FunctionType(admission.decide.__code__,_globals,'abcd_unchanged_admission',admission.decide.__defaults__,admission.decide.__closure__);_decide.__kwdefaults__=admission.decide.__kwdefaults__
def decide_current_pool(*,evidence,lines,historical,clock,variant,sectors,previous=(),occupied=(),bootstrap=False,completed_exits=(),entry_mode='A'):
 global _mode
 _mode=entry_mode;stocks,sec,row=market_facts(evidence,lines,historical,sectors,clock,entry_mode)
 result=_decide(clock=clock,variant=variant,securities=tuple(stocks.values()),sectors=tuple(sec.values()),previous=previous,occupied=occupied,bootstrap=bootstrap,completed_exits=completed_exits)
 return pool.CurrentPoolDecision(evidence,result)
