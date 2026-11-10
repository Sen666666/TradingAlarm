"""Entry semantics, selected real decision identity and holding independence."""
import sys
import pandas as pd
import numpy as np
from dataclasses import replace
from util_ix import *
from entry_rules import events
sys.path.append(str(OLD/'code'))
import selection_adapter as adapter
import current_fixed_pool as pool
from current_pool_bridge import load_bundle,load_prepared_states
from market_runner import FrozenMarket,iso

def main():
 checks=[]
 def check(name,ok):
  checks.append(dict(name=name,passed=bool(ok)))
  if not ok:raise AssertionError(name)
 ix=pd.bdate_range('2020-01-01',periods=14)
 grade=[0,2,3,3,4,3,2,4,-2,3,2,np.nan,3,4]
 g=pd.DataFrame(dict(grade=grade,segment_id='A',ready=[np.isfinite(x) for x in grade]),index=ix)
 state=pd.DataFrame(dict(buy_event=True),index=ix);e=events(g,state)
 check('strict_warm_to_hot',[*np.flatnonzero(e.W23)]==[2,12])
 check('warm_jump_to_expansion',[*np.flatnonzero(e.W2H)]==[2,7,12])
 check('cross_hot_includes_cold_jump',[*np.flatnonzero(e.C3)]==[2,7,9,12])
 check('no_static_hot_buy',not e.W23.iloc[3] and not e.C3.iloc[3])
 check('cool_expansion_to_hot_not_buy',not e.C3.iloc[5])
 check('hot_to_expansion_not_new_hot_cross',not e.C3.iloc[4])
 check('strict_subset_jump_subset_cross',((~e.W23|e.W2H)&(~e.W2H|e.C3)&(~e.C3|e.IX)).all())
 g2=g.copy();g2.loc[ix[12]:,'segment_id']='B';z=events(g2,state);check('source_reset_no_fake_transition',not z.W23.iloc[12])
 state.loc[ix[2],'buy_event']=False;z=events(g,state);check('E0_or_IX_not_valid_rejects_transition',not z.W23.iloc[2])
 for n in [2,4,9,12]:pd.testing.assert_frame_equal(events(g.iloc[:n],state.iloc[:n]),events(g,state).iloc[:n],check_exact=True)
 check('entry_definitions_prefix',True)
 # Deterministic dates selected before any new account. All static facts,
 # ranks, histories and clock are exactly those of the original frozen runner.
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2')
 m=FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 for day in ['2015-01-05','2020-12-31','2026-10-22']:
  at=iso(day+'T15:10:00+08:00');clock=pool.admission.Clock(at,m.lag('A',at,1),at.date());inputs=b.at_decision(clock,market_buyable=m.market_buyable(at))
  adapter.configure('E0',{})
  for variant in ['T0','T1','S0','S1']:
   kwargs=dict(evidence=inputs.evidence,lines=inputs.lines,historical=inputs.historical,sectors=inputs.sectors,clock=clock,variant=variant,bootstrap=True)
   a=pool.decide_current_pool(**kwargs);z=adapter.decide_current_pool(**kwargs);check(f'{day}:{variant}:cached_facts_identity',a==z)
  # A held security with genuine True holding trend must not be sold merely
  # because no current entry event exists. Gate is buyability, not trend.
  candidate=next(h for h in inputs.historical if h.trend_up.read(clock) is True and next(x for x in inputs.lines if x.security_id==h.security_id).company_cap_cny is not None)
  line=next(x for x in inputs.lines if x.security_id==candidate.security_id)
  occ=pool.admission.Occupancy(line.security_id,line.issuer_id,line.sector_id,at,has_position=True)
  adapter.configure('W23',{})
  z=adapter.decide_current_pool(evidence=inputs.evidence,lines=inputs.lines,historical=inputs.historical,sectors=inputs.sectors,clock=clock,variant='T0',occupied=(occ,),bootstrap=True).decision
  check(day+':no_entry_event_does_not_sell_held',line.security_id not in z.exit_requests)
  check(day+':no_entry_event_no_selected',not z.selected)
 write(HERE/'validation/tests.json',dict(recorded_at=now(),passed=True,checks=len(checks),details=checks,new_economic_accounts=0))
 print(dict(passed=True,checks=len(checks)),flush=True)

if __name__=='__main__':main()
