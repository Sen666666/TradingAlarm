import unittest
from quarterly_earnings import quarter_growth
class QuarterEarningsTests(unittest.TestCase):
 def row(self,end='2019-09-30',now='338063615.35',prior='332789830.57',pub='2019-10-22'):
  return dict(symbol='002541.SZ',period_end=end,current_ytd=now,comparative_ytd=prior,available_date=pub,verified=True,evidence_url='https://issuer.example/report',basis_id='verified-compatible',currency='CNY',metric='attributable_net_profit',period_basis='year_to_date')
 def previous(self):return self.row('2019-06-30','169619647.87','161841970.33','2019-08-28')
 def test_reconstruction(self):
  r=quarter_growth(self.row(),self.previous(),'2019-10-23');self.assertEqual(r['current_quarter'],'168443967.48');self.assertEqual(r['prior_quarter'],'170947860.24');self.assertLess(float(r['yoy']),0)
 def test_unavailable_or_unverified(self):
  self.assertIsNone(quarter_growth(self.row(),self.previous(),'2019-10-22'))
  p=self.previous();p['verified']=False;self.assertIsNone(quarter_growth(self.row(),p,'2019-10-23'))
 def test_incompatible_and_nonadjacent_rejected(self):
  for key,val in [('basis_id','restated'),('currency','USD'),('symbol','other'),('period_end','2018-06-30')]:
   p=self.previous();p[key]=val
   with self.assertRaises(ValueError):quarter_growth(self.row(),p,'2019-10-23')
 def test_q1_and_nonpositive_base(self):
  r=self.row('2019-03-31','10','-5','2019-04-20');v=quarter_growth(r,None,'2019-04-21');self.assertIsNone(v['yoy']);self.assertEqual(v['current_quarter'],'10')
  with self.assertRaises(ValueError):quarter_growth(r,self.previous(),'2019-10-23')
if __name__=='__main__':unittest.main()
