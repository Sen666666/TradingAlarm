"""Compare cached event gating with the explicit unoptimized old decision API."""
import sys
from dataclasses import replace
from util_ix import *
sys.path.append(str(OLD/'code'))
import multi_selection as multi
import sector_stock_admission as a
import current_fixed_pool as pool
from current_pool_bridge import load_bundle,load_prepared_states
from market_runner import FrozenMarket,iso

def main():
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');m=FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'));details=[]
 for day in ['2015-01-05','2026-10-22']:
  at=iso(day+'T15:10:00+08:00');clock=a.Clock(at,m.lag('A',at,1),at.date());inputs=b.at_decision(clock,market_buyable=m.market_buyable(at));ids=sorted(h.security_id for h in inputs.historical)
  buy={mode:{day:set(ids[j::j+2])} for j,mode in enumerate(ENTRY_TYPES)};multi.configure(buy)
  for mode in ['E0']+ENTRY_TYPES:
   hs=[]
   for h in inputs.historical:
    v=h.market_buyable.read(clock,for_execution=True)
    gate=h.market_buyable if mode=='E0' else a.Fact(None if v is None else bool(v and h.security_id in buy[mode][day]),at,at,observed_at=at,source_id='test_explicit_gate')
    hs.append(replace(h,market_buyable=gate))
   for variant in ['T0','T1','S0','S1']:
    kwargs=dict(evidence=inputs.evidence,lines=inputs.lines,sectors=inputs.sectors,clock=clock,variant=variant,bootstrap=True)
    reference=pool.decide_current_pool(historical=tuple(hs),**kwargs);actual=multi.decide_current_pool(historical=inputs.historical,entry_mode=mode,**kwargs)
    assert actual==reference,(day,mode,variant)
    details.append(dict(date=day,entry=mode,variant=variant,entire_decision_exact=True,eligibility_rows=len(reference.decision.eligibility)))
 write(HERE/'validation/multi-decision-identity.json',dict(recorded_at=now(),passed=True,decisions=len(details),eligibility_rows=sum(x['eligibility_rows'] for x in details),details=details,account_runs=0))
 print(dict(passed=True,decisions=len(details)),flush=True)

if __name__=='__main__':main()
