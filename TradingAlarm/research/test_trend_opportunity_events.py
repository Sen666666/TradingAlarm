import unittest
from trend_opportunity_events import merge_intervals


class IntervalTests(unittest.TestCase):
    def test_transitive_and_separate(self):
        self.assertEqual(merge_intervals([(7,10),(1,4),(4,8),(12,13)]),[dict(start=1,end=10,members=3),dict(start=12,end=13,members=1)])
        self.assertEqual(merge_intervals([]),[])
        with self.assertRaises(ValueError):merge_intervals([(3,2)])


if __name__=='__main__':unittest.main()
