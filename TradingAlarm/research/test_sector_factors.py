import unittest
import numpy as np
import pandas as pd
from sector_factors import breakout_gate,scores,allocator_factory
class FactorTests(unittest.TestCase):
 def test_long_rank_ignores_most_recent_month(self):
  rng=np.random.default_rng(31)
  r=pd.DataFrame(rng.normal(.001,.01,(300,5)))
  a=scores(r,'long');r.iloc[-21:]=.2
  pd.testing.assert_series_equal(a,scores(r,'long'))
 def test_breakout_uses_prior_channel_and_future_isolation(self):
  idx=pd.bdate_range('2020-01-01',periods=100)
  f=pd.DataFrame({'close':100.,'high':101.,'low':99.},index=idx)
  f.loc[idx[60],'close']=102;f.loc[idx[70],'close']=98
  a=breakout_gate(f)
  self.assertFalse(a.iloc[59]);self.assertTrue(a.iloc[60]);self.assertTrue(a.iloc[69]);self.assertFalse(a.iloc[70])
  f.iloc[80:]*=10
  pd.testing.assert_series_equal(a.iloc[:80],breakout_gate(f).iloc[:80])
 def test_all_policy_is_invariant_to_return_rank(self):
  rng=np.random.default_rng(7);r=pd.DataFrame(rng.normal(.001,.01,(300,6)),columns=list('abcdef'))
  assets={n:dict(kind='equity',sector=n,currency='CNY') for n in r}
  active={n:True for n in r}
  a,_=allocator_factory('none',0)(r,active,assets)
  b,_=allocator_factory('long',0)(r,active,assets)
  pd.testing.assert_series_equal(a,b)
class RankBufferTests(unittest.TestCase):
 def test_retains_rank4_but_exits_rank7_and_ineligible(self):
  from unittest.mock import patch
  names=list('abcdefg');rng=np.random.default_rng(8)
  r=pd.DataFrame(rng.normal(.001,.01,(300,7)),columns=names)
  assets={n:dict(kind='equity',sector=n,currency='CNY') for n in names}
  active={n:True for n in names};policy=allocator_factory('short',3,6)
  with patch('sector_factors.scores',return_value=pd.Series([7,6,5,4,3,2,1],index=names)):
   w,_=policy(r,active,assets);self.assertGreater(w['a'],0)
  with patch('sector_factors.scores',return_value=pd.Series([4,7,6,5,3,2,1],index=names)):
   w,_=policy(r,active,assets);self.assertGreater(w['a'],0);self.assertEqual(w['d'],0)
  with patch('sector_factors.scores',return_value=pd.Series([0,7,6,5,3,2,1],index=names)):
   w,_=policy(r,active,assets);self.assertEqual(w['a'],0);self.assertGreater(w['d'],0)
   active['b']=False;w,_=policy(r,active,assets);self.assertEqual(w['b'],0)
if __name__=='__main__':unittest.main()
