import unittest
import numpy as np
import pandas as pd
from walk_forward import choose_models, year_stats

class WalkForwardTests(unittest.TestCase):
    def test_future_returns_cannot_change_selection(self):
        idx=pd.bdate_range('2020-01-01','2025-12-31')
        wave=np.sin(np.arange(len(idx)))*.01
        returns=pd.DataFrame({'a':wave+.001,'b':wave+.0001},index=idx)
        before=choose_models(returns,[2024])
        self.assertEqual(before[0]['strategy'],'a')
        returns.loc['2024-01-01':,'b']=.5
        self.assertEqual(before,choose_models(returns,[2024]))
        self.assertLess(before[0]['training_end'],'2024-01-01')

    def test_insufficient_training_is_skipped(self):
        x=pd.DataFrame({'a':[.1,.2]},index=pd.to_datetime(['2023-01-01','2023-01-02']))
        self.assertEqual(choose_models(x,[2024]),[])

    def test_yearly_returns_include_boundary_day(self):
        p=pd.DataFrame({'return':[.1,-.2,.1]},index=pd.to_datetime(['2023-12-29','2024-01-02','2024-01-03']))
        r=year_stats(p)
        self.assertAlmostEqual(r[1]['return_total'],-.12)
        self.assertAlmostEqual(r[1]['max_drawdown_within_year'],-.2)

if __name__=='__main__': unittest.main()
