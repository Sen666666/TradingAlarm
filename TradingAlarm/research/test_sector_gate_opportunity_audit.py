import unittest
import pandas as pd
from sector_gate_opportunity_audit import match_strength
class MatchTests(unittest.TestCase):
 def test_no_replacement(self):
  a=pd.DataFrame({'symbol':['A','B','C'],'strength':[9.,9.1,9.2]},index=[0,1,2]);b=pd.DataFrame({'symbol':['D','E'],'strength':[9.05,9.3]},index=[3,4]);self.assertEqual(match_strength(a,b),[(0,3),(1,4)])
 def test_no_future_outcomes(self):
  a=pd.DataFrame({'symbol':['A'],'strength':[9.],'future':[100]},index=[0]);b=pd.DataFrame({'symbol':['D','E'],'strength':[8.9,9.3],'future':[-100,100]},index=[1,2]);before=match_strength(a,b);b.future=-b.future;self.assertEqual(before,match_strength(a,b))
if __name__=='__main__':unittest.main()
