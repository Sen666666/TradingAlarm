import unittest
import numpy as np
import pandas as pd
from broad_daily_sleeve_path import sleeve_path
class Tests(unittest.TestCase):
    def test_entry_hold_exit_cash(self):
        ix=pd.date_range('2024-01-01',periods=4);marks=pd.Series([100,120,110,130],index=ix)
        e=[dict(entry_date='2024-01-01',exit_date='2024-01-03',status='closed',entry_price=100,exit_price=110)]
        nav,cash=sleeve_path(ix,marks,e,cost=0);np.testing.assert_allclose(nav,[1,1.18,1.09,1.09]);np.testing.assert_allclose(cash,[.1,.1,1.09,1.09])
    def test_cash_only_and_open_fee(self):
        ix=pd.date_range('2024-01-01',periods=2);p=pd.Series([100,110],index=ix)
        np.testing.assert_allclose(sleeve_path(ix,p,[])[0],[1,1])
        ep=[dict(entry_date='2024-01-01',status='open_at_cutoff',entry_price=100,exit_price=110)]
        nav,_=sleeve_path(ix,p,ep);self.assertAlmostEqual(nav[-1],.1+.9*110/(100*1.0015))
if __name__=='__main__':unittest.main()
