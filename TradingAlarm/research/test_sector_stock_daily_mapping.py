import unittest
import numpy as np
import pandas as pd
from sector_stock_daily_mapping import associate
class Tests(unittest.TestCase):
    def test_prefix_invariance_missing_and_ties(self):
        ix=pd.bdate_range('2020-01-01',periods=220);x=pd.Series(np.random.default_rng(1).normal(size=220),index=ix)
        p=pd.DataFrame({'z':x,'a':x,'negative':-x})
        full=associate(x,p);prefix=associate(x.iloc[:150],p.iloc[:150])
        pd.testing.assert_frame_equal(full.iloc[:150],prefix)
        self.assertTrue(full.proxy.iloc[:99].isna().all());self.assertTrue(full.proxy.iloc[99:].eq('a').all())
        damaged=x.copy();damaged.iloc[100:140]=np.nan
        self.assertTrue(associate(damaged,p).proxy.iloc[139:150].isna().all())
if __name__=='__main__':unittest.main()
