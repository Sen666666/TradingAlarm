import unittest
from in_kind_ledger import InKindLedger
class InKindTests(unittest.TestCase):
 def marks(self,p=200.,d='2022-03-25'):return {'JD':(d,p,d,.8)}
 def test_entitlement_is_not_spendable_or_delivered_early(self):
  l=InKindLedger();l.accrue('jd','JD','2022-01-20',420,1,21)
  self.assertEqual(l.deliver('jd','2022-01-21',None),0)
  self.assertEqual(l.deliver('jd','2022-01-21','2022-03-25'),0)
  self.assertEqual(l.holdings,{})
  before=l.value('2022-03-25',self.marks())
  self.assertEqual(before['total'],3200);self.assertEqual(before['spendable_cash'],0)
  self.assertEqual(l.deliver('jd','2022-03-25','2022-03-25'),20)
  self.assertEqual(l.value('2022-03-25',self.marks())['total'],before['total'])
  self.assertEqual(l.deliver('jd','2022-03-26','2022-03-25'),0)
  with self.assertRaises(ValueError):l.value('2022-03-24',self.marks(d='2022-03-24'))
 def test_distribution_and_recipient_price_changes(self):
  l=InKindLedger();l.accrue('jd','JD','2022-01-20',420,1,21)
  old_parent=420*500*.8;ex_parent=420*(500-200/21)*.8
  self.assertAlmostEqual(ex_parent+l.value('2022-03-25',self.marks())['total'],old_parent)
  self.assertEqual(l.value('2022-03-25',self.marks(150))['total'],2400)
 def test_fractions_and_future_marks_rejected(self):
  l=InKindLedger();l.accrue('jd','JD','2022-01-20',100,1,21)
  with self.assertRaises(ValueError):l.value('2022-03-25',self.marks())
  with self.assertRaises(ValueError):l.accrue('jd','JD','2022-01-20',100,1,21)
  l=InKindLedger();l.accrue('jd','JD','2022-01-20',420,1,21)
  with self.assertRaises(ValueError):l.value('2022-01-20',self.marks())
if __name__=='__main__':unittest.main()
