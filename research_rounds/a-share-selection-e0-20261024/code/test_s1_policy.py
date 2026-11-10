"""Economic policy boundaries for S1, with no historical account execution."""
from pathlib import Path
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
import importlib.util,sys,unittest
import sector_stock_admission as a
from sector_account import SectorAccount
from test_sector_account import quote,marks,CLOCK as LEDGER_CLOCK,T as LEDGER_T

T=datetime(2020,1,2,9,tzinfo=timezone.utc)
clock=a.Clock(T,T+timedelta(days=1),T.date())

def setup(mod=a,groups=('G0',)*7+('G1',)*2,score0=2.,score1=1.):
 f=lambda value:mod.Fact(value,T,T,source_id='synthetic')
 sectors=[mod.Sector('G0',f(True),mod.Rank(score0,T,T)),mod.Sector('G1',f(True),mod.Rank(score1,T,T))]
 stock=[mod.Security(f'S{i}',f(f'I{i}'),f(g),f(True),f(True),f(20e9),f(True),mod.Rank(10.-i/10,T,T)) for i,g in enumerate(groups)]
 return stock,sectors

class SingleSectorTests(unittest.TestCase):
 def test_six_from_strongest_only_and_no_fallback_to_second(self):
  stocks,sectors=setup();d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,bootstrap=True)
  self.assertEqual(d.selected,tuple(f'S{i}' for i in range(6)))
  self.assertIn(('S7','not_top_ranked_sector'),d.rejected)
  stocks,sectors=setup(groups=('G0','G1','G1'))
  d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,bootstrap=True)
  self.assertEqual(d.selected,('S0',))

 def test_strongest_sector_with_no_eligible_stock_means_cash(self):
  stocks,sectors=setup(groups=('G1',)*6)
  d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,bootstrap=True)
  self.assertEqual(d.selected,())
  self.assertEqual(len(d.waiting),6)

 def test_rank_rotation_does_not_sell_but_old_sector_blocks_second(self):
  stocks,sectors=setup(score0=1.,score1=2.)
  occ=[a.Occupancy('S0','I0','G0',T,has_position=True)]
  d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,occupied=occ,bootstrap=True)
  self.assertEqual(d.exit_requests,())
  self.assertEqual(d.selected,())
  self.assertIn(('S7','sector_slots_full'),d.rejected)

 def test_partial_buy_keeps_frozen_commitment_when_sector_loses_top_rank(self):
  stocks,sectors=setup(score0=1.,score1=2.)
  occ=[a.Occupancy('S0','I0','G0',T,has_position=True,pending_buy=True,partial_fill=True)]
  d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,occupied=occ,bootstrap=True)
  self.assertIn('S0',d.continue_buys);self.assertEqual(d.cancel_buys,())

 def test_unknown_sector_rs_uses_declared_group_id_fallback(self):
  stocks,sectors=setup(score0=None,score1=3.)
  d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,bootstrap=True)
  self.assertTrue(all(int(s[1:])<7 for s in d.selected))
  self.assertIn('S1:all_up_sectors',d.ranking_fallbacks)

 def test_ledger_commits_six_at_same_15pct_budget_and_rejects_seventh(self):
  # Separate allocator guard verifies that recommendations cannot bypass money
  # and capacity just because the admission module recommended six.
  stocks,sectors=setup();d=a.decide(clock=clock,variant='S1',securities=stocks,sectors=sectors,bootstrap=True)
  qs={s.security_id:quote(sid=s.security_id,issuer=f'I{i}',sector='G0') for i,s in enumerate(stocks)}
  acct=SectorAccount(max_sectors=1,max_issuers_per_sector=6)
  c=a.Clock(LEDGER_T,LEDGER_T+timedelta(days=1),LEDGER_T.date())
  # Facts use a later synthetic clock; only reuse the policy's structural result
  # with a matching ledger cutoff and its original creation records.
  d=replace(d,decision_at=LEDGER_T,memories=tuple(replace(m,created_at=LEDGER_T,as_of=LEDGER_T) for m in d.memories))
  ack=acct.apply_decision(d,clock=c,quotes=qs,marks={})
  self.assertEqual(len(ack.accepted),6)
  self.assertTrue(all(o.budget_cny==150000 for o in acct.buys.values()))
  seventh=acct.apply_decision(replace(d,selected=('S6',)),clock=c,quotes=qs,marks={})
  self.assertEqual(seventh.rejected,(('S6','capacity_already_committed'),))

 def test_original_three_policies_match_original_adapter(self):
  path=Path(__file__).resolve().parents[3]/'research_rounds/sector-stock-20261021/code/sector_stock_admission.py'
  spec=importlib.util.spec_from_file_location('original_admission_control',path);original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
  for variant in ['T0','T1','S0']:
   ns,ng=setup();os,og=setup(original)
   oc=original.Clock(T,T+timedelta(days=1),T.date())
   now=a.decide(clock=clock,variant=variant,securities=ns,sectors=ng,bootstrap=True)
   old=original.decide(clock=oc,variant=variant,securities=os,sectors=og,bootstrap=True)
   self.assertEqual(asdict(now),asdict(old),variant)

if __name__=='__main__':unittest.main()
