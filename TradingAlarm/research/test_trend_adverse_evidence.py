import unittest
import pandas as pd
from trend_adverse_evidence import first_adverse


class AdverseTests(unittest.TestCase):
    def test_excludes_exit_close_and_snapshot_uses_past(self):
        idx=pd.date_range('2025-01-01',periods=10);p=pd.Series([100]*6+[95,96,94,80],index=idx);s=pd.Series(range(10),index=idx,dtype=float)
        r=first_adverse(p,s,idx[0],idx[-1],100,True)
        self.assertEqual(r['date'],'2025-01-07');self.assertEqual(r['strength'],6);self.assertEqual(r['change5'],5)
        self.assertIsNone(first_adverse(p,s,idx[0],idx[6],100,True))
        changed=s.copy();changed.iloc[7:]=100
        self.assertEqual(r,first_adverse(p,changed,idx[0],idx[-1],100,True))


if __name__=='__main__':unittest.main()
