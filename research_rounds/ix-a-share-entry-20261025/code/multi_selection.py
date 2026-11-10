"""Shared immutable market facts; entry gates differ, accounts never share cash."""
from dataclasses import replace
import types
import sector_stock_admission as admission
import current_fixed_pool as pool

BUY={};_key=None;_securities=();_base={};_derived={};_buyable={};_mode='E0'
ORDER=('common_ready','buy_allowed','cap_above_10bn','stock_up','issuer_known','sector_known','stock_rs_ready_fresh','sector_observed_today','sector_rs_ready_fresh','sector_up')

def configure(buy):
 global BUY,_key
 BUY=buy;_key=None

def eligibility(s,sectors,clock,variant):
 key=(s.security_id,variant)
 if key not in _base:_base[key]=admission.eligibility(s,sectors,clock,variant)
 original=_base[key]
 if _mode=='E0' or _buyable[s.security_id] is not True or s.security_id in BUY[_mode].get(clock.session_date.isoformat(),set()):return original
 dk=(_mode,*key)
 if dk not in _derived:
  # A false current entry event adds exactly the original buy_allowed:false
  # check. Unknowns retain precedence; reason ordering follows the old kernel.
  reasons={p.split(':',1)[0]:p.split(':',1)[1] for p in original.reasons};reasons['buy_allowed']='false'
  ordered=tuple(k+':unknown' for k in ORDER if reasons.get(k)=='unknown')+tuple(k+':false' for k in ORDER if reasons.get(k)=='false')
  _derived[dk]=replace(original,q=None if any(v=='unknown' for v in reasons.values()) else False,reasons=ordered)
 return _derived[dk]

_globals=dict(admission.decide.__globals__,eligibility=eligibility)
_decide=types.FunctionType(admission.decide.__code__,_globals,'fixed_decide_cached_market_facts',admission.decide.__defaults__,admission.decide.__closure__);_decide.__kwdefaults__=admission.decide.__kwdefaults__

def decide_current_pool(*,evidence,lines,historical,clock,variant,sectors,previous=(),occupied=(),bootstrap=False,completed_exits=(),entry_mode='E0'):
 global _key,_securities,_base,_derived,_buyable,_mode
 key=(clock.decision_at,id(historical),id(sectors))
 if key!=_key:
  fixed={x.security_id:x for x in lines};dynamic={x.security_id:x for x in historical}
  assert fixed.keys()==dynamic.keys()
  _securities=tuple(pool.build_security(fixed[sid],dynamic[sid],evidence) for sid in sorted(fixed))
  _buyable={s.security_id:s.buy_allowed.read(clock,for_execution=True) for s in _securities}
  _base={};_derived={};_key=key
 _mode=entry_mode
 decision=_decide(clock=clock,variant=variant,securities=_securities,sectors=sectors,previous=previous,occupied=occupied,bootstrap=bootstrap,completed_exits=completed_exits)
 return pool.CurrentPoolDecision(evidence,decision)
