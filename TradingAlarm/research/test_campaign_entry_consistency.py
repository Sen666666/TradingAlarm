import unittest
from unittest.mock import patch
import pandas as pd
import test_campaign_completion as completion
from campaign_engine import run_campaign


class EntryConsistencyTests(unittest.TestCase):
    def run_case(self,release=None,delay=0):
        fixture=completion.CompletionTests();a=fixture.asset();idx=a['raw'].index
        def signals(asset):
            f=fixture.fixed_features(asset);f['trend_exit']=True
            if release is not None:f.loc[idx[release]:,'trend_exit']=False
            return f
        with patch('campaign_engine.features',signals),patch('campaign_engine.fx_series',lambda index:pd.Series(1.,index=index)):
            result=run_campaign({'a':a},start=str(idx[240].date()),pyramid=False,exit_mode='trend',avoid_active_exit=True,extra_delay=delay)
        return idx,result

    def test_active_exit_blocks_breakout(self):
        _,r=self.run_case();self.assertFalse(r[2])

    def test_release_uses_previous_close(self):
        idx,r=self.run_case(release=241)
        self.assertEqual(r[2][0]['date'],str(idx[242].date()))
        idx,r=self.run_case(release=241,delay=1)
        self.assertEqual(r[2][0]['date'],str(idx[243].date()))


if __name__=='__main__':unittest.main()
