import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from market import decode
from stock_actions import parse_ths_rights

class RightsTests(unittest.TestCase):
 def test_captured_rle_table(self):
  body=(ROOT/'results/stock-data-audit/ths-actions-300033.bin').read_bytes()
  self.assertIsNone(decode(body))
  kind,instance,rows=decode(body,allowed_kinds=(211,))
  self.assertEqual(kind,211);self.assertEqual(len(rows),19)
  event=parse_ths_rights('USZA300033',rows[0])
  self.assertEqual(event['effective_date'],'2010-03-12')
  self.assertEqual(event['capitalization_shares_per_old_share'],1.)
  self.assertAlmostEqual(event['gross_cash_per_old_share'],.3)
  self.assertFalse(event['ledger_ready'])
 def test_unmodeled_subscription_and_date_mismatch_rejected(self):
  with self.assertRaises(ValueError):parse_ths_rights('X',{'1':20200101,'471':'2020-01-01(每十股 配股3.00股 红利1.00元)$'})
  with self.assertRaises(ValueError):parse_ths_rights('X',{'1':20200102,'471':'2020-01-01(每十股 红利1.00元)$'})

if __name__=='__main__':unittest.main()
