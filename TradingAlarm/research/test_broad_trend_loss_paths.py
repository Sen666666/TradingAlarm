import unittest
import pandas as pd
from broad_trend_loss_paths import excursion


class ExcursionTests(unittest.TestCase):
    def test_exit_day_exclusion_and_open_inclusion(self):
        idx=pd.date_range('2025-01-01',periods=3)
        f=pd.DataFrame(dict(observed_bar=True,volume=100,signal_high=[105,110,200],signal_low=[95,90,50]),index=idx)
        closed=excursion(f,str(idx[0].date()),str(idx[2].date()),100,95,True)
        self.assertAlmostEqual(closed['mfe'],.1);self.assertAlmostEqual(closed['mae'],-.1)
        opened=excursion(f,str(idx[0].date()),str(idx[2].date()),100,95,False)
        self.assertEqual(opened['mfe'],1);self.assertEqual(opened['mae'],-.5)
        terminal=excursion(f,str(idx[0].date()),str(idx[0].date()),100,80,True)
        self.assertAlmostEqual(terminal['mae'],-.2)


if __name__=='__main__':unittest.main()
