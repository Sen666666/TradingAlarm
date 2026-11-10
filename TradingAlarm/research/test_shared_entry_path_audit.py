import unittest
import pandas as pd
from shared_entry_path_audit import episode_marks,match_cash_blend
class Tests(unittest.TestCase):
 def test_partial_fills_fees_and_marked_excursion(self):
  d=pd.bdate_range('2024-01-01',periods=4);marks=pd.Series([10.,12.,15.,9.],index=d)
  orders=[dict(date=str(d[0].date()),units=10.,raw_open=10.,fee=1.),dict(date=str(d[1].date()),units=5.,raw_open=11.,fee=1.),dict(date=str(d[3].date()),units=-15.,raw_open=9.,fee=1.)]
  p,b=episode_marks(orders,marks);self.assertEqual(b,157.);self.assertEqual(p.tolist(),[-1.,23.,68.,-23.])
 def test_blend_matches_known_constant_exposure(self):
  p=pd.DataFrame({'nav':[1.,1.,1.],'cash':[.2e6,.2e6,.2e6]})
  a,n,e=match_cash_blend(p,.4);self.assertAlmostEqual(a,.5);self.assertAlmostEqual(e,.4);self.assertTrue(n.eq(1).all())
if __name__=='__main__':unittest.main()
