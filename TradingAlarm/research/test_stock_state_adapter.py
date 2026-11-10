import unittest
from stock_state_adapter import provider_open_state
from stock_execution import next_open_guard
class StateAdapterTests(unittest.TestCase):
 def row(self):return dict(code='sz.000001',date='2024-01-03',adjustflag='3',open='10',tradestatus='1',isST='0',preclose='9.9')
 def test_tradeable_flag_never_fabricates_limits(self):
  s=provider_open_state(self.row(),'000001.SZ','2024-01-03',True)
  self.assertIsNone(s.upper_limit);self.assertFalse(s.explicitly_unlimited)
  self.assertEqual(next_open_guard(s,'buy','2024-01-02').reason,'missing_or_stale_price_limit_state')
 def test_suspend_and_identity(self):
  r=self.row();r['tradestatus']='0'
  s=provider_open_state(r,'000001.SZ','2024-01-03',True)
  self.assertEqual(next_open_guard(s,'buy','2024-01-02').reason,'suspended')
  with self.assertRaises(ValueError):provider_open_state(r,'000001.SZ','2024-01-04',True)
 def test_source_and_unknown_flags_fail_closed(self):
  r=self.row();r['tradestatus']='?'
  s=provider_open_state(r,'000001.SZ','2024-01-03',True)
  self.assertEqual(next_open_guard(s,'buy','2024-01-02').reason,'unknown_trading_state')
  s=provider_open_state(self.row(),'000001.SZ','2024-01-03',False)
  self.assertFalse(next_open_guard(s,'buy','2024-01-02').allowed)
if __name__=='__main__':unittest.main()
