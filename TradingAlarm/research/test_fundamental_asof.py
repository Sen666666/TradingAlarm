import unittest
from fundamental_asof import available_snapshot
class FinancialAsOfTests(unittest.TestCase):
 def row(self,pub='2020-04-20',value='0.2'):
  return dict(statDate='2019-12-31',pubDate=pub,YOYPNI=value,verified_original_fields=['YOYPNI'],evidence_url='https://issuer.example/report',evidence_available_date=pub)
 def test_publication_delay_and_missing_not_zero(self):
  r=self.row();self.assertIsNone(available_snapshot([r],'2020-04-20','YOYPNI'));self.assertEqual(available_snapshot([r],'2020-04-21','YOYPNI')['value'],'0.2')
  r['verified_original_fields']=[];self.assertIsNone(available_snapshot([r],'2020-05-01','YOYPNI'))
 def test_future_revision_does_not_rewrite_past(self):
  first=self.row();revision=self.row('2021-04-20','-0.5')
  self.assertEqual(available_snapshot([first,revision],'2020-06-01','YOYPNI')['value'],'0.2')
  self.assertEqual(available_snapshot([first,revision],'2021-04-21','YOYPNI')['value'],'-0.5')
 def test_evidence_availability_later_than_vendor(self):
  r=self.row();r['evidence_available_date']='2020-06-01'
  self.assertIsNone(available_snapshot([r],'2020-05-01','YOYPNI'))
 def test_conflict_and_bad_date_rejected(self):
  with self.assertRaises(ValueError):available_snapshot([self.row(),self.row(value='.3')],'2020-05-01','YOYPNI')
  with self.assertRaises(ValueError):available_snapshot([self.row(pub='2019-01-01')],'2020-05-01','YOYPNI')
if __name__=='__main__':unittest.main()
