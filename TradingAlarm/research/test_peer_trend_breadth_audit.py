import unittest
import pandas as pd
from peer_trend_breadth_audit import peer_breadth
class Tests(unittest.TestCase):
    def test_leave_self_out_and_dates(self):
        f=pd.DataFrame(dict(date=['2026-01-01']*3+['2026-01-02'],group=['A']*4,symbol=['a','b','c','a'],strength=[9.,7.,3.,9.]))
        a=peer_breadth(f);self.assertEqual(a.breadth.iloc[:3].tolist(),[.5,.5,1.]);self.assertTrue(pd.isna(a.breadth.iloc[3]))
        f.loc[0,'strength']=1.;b=peer_breadth(f);self.assertEqual(a.breadth.iloc[0],b.breadth.iloc[0]);self.assertEqual(b.breadth.iloc[1],0.)
if __name__=='__main__':unittest.main()
