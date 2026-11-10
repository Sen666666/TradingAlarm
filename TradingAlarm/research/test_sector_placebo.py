import unittest
import numpy as np
from stock_sector_placebo import pick_indices
class PlaceboSelectionTests(unittest.TestCase):
 def test_rank_then_mask_with_no_refill_on_outcomes(self):
  order=np.array([3,1,0,2]);gate=np.array([True,True,False,True])
  np.testing.assert_array_equal(pick_indices(order,gate,2),[3,1])
  np.testing.assert_array_equal(pick_indices(order,np.zeros(4,bool)),[])
 def test_permutation_preserves_gate_and_selection_count(self):
  rng=np.random.default_rng(1);gate=np.array([True]*7+[False]*13);order=np.arange(20)
  for _ in range(20):
   p=rng.permutation(gate);self.assertEqual(len(pick_indices(order,p)),7)
if __name__=='__main__':unittest.main()
