import unittest
import pandas as pd
from strategy_signals import channel_signal,build_signals


class ChannelTests(unittest.TestCase):
    def frame(self):
        idx=pd.bdate_range('2020-01-01',periods=160)
        return pd.DataFrame({'open':100.,'close':100.,'high':101.,'low':99.},index=idx)

    def test_current_high_not_used_in_breakout_threshold(self):
        f=self.frame();f.iloc[70,f.columns.get_loc('close')]=102;f.iloc[70,f.columns.get_loc('high')]=103
        s=channel_signal(f,21)
        self.assertEqual(s.iloc[70],1.);self.assertTrue(s.iloc[71:].eq(1).all())

    def test_long_exit_keeps_state_through_short_channel_break(self):
        f=self.frame();f.iloc[70:110]=[110,110,111,109]
        f.iloc[110:]=[108,108,109,107]
        fast=channel_signal(f,21);slow=channel_signal(f,63)
        self.assertEqual(fast.iloc[110],0.);self.assertEqual(slow.iloc[110],1.)
        self.assertTrue(fast.iloc[:63].eq(0).all())

    def test_future_mutation_preserves_all_prior_signals(self):
        f=self.frame();f.iloc[70:]=[110,110,111,109]
        for name in ('channel21_21','channel21_63'):
            old=build_signals({'A':{'signal':f}},name)['A']
            changed=f.copy();changed.iloc[120:]*=.3
            new=build_signals({'A':{'signal':changed}},name)['A']
            pd.testing.assert_series_equal(old.iloc[:120],new.iloc[:120])

if __name__=='__main__':unittest.main()
