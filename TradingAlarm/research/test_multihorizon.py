import unittest
import pandas as pd
from multihorizon_engine import trend_scores,run


class MultiHorizonTests(unittest.TestCase):
    def asset(self):
        idx=pd.bdate_range('2005-01-03',periods=400)
        raw=pd.DataFrame({'open':[100+i*.1 for i in range(400)],'close':[100+i*.1 for i in range(400)],'volume':1e7},index=idx)
        return dict(raw=raw,signal=raw.copy(),currency='USD',splits=[],dividends=[],lot=1,commission_min=0.)

    def test_common_warmup_and_positive_vote(self):
        a=self.asset();s=trend_scores(a['signal'].close,'ensemble')
        self.assertTrue(s.iloc[:252].eq(0).all());self.assertTrue(s.iloc[252:].eq(1).all())

    def test_future_quotes_do_not_change_prior_path(self):
        a=self.asset();idx=a['raw'].index
        _,p,o,_,_,_=run({'a':a},str(idx[280].date()),str(idx[-1].date()),'ensemble')
        a['raw'].loc[idx[350]:,['open','close']]*=.5;a['signal']=a['raw'].copy()
        _,q,oo,_,_,_=run({'a':a},str(idx[280].date()),str(idx[-1].date()),'ensemble')
        pd.testing.assert_frame_equal(p.loc[:idx[349]],q.loc[:idx[349]])
        self.assertEqual([r for r in o if r['date']<str(idx[350].date())],[r for r in oo if r['date']<str(idx[350].date())])
        self.assertTrue(all(pd.Timestamp(r['signal_date'])<pd.Timestamp(r['date']) for r in o))

    def test_delay_preserves_frozen_monthly_signal(self):
        a=self.asset();idx=a['raw'].index;start=str(idx[280].date());end=str(idx[-1].date())
        base=run({'a':a},start,end,'single252');later=run({'a':a},start,end,'single252',delay=1)
        self.assertEqual(base[2][0]['signal_date'],later[2][0]['signal_date'])
        self.assertEqual(pd.Timestamp(later[2][0]['date']),idx[281])

    def test_unchanged_score_keeps_shares_as_price_rises(self):
        a=self.asset();idx=a['raw'].index
        start=str(idx[280].date());end=str(idx[-1].date())
        base=run({'a':a},start,end,'single252')
        drift=run({'a':a},start,end,'single252',rebalance='score_change')
        self.assertGreater(len(base[2]),1)
        self.assertEqual(len(drift[2]),1)
        self.assertGreater(drift[1]['w_a'].iloc[-1],.9)

    def test_changed_score_exits_and_future_is_causal(self):
        a=self.asset();idx=a['raw'].index
        args=({'a':a},str(idx[280].date()),str(idx[-1].date()),'single252')
        before=run(*args,rebalance='score_change',delay=1)
        a['raw'].loc[idx[350]:,['open','close']]*=.5;a['signal']=a['raw'].copy()
        after=run(*args,rebalance='score_change',delay=1)
        pd.testing.assert_frame_equal(before[1].loc[:idx[349]],after[1].loc[:idx[349]])
        self.assertEqual(after[1]['w_a'].iloc[-1],0.)
        self.assertEqual(len(after[2]),2)
        self.assertTrue(all(o['signal_date']<o['date'] for o in after[2]))


if __name__=='__main__':unittest.main()
