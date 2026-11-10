import unittest
from tail_opportunity_concentration import concentration
class Tests(unittest.TestCase):
    def test_effective_counts_and_units(self):
        self.assertEqual(concentration([2,2,2,2])['effective_buckets'],4)
        self.assertEqual(concentration([2,0])['largest_share'],1)
        self.assertEqual(concentration([0])['effective_buckets'],None)
        self.assertEqual(concentration([1,2,3]),concentration([100,200,300]))
if __name__=='__main__':unittest.main()
