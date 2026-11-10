import unittest
import numpy as np
import pandas as pd
from stock_shadow_portfolio import simulate
class ShadowTests(unittest.TestCase):
 def test_missing_quote_blocks_sale_and_cash_never_negative(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.,'b':100.},index=dates);active=p.notna();active.loc[dates[1],'a']=False
  _,path=simulate(p,active,{dates[0]:['a'],dates[1]:['b'],dates[2]:[]},20)
  self.assertEqual(path.loc[dates[1],'positions'],2);self.assertGreater(path.loc[dates[1],'stale_value'],0);self.assertEqual(path.loc[dates[2],'positions'],0);self.assertTrue(path.cash.ge(0).all())
 def test_future_prices_do_not_affect_prior_nav(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':100.},index=dates);a=p.notna();_,first=simulate(p,a,{dates[0]:['a']},20);p.iloc[200:]=150;_,second=simulate(p,a,{dates[0]:['a']},20)
  pd.testing.assert_frame_equal(first.iloc[:200],second.iloc[:200])
 def test_audit_reconciles_and_does_not_change_results(self):
  dates=pd.bdate_range('2020-01-01',periods=300);p=pd.DataFrame({'a':np.linspace(100,150,300)},index=dates);active=p.notna();schedule={dates[0]:['a'],dates[100]:[],dates[150]:['a']}
  m,path=simulate(p,active,schedule,20);audit=[];n,q=simulate(p,active,schedule,20,audit=audit)
  self.assertEqual(m,n);pd.testing.assert_frame_equal(path,q)
  a=pd.DataFrame(audit);net=(a.pnl-a.fee).groupby(a.date).sum().reindex(dates,fill_value=0)
  np.testing.assert_allclose(1+net.cumsum()/1e6,path.nav,atol=1e-12)
if __name__=='__main__':unittest.main()
