import unittest
import numpy as np
import pandas as pd
from geometric_strength import strength_exposure
from a_stock_monthly252 import simulate
class Tests(unittest.TestCase):
    def test_jump_hold_exit_prefix(self):
        s=pd.Series([np.nan,4,9,7,6,3,5,8,9,5])
        expected=[0,0,1,1,1,0,0,0,1,0]
        self.assertEqual(strength_exposure(s).tolist(),expected)
        pd.testing.assert_series_equal(strength_exposure(s[:6]),strength_exposure(s)[:6])
    def test_first_state_and_missing(self):
        self.assertEqual(strength_exposure(pd.Series([7,np.nan,9,np.nan,4])).tolist(),[0,0,1,1,0])
        self.assertEqual(strength_exposure(pd.Series([9])).tolist(),[1])
    def test_next_open(self):
        dates=pd.date_range('2024-01-01',periods=5)
        scores=strength_exposure(pd.Series([4,9,7,3,4],index=dates)).to_numpy(bool)
        prices=np.arange(10.,15.)
        rows=simulate(dates,prices,prices,scores,np.ones(5,bool),np.ones(5,bool),[dates[-1]],'X',cadence='daily',start='2024-01-01')['2024-01-05']
        self.assertEqual(len(rows),1);e=rows[0]
        self.assertEqual(e['entry_date'],'2024-01-03');self.assertEqual(e['exit_date'],'2024-01-05')
        self.assertEqual(e['entry_price'],12);self.assertEqual(e['exit_price'],14)
if __name__=='__main__':unittest.main()
