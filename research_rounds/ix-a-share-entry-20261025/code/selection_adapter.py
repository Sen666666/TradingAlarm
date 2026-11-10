"""Keep holding trend separate from today's entry event; pure daily caches."""
from dataclasses import replace
import types
import sector_stock_admission as admission
import current_fixed_pool as pool

MODE='E0';BUY_BY_DAY={};_key=None;_securities=None;_eligibility={}
_original_eligibility=admission.eligibility

def cached_eligibility(s,sectors,clock,variant):
    key=(s.security_id,variant)
    if key not in _eligibility:_eligibility[key]=_original_eligibility(s,sectors,clock,variant)
    return _eligibility[key]

# Identical decision bytecode, immutable facts and return values. Only pure
# eligibility calculations are memoized inside one cutoff; no state transition
# or money/position operation is cached. Original module/file stays untouched.
_globals=dict(admission.decide.__globals__,eligibility=cached_eligibility)
_decide=types.FunctionType(admission.decide.__code__,_globals,'cached_fact_decide',admission.decide.__defaults__,admission.decide.__closure__)
_decide.__kwdefaults__=admission.decide.__kwdefaults__

def configure(mode,buy_by_day):
    global MODE,BUY_BY_DAY,_key,_securities,_eligibility
    MODE=mode;BUY_BY_DAY=buy_by_day;_key=None;_securities=None;_eligibility={}

def decide_current_pool(*,evidence,lines,historical,clock,variant,sectors,previous=(),occupied=(),bootstrap=False,completed_exits=()):
    global _key,_securities,_eligibility
    key=(clock.decision_at,id(historical),id(sectors),MODE)
    if key!=_key:
        if MODE!='E0':
            valid=BUY_BY_DAY.get(clock.session_date.isoformat(),set());new=[]
            for h in historical:
                old=h.market_buyable.read(clock,for_execution=True)
                allowed=None if old is None else bool(old and h.security_id in valid)
                gate=admission.Fact(allowed,clock.decision_at,clock.decision_at,observed_at=clock.decision_at,source_id='derived_actual_buyability_AND_'+MODE+'_current_event')
                new.append(replace(h,market_buyable=gate))
            historical=tuple(new)
        fixed={x.security_id:x for x in lines};dynamic={x.security_id:x for x in historical}
        if fixed.keys()!=dynamic.keys():raise ValueError('All fixed lines must remain explicit')
        _securities=tuple(pool.build_security(fixed[sid],dynamic[sid],evidence) for sid in sorted(fixed))
        _eligibility={};_key=key
    decision=_decide(clock=clock,variant=variant,securities=_securities,sectors=sectors,previous=previous,occupied=occupied,bootstrap=bootstrap,completed_exits=completed_exits)
    return pool.CurrentPoolDecision(evidence,decision)
