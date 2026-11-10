"""Analyzer regressions only. No native account or indicator model is imported."""
import json,unittest
from pathlib import Path
from unittest.mock import patch
import analyze as A

STAR='688001.SH'
class OrderMinimumTests(unittest.TestCase):
 def test_flat_new_STAR_order_requires_200(self):
  self.assertEqual(A.order_minimum(STAR,held_shares=0),200)
  with patch.object(A,'price',return_value=100.01):self.assertFalse(A.minimum_ok(STAR,'d',held_shares=0))
 def test_held_new_STAR_order_still_requires_200(self):
  self.assertEqual(A.order_minimum(STAR,held_shares=1000),200)
  with patch.object(A,'price',return_value=100.01):self.assertFalse(A.minimum_ok(STAR,'d',held_shares=1000))
 def test_new_STAR_200_boundary_is_preserved(self):
  with patch.object(A,'price',return_value=100):self.assertTrue(A.minimum_ok(STAR,'d',held_shares=1000))
 def test_same_original_partial_remainder_is_separate(self):
  # Original200, filled150, remaining50: minimum1 applies to this same
  # remaining order, never to the next canonical CP1/new order.
  self.assertEqual(A.order_minimum(STAR,same_order_partial=True,filled_in_this_order=150),1)
  self.assertGreaterEqual(50,A.order_minimum(STAR,same_order_partial=True,filled_in_this_order=150))
  self.assertEqual(A.order_minimum(STAR,held_shares=150),200)
 def test_holdings_cannot_impersonate_partial_fill(self):
  with self.assertRaises(ValueError):A.order_minimum(STAR,held_shares=1000,same_order_partial=True,filled_in_this_order=0)
 def test_main_board_new_order_minimum_100_unchanged(self):
  self.assertEqual(A.order_minimum('600001.SH',held_shares=1000),100)
 def test_fresh_CP1_after_trial_does_not_use_partial_remainder(self):
  ctx='S|2026-01-01';ds=['2026-01-01','2026-01-02','2026-01-05']
  hist={d:dict(context=ctx,permit=True,mature=i>0) for i,d in enumerate(ds)}
  node=dict(lo=ds[0],hi=ds[-1],contexts=[dict(id=ctx)])
  ops=[dict(day=d,sid=STAR,CP1_id='cp'+str(i),mobile_Q=True) for i,d in enumerate(ds)]
  prices={ds[0]:80,ds[1]:150,ds[2]:90}
  with patch.object(A,'price',side_effect=lambda s,d:prices[d]):r=A.capacity(node,None,hist,dict(zip(ds,ds[1:]+[None])),ops,'raw_CP1')
  self.assertEqual([x['units'] for x in r['daily_capacity']],[1,2])
  self.assertIn('not a fixed executable plan',r['initial_trial_selection'])

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(OrderMinimumTests)
 r=unittest.TextTestRunner(verbosity=2).run(suite)
 payload=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),scope='analysis-only order minimum and actual capacity-branch regression; not native account execution')
 Path(__file__).with_name('ORDER_MINIMUM_REGRESSION.json').write_text(json.dumps(payload,indent=2)+'\n')
 raise SystemExit(not r.wasSuccessful())
