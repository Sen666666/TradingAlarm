import study as S
from study import *
from datetime import datetime,timedelta,timezone
import unittest
fixture=C.import_path('sector_cap_fixture',P.BASE/'code/test_contracts.py')
T=datetime(2024,1,2,15,10,tzinfo=timezone(timedelta(hours=8)))

def data(n=7,same_sector=False,down=False):
 def fact(v):return E.admission.Fact(v,T,T,observed_at=T)
 stocks=[];sectors={}
 for i in range(n):
  sid=f'S{i}';g='G0' if same_sector else f'G{i}';sectors[g]=E.admission.Sector(g,fact(not down),E.admission.Rank(90-i,T,T))
  stocks.append(E.admission.Security(sid,fact(sid),fact(g),fact(True),fact(True),fact(20e9),fact(True),E.admission.Rank(90-i,T,T)))
 return tuple(stocks),tuple(sectors.values()),E.admission.Clock(T,T+timedelta(days=1),T.date())

class CapTests(unittest.TestCase):
 def setUp(self):S.NO_CAPS=True
 def tearDown(self):S.NO_CAPS=False
 def test_original_same_sector_stops_at_two(self):
  ss,gg,c=data(same_sector=True);d=original_decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertEqual(len(d.selected),2)
 def test_six_same_sector_are_admitted(self):
  ss,gg,c=data(same_sector=True);d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertEqual(d.selected,tuple(f'S{i}' for i in range(6)))
 def test_six_distinct_sectors_are_admitted(self):
  ss,gg,c=data();d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertEqual(d.selected,tuple(f'S{i}' for i in range(6)))
 def test_sector_trend_filter_remains(self):
  ss,gg,c=data(down=True);d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertFalse(d.selected)
 def test_total_six_includes_pending_orders(self):
  ss,gg,c=data();occ=tuple(E.admission.Occupancy(f'S{i}',f'S{i}',f'G{i}',T,has_position=False,pending_buy=True) for i in range(3));d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True,occupied=occ);self.assertLessEqual(len(d.selected)+len(occ),6)
 def test_no_new_signal_is_not_created_by_capacity(self):
  ss,gg,c=data();ss=tuple(replace(s,buy_allowed=replace(s.buy_allowed,value=False)) for s in ss);d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertFalse(d.selected)
 def test_missing_rank_still_unknown(self):
  ss,gg,c=data();ss=tuple(replace(s,rank=None) for s in ss);d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);self.assertFalse(d.selected)
 def test_ledger_accepts_six_same_sector_with_original_budget(self):
  ss,gg,c=data(same_sector=True);d=decide(clock=c,variant='S0',securities=ss,sectors=gg,bootstrap=True);a=CapacityAccount();a.facts=fixture.FixedFacts();qs={s.security_id:fixture.quote(sid=s.security_id,sector='G0') for s in ss};ack=a.apply_decision(d,clock=c,quotes=qs,marks={});self.assertEqual(len(ack.accepted),6);self.assertEqual(a.max_sectors,6);self.assertEqual(a.max_issuers_per_sector,6);self.assertGreaterEqual(a.available,0)
  for b in a.buys.values():self.assertLessEqual(b.budget_cny,150000)
 def test_disabled_keeps_ledger_original_caps(self):
  S.NO_CAPS=False;a=CapacityAccount();self.assertEqual((a.max_sectors,a.max_issuers_per_sector),(3,2))

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CapTests))
 if result.wasSuccessful():save(O/'synthetic.json',{'passed':True,'tests':result.testsRun})
 else:sys.exit(1)
