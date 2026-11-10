import unittest
import pandas as pd
from global_tail_concentration import describe


class TailConcentrationTests(unittest.TestCase):
    def test_open_mark_does_not_become_closed_profit(self):
        frame=pd.DataFrame({'status':['closed','closed','open_at_cutoff'], 'R_cost15':[-1.,4.,20.]})
        result=describe(frame,15)
        self.assertEqual(result['closed']['sum_R'],3)
        self.assertEqual(result['open_mark_R'],20)
        self.assertEqual(result['marked']['remove_largest_1_sum'],3)
        self.assertEqual(result['closed']['remove_largest_1_sum'],-1)
        self.assertEqual(result['closed']['ordinary_below3R_sum'],-1)

    def test_three_r_boundary_is_in_tail(self):
        frame=pd.DataFrame({'status':['closed']*3,'R_cost30':[3.,2.,-1.]})
        r=describe(frame,30)['closed']
        self.assertEqual(r['tail_count'],1)
        self.assertEqual(r['tail_sum'],3)
        self.assertEqual(r['ordinary_below3R_sum'],1)
        self.assertEqual(r['remove_largest_3_sum'],0)


if __name__=='__main__':unittest.main()
