import unittest
import pandas as pd
import numpy as np
from ths_volume_units import ths_split_consistent_volume
class Tests(unittest.TestCase):
    def test_split_cash_and_prefix(self):
        ix=pd.date_range('2024-01-01',periods=6);v=pd.Series([100,100,150,150,150,150],index=ix)
        rights={'symbol':'USZA000001','records':[{'1':20240103,'471':'2024-01-03(每十股 转增5.00股 红利1.00元)$'},{'1':20240105,'471':'2024-01-05(每十股 红利2.00元)$'}]}
        out=ths_split_consistent_volume(v,rights);np.testing.assert_allclose(out,100)
        pd.testing.assert_series_equal(out.iloc[:2],ths_split_consistent_volume(v.iloc[:2],rights));self.assertEqual(v.iloc[-1],150)
    def test_empty_fails(self):
        with self.assertRaises(ValueError):ths_split_consistent_volume(pd.Series([1],index=pd.date_range('2024-01-01',periods=1)),{'records':[]})
if __name__=='__main__':unittest.main()
