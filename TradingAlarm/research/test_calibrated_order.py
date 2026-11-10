import unittest
import pandas as pd
from calibrate_pair_order import calibration
from calibrated_order_signal import balance_exposure
class Tests(unittest.TestCase):
    def test_occupancy_threshold(self):
        r=calibration(pd.Series([4.,4.,4.,9.]),pd.Series([.1,.2,.3,.9]))
        self.assertEqual(r['threshold'],.9);self.assertEqual(r['baseline_occupancy'],r['order_occupancy'])
    def test_hysteresis(self):
        s=pd.Series([.1,.9,.5,-.1,.95])
        self.assertEqual(balance_exposure(s,.8).tolist(),[0,1,1,0,1])
if __name__=='__main__':unittest.main()
