import unittest
import pandas as pd
from strength_account_review import drawup
class Tests(unittest.TestCase):
    def test_initial_and_later_trough(self):
        idx=pd.date_range('2024-01-01',periods=4)
        self.assertAlmostEqual(drawup(pd.Series([1.1,1.2,1.3,1.4],index=idx))['max_hindsight_drawup'],.4)
        r=drawup(pd.Series([1.2,.8,1.5,1.3],index=idx));self.assertAlmostEqual(r['max_hindsight_drawup'],.875);self.assertEqual(r['start'],'2024-01-02')
        self.assertEqual(drawup(pd.Series([.9,.8,.7,.6],index=idx))['max_hindsight_drawup'],0)
if __name__=='__main__':unittest.main()
