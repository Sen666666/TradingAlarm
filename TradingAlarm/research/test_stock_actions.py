import unittest
from stock_actions import normalize_distribution

class ActionTests(unittest.TestCase):
 def row(self):
  return dict(symbol='X',status='实施方案',plan='10派3元(含税)',announcement_date='2023-08-05',record_date='2023-08-10',ex_date='2023-08-11',source='fixture')
 def test_unknown_pay_date_is_not_assumed_ex_date(self):
  r=normalize_distribution(self.row());self.assertIsNone(r['pay_date']);self.assertFalse(r['ledger_ready']);self.assertAlmostEqual(r['gross_cash_per_old_share'],.3)
 def test_proposals_do_not_create_receivables(self):
  r=self.row();r['status']='董事会预案';self.assertIsNone(normalize_distribution(r))
 def test_mixed_cash_and_shares_require_share_availability(self):
  r=self.row();r.update(plan='10送2转增3派1元(含税)',pay_date='2023-08-11');x=normalize_distribution(r)
  self.assertAlmostEqual(x['bonus_shares_per_old_share'],.2);self.assertAlmostEqual(x['capitalization_shares_per_old_share'],.3);self.assertFalse(x['ledger_ready'])
 def test_nonstandard_and_invalid_dates_fail(self):
  r=self.row();r['plan']='每股派发特别股息';
  with self.assertRaises(ValueError):normalize_distribution(r)
  r=self.row();r['record_date']='2023-08-12'
  with self.assertRaises(ValueError):normalize_distribution(r)

if __name__=='__main__':unittest.main()
