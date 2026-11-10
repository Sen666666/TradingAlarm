import unittest
import pandas as pd
from matched_trend_exit_audit import first_exit
class ExitTests(unittest.TestCase):
 def test_first_cross(self):self.assertEqual(first_exit(pd.Series([9,8,5,3]),0,3),(2,False))
 def test_entry_conflict_and_missing(self):self.assertEqual(first_exit(pd.Series([4,float('nan'),6,4]),0,3),(3,False))
 def test_censoring(self):self.assertEqual(first_exit(pd.Series([9,8,7]),0,2),(2,True))
if __name__=='__main__':unittest.main()
