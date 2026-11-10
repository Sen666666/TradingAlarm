import unittest
import numpy as np
import pandas as pd
from sector_experiment import fast_gate,rotation_allocator
class SectorTests(unittest.TestCase):
 def test_future_change_cannot_change_gate_history(self):
  idx=pd.date_range('2020-01-01',periods=220)
  a=pd.DataFrame({'close':100+np.sin(np.arange(220)/8)*10+np.arange(220)/5},index=idx)
  b=a.copy();b.iloc[160:]*=10
  pd.testing.assert_series_equal(fast_gate(a).iloc[:160],fast_gate(b).iloc[:160])
 def test_sector_duplicate_and_cash_slots(self):
  names=['a','b','c','d'];idx=pd.date_range('2020-01-01',periods=160)
  rng=np.random.default_rng(9)
  r=pd.DataFrame(rng.normal(.001,.01,(160,4)),columns=names,index=idx)
  assets={n:{'kind':'equity','sector':'same' if n in ['a','b'] else n,'currency':'CNY'} for n in names}
  w,_=rotation_allocator(r,{n:True for n in names},assets)
  self.assertLessEqual(int((w[['a','b']]>0).sum()),1)
  self.assertLessEqual(w.sum(),.6+1e-10)
  self.assertTrue((w<=.2+1e-10).all())
  zero,_=rotation_allocator(r,{n:False for n in names},assets)
  self.assertEqual(zero.sum(),0)
class BufferTests(unittest.TestCase):
 def test_buffer_skips_resize_but_preserves_full_exit(self):
  from unittest.mock import patch
  from portfolio_engine import run_portfolio
  idx=pd.bdate_range('2020-01-01',periods=300)
  raw=pd.DataFrame({c:100. for c in ['open','high','low','close']},index=idx)
  a=dict(raw=raw,signal=raw,splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test')
  def allocator(r,*args):
   end=r.index[-1]
   weight=.2 if end<idx[270] else (.21 if end<idx[285] else 0.)
   return pd.Series({'a':weight}),[['a']]
  with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)):
   _,_,orders,_=run_portfolio({'a':a},start=str(idx[260].date()),passive=True,guard=False,cost_bps=0,fx_bps=0,allocator_fn=allocator,rebalance_band=.02)
  self.assertEqual(len(orders),2)
  self.assertEqual(orders[0]['units'],-orders[1]['units'])
  self.assertGreater(orders[0]['units'],0)
if __name__=='__main__':unittest.main()
