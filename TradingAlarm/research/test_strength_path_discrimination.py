import unittest
import pandas as pd
from strength_path_discrimination import path_labels
class Tests(unittest.TestCase):
    def test_nextopen_and_extremes(self):
        f=pd.DataFrame({'signal_open':[100,10,12,13],'signal_high':[500,12,15,14],'signal_low':[1,9,11,12],'signal_close':[100,11,14,13]},index=pd.date_range('2024-01-01',periods=4))
        r=path_labels(f,2);self.assertAlmostEqual(r.iloc[0]['asym2'],2/3);self.assertAlmostEqual(r.iloc[0]['return2'],.4);self.assertTrue(r.iloc[-1].isna().all())
    def test_year_boundary_and_flat(self):
        f=pd.DataFrame({k:[10]*4 for k in ['signal_open','signal_high','signal_low','signal_close']},index=pd.date_range('2024-12-30',periods=4))
        r=path_labels(f,1);self.assertEqual(r.iloc[0]['asym1'],0);self.assertTrue(r.iloc[1].isna().all())
if __name__=='__main__':unittest.main()
