import unittest
from decimal import Decimal
from hk_cash_annotations import parse_cash
class CashTests(unittest.TestCase):
 def test_two_dividends_not_currency_alternatives(self):
  c=parse_cash('第一季度息0.1美元;相当于0.780688港元;第一季度特别息0.21美元;相当于1.639445港元;')
  self.assertEqual(sum(x['amount'] for x in c),Decimal('.31'));self.assertEqual(len(c),2)
 def test_ads_and_currency_are_not_additional_cash(self):
  c=parse_cash('末期息0.38美元;每股美国存托股0.76美元;');self.assertEqual(c[0]['amount'],Decimal('.38'));self.assertEqual(len(c),1)
  c=parse_cash('第二次股息0.1美元;相当于0.779073港元;相当于0.075817英镑;');self.assertEqual(len(c[0]['alternatives']),2)
 def test_unknown_and_orphan_alternative_fail(self):
  for text in ['每10股送1股','相当于1港元','末期息0.2港元;配股1股','']:
   with self.assertRaises(ValueError):parse_cash(text)
 def test_chinese_semicolon_and_per_share(self):
  self.assertEqual(parse_cash('第三期中期股息每股0.63港元；')[0]['amount'],Decimal('.63'))
if __name__=='__main__':unittest.main()
