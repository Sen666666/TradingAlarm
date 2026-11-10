import unittest
import numpy as np
import pandas as pd
from strategy_signals import channel_signal

class TrailingTests(unittest.TestCase):
    def frame(self):
        close=np.r_[np.full(70,100.),np.arange(105.,147.,2.),130.,129.,128.,150.]
        return pd.DataFrame({'close':close,'high':close+1,'low':close-1},index=pd.bdate_range('2024-01-01',periods=len(close)))
    def test_giveback_exit_before_initial_stop(self):
        f=self.frame();a=channel_signal(f,63,True);b=channel_signal(f,63,True,True)
        self.assertEqual(a.iloc[-4],1.)
        self.assertEqual(b.iloc[-5],1.)
        self.assertEqual(b.iloc[-4],0.)
    def test_causal_scale_and_peak_has_no_profit_cap(self):
        f=self.frame();a=channel_signal(f,63,True,True)
        self.assertTrue(a.iloc[70:91].eq(1).all())
        pd.testing.assert_series_equal(a,channel_signal(f*10,63,True,True))
        f.iloc[-4:]*=10
        pd.testing.assert_series_equal(a.iloc[:-4],channel_signal(f,63,True,True).iloc[:-4])

if __name__=='__main__':unittest.main()
