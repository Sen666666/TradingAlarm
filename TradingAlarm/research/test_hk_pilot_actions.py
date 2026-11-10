import unittest
from audit_hk_pilot_actions import classify
class HKActionTests(unittest.TestCase):
 def test_non_cash_events_do_not_become_cash(self):
  self.assertEqual(classify({'FHcontent':'实物分派:每21股获发1股京东'}),'in_kind_distribution_requires_asset_ledger')
  self.assertEqual(classify({'FHcontent':'优先认购股份'}),'subscription_right_requires_review')
  self.assertEqual(classify({'HGcontent':'未知内容'}),'unparsed_holder_annotation')
 def test_cash_with_buyback_is_not_discarded(self):
  self.assertEqual(classify({'FHcontent':'末期息3.4港元;','HGcontent':'回购105万股'}),'cash_dividend_candidate')
  self.assertEqual(classify({'HGcontent':'回购105万股'}),'issuer_buyback_not_holder_cashflow')
if __name__=='__main__':unittest.main()
