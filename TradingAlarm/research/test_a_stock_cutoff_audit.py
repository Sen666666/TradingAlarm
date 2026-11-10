import unittest
import pandas as pd
from a_stock_cutoff_audit import snapshot


class CutoffTests(unittest.TestCase):
 def test_future_exit_price_and_status_do_not_change_current_mark(self):
  h=pd.DataFrame(dict(date=pd.to_datetime(['2022-01-03','2022-01-04','2023-01-03']),observed_bar=True,positive_volume=True,signal_close=[100.,101.,1000.]))
  r=dict(symbol='x',source='test',entry_date='2022-01-03',exit_date='2023-01-03',entry_price=100.,exit_price=1000.,risk_distance=4.)
  a=snapshot([r],h,'2022-01-04');r['exit_price']=1.;r['exit_date']=None
  self.assertEqual(a,snapshot([r],h,'2022-01-04'));self.assertEqual(a[0]['status'],'open_at_cutoff')
 def test_missing_cutoff_is_not_a_filled_exit(self):
  h=pd.DataFrame(dict(date=pd.to_datetime(['2022-01-03']),observed_bar=True,positive_volume=True,signal_close=[100.]))
  r=dict(symbol='x',source='test',entry_date='2022-01-03',exit_date=None,entry_price=100.,exit_price=100.,risk_distance=4.)
  a=snapshot([r],h,'2022-12-30')[0];self.assertEqual(a['status'],'stale_unknown');self.assertLess(a['R_zero_terminal_cost15'],-25.)


if __name__=='__main__':unittest.main()
