import unittest
import pandas as pd
from stock_smooth_matched import match_date
class MatchTests(unittest.TestCase):
 def sample(self):
  return pd.DataFrame({'symbol':[f'{i:03}' for i in range(30)],'date':pd.Timestamp('2020-01-02'),'smooth_score':range(30),'momentum126_21':.2,'atr_fraction':.03,'turnover60':100.,'forward_126':range(30)})
 def test_no_replacement_no_future_labels(self):
  g=self.sample();pairs,n=match_date(g);self.assertEqual(n,10);self.assertEqual(len(pairs),10)
  self.assertEqual(len({x['control'] for x in pairs}),10)
  self.assertTrue(all(x['max_rank_gap']<=.2 and x['score_gap']>0 for x in pairs))
  g.forward_126=-100;self.assertEqual(pairs,match_date(g)[0])
 def test_caliper_can_reject_all(self):
  g=self.sample();g['momentum126_21']=range(30)
  self.assertEqual(match_date(g,caliper=0)[0],[])
if __name__=='__main__':unittest.main()
