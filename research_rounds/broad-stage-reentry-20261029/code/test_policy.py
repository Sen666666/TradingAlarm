import unittest
from decimal import Decimal as D
from types import SimpleNamespace as S
import pandas as pd
from policy import support_cache, advance

def layer(kind='trial',floor=90,cost=100):
    x=dict(kind=kind,floor=D(floor),entry_cost=D(cost),opened='2025-01-02T09:30:00+08:00',phase='TRIAL')
    if kind=='core':x.update(bridge_floor=D(floor),phase='CORE_BRIDGE')
    return x
def f(price,date='2025-01-03'):return S(event=1,pivot=price,pivot_date=date)
def cp(price):return S(receipt=True,candidate=price)

class Policy(unittest.TestCase):
    def test_old_line_wins_over_same_day_recovery(self):
        x=layer(floor=105);self.assertEqual(advance(x,'2025-01-03',D(104),D(90),f(106),cp(108)),'exit');self.assertEqual(x['floor'],105)
    def test_f_promotes_without_cp(self):
        x=layer();self.assertEqual(advance(x,'2025-01-03',D(120),D(95),f(104),None),'promote');self.assertEqual(x['bridge_floor'],104)
    def test_cp_promotes_without_pullback(self):
        x=layer();self.assertEqual(advance(x,'2025-01-03',D(120),D(95),None,cp(104)),'promote')
    def test_candidate_not_above_cost_does_not_promote(self):
        x=layer();advance(x,'2025-01-03',D(110),D(95),f(100),cp(99));self.assertEqual(x['kind'],'trial');self.assertEqual(x['floor'],100)
    def test_pre_entry_pivot_does_not_promote(self):
        x=layer();advance(x,'2025-01-03',D(120),D(95),f(110,'2025-01-01'),None);self.assertEqual(x['kind'],'trial')
    def test_core_stops_fast_updates(self):
        x=layer('core',104);advance(x,'2025-01-04',D(150),D(120),f(140),cp(145));self.assertEqual(x['floor'],120);self.assertEqual(x['phase'],'CORE_TREND')
    def test_bridge_never_drops(self):
        x=layer('core',110);advance(x,'2025-01-04',D(120),D(95),None,None);self.assertEqual(x['floor'],110);self.assertEqual(x['phase'],'CORE_BRIDGE')
    def test_mobile_remains_mobile(self):
        x=layer('mobile');advance(x,'2025-01-04',D(150),D(95),None,cp(130));self.assertEqual(x['kind'],'mobile');self.assertEqual(x['floor'],130)
    def test_support_invalidation_and_prefix(self):
        ix=pd.date_range('2025-01-01',periods=5)
        facts=pd.DataFrame(dict(i_target=[1,1,1,1,1],segment_id=[0]*5,close=[100,110,99,115,120]),index=ix)
        fine=pd.DataFrame(dict(event=[0,1,0,0,1],pivot=[None,100,None,None,105],pivot_date=[None,'2025-01-01',None,None,'2025-01-04']),index=ix)
        c=pd.DataFrame(dict(receipt=[0,1,0,0,1],candidate=[None,101,None,None,110]),index=ix)
        full=support_cache(facts,fine,c)
        self.assertTrue(pd.isna(full.iloc[2].f_valid));self.assertTrue(pd.isna(full.iloc[3].cp_valid))
        pd.testing.assert_frame_equal(full.iloc[:4],support_cache(facts.iloc[:4],fine.iloc[:4],c.iloc[:4]))
    def test_source_and_i_reset_reject_prior_pivot(self):
        ix=pd.date_range('2025-01-01',periods=4)
        facts=pd.DataFrame(dict(i_target=[1,0,1,1],segment_id=[0,0,1,1],close=[100,105,110,115]),index=ix)
        fine=pd.DataFrame(dict(event=[1,0,1,1],pivot=[90,None,100,108],pivot_date=['2025-01-01',None,'2025-01-01','2025-01-03']),index=ix)
        c=pd.DataFrame(dict(receipt=[1,0,0,0],candidate=[90,None,None,None]),index=ix)
        z=support_cache(facts,fine,c);self.assertTrue(pd.isna(z.iloc[2].f_valid));self.assertTrue(pd.isna(z.iloc[2].cp_valid));self.assertEqual(z.iloc[3].f_valid,108)

if __name__=='__main__':unittest.main()
