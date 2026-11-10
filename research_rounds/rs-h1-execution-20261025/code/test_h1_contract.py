"""Behavior regressions for the two diagnosed defects, no historical accounts."""
import unittest
from dataclasses import replace
from datetime import timedelta
import sector_stock_admission as a
from test_sector_account import T,CLOCK,quote,window,marks
from sector_account import SectorAccount,commit_cutoff

def fact(x,at=T):return a.Fact(x,at,at,observed_at=at)
def stock(sid,score):return a.Security(sid,fact(sid),fact('G'),fact(True),fact(True),fact(20e9),fact(True),a.Rank(score,T,T))
def sector(score=80):return a.Sector('G',fact(True),a.Rank(score,T,T))
def decide(xs,**kw):return a.decide(clock=CLOCK,variant='T0',securities=xs,sectors=[sector()],bootstrap=True,**kw)
class Contract(unittest.TestCase):
 def test_unknown_does_not_code_sort_known_batch(self):
  d=decide([stock('000',None),stock('001',10),stock('999',90)])
  self.assertEqual(d.selected,('999','001'));self.assertIsNone(d.eligibility[0].q);self.assertEqual(d.ranking_fallbacks,())
 def test_first_unknown_to_known_not_lost(self):
  unknown=decide([stock('A',None)])
  d=a.decide(clock=CLOCK,variant='T0',securities=[stock('A',70)],sectors=[sector()],previous=unknown.memories)
  self.assertEqual(d.selected,('A',))
 def test_missing_rank_is_not_holding_exit(self):
  o=a.Occupancy('A','A','G',T,has_position=True)
  d=decide([stock('A',None)],occupied=[o]);self.assertFalse(d.exit_requests);self.assertFalse(d.selected)
 def test_daily_expiry_without_stock_bar_releases_all(self):
  acc=SectorAccount();acc.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=150000)
  self.assertEqual(acc.expire_day_buys(T+timedelta(days=1,hours=8)),{'A'})
  self.assertEqual(acc.available,acc.initial_cash);self.assertFalse(acc.occupancy(T+timedelta(days=1,hours=8)))
 def test_expiry_not_before_scheduled_session(self):
  acc=SectorAccount();acc.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=150000)
  self.assertFalse(acc.expire_day_buys(T));self.assertIn('A',acc.buys)
 def test_partial_expiry_keeps_filled_no_topup(self):
  acc=SectorAccount();acc.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=150000)
  self.assertEqual(acc.fill_buy('A',window(capacity=100)).shares,100)
  self.assertFalse(acc.expire_day_buys(T+timedelta(days=1,hours=8)));self.assertEqual(acc.quantity('A'),100);self.assertFalse(acc.buys)
 def test_expired_stock_competes_again_without_priority(self):
  d=decide([stock('A',10)]);old=replace(d.memories[0],waiting=True,origin='expired_unfilled_recompetition')
  xs=[stock('A',10),stock('B',99),stock('C',80)]
  d=a.decide(clock=CLOCK,variant='T0',securities=xs,sectors=[sector()],previous=[old],bootstrap=False)
  self.assertEqual(d.selected,('B','C'));self.assertIn(('A','sector_issuer_slots_full'),d.rejected)
 def test_delay_credit_only_after_eligible_event(self):
  acc=SectorAccount(delay_events=1);acc.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=150000)
  self.assertIsNone(acc.fill_buy('A',window()))
  acc.expire_day_buys(T+timedelta(days=1,hours=8));self.assertEqual(acc.daily_delay_credit,{'A'})
  at=T+timedelta(days=1,hours=8);c=a.Clock(at,T+timedelta(days=2),at.date())
  acc.reserve_budget(quote=quote(),clock=c,gross_budget_cny=150000);self.assertEqual(acc.buys['A'].delay_remaining,0)
  self.assertIsNotNone(acc.fill_buy('A',window(at=T+timedelta(days=2),eid='open2')))
 def test_no_window_no_delay_credit(self):
  acc=SectorAccount(delay_events=1);acc.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=150000)
  acc.expire_day_buys(T+timedelta(days=1,hours=8));self.assertFalse(acc.daily_delay_credit)
 def test_rank_drop_cannot_rotate_held_stock(self):
  d=decide([stock('A',1),stock('B',99),stock('C',80)],occupied=[a.Occupancy('A','A','G',T,has_position=True)])
  self.assertFalse(d.exit_requests);self.assertEqual(d.selected,('B',))
 def test_sector_unknown_is_local_to_sector(self):
  s=stock('A',90);s=replace(s,sector_id=fact('X'))
  d=a.decide(clock=CLOCK,variant='S0',securities=[s,stock('B',80)],sectors=[sector(),a.Sector('X',fact(True),a.Rank(None,T,T))],bootstrap=True)
  self.assertEqual(d.selected,('B',));self.assertFalse(d.ranking_fallbacks)
 def test_genuine_tie_stable_id(self):
  self.assertEqual(decide([stock('Z',50),stock('A',50)]).selected,('A','Z'))
if __name__=='__main__':unittest.main()
