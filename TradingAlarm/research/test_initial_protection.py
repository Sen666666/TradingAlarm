import unittest
import pandas as pd
from strategy_signals import channel_signal


class ProtectionTests(unittest.TestCase):
    def frame(self):
        idx=pd.bdate_range('2020-01-01',periods=130)
        f=pd.DataFrame({'open':100.,'high':101.,'low':90.,'close':100.},index=idx)
        f.iloc[63:]=[100,101,99,100]
        f.iloc[90]=[102,103,101,102]
        f.iloc[91:]=[100,101,99,100]
        return f

    def test_small_pullback_held_but_failure_exits(self):
        f=self.frame();f.iloc[95:]=[97,98,96,97]
        base=channel_signal(f,63);new=channel_signal(f,63,True)
        self.assertEqual(new.iloc[91],1.)
        self.assertEqual(base.iloc[95],1.)
        self.assertEqual(new.iloc[95],0.)

    def test_fixed_initial_line_does_not_widen_with_new_volatility(self):
        f=self.frame();f.iloc[91:95,f.columns.get_loc('high')]=200
        f.iloc[95:]=[97,98,96,97]
        self.assertEqual(channel_signal(f,63,True).iloc[95],0.)

    def test_future_independence_and_scale(self):
        f=self.frame();old=channel_signal(f,63,True)
        changed=f.copy();changed.iloc[100:]*=.1
        pd.testing.assert_series_equal(old.iloc[:100],channel_signal(changed,63,True).iloc[:100])
        pd.testing.assert_series_equal(old,channel_signal(f*10,63,True))

if __name__=='__main__':unittest.main()
