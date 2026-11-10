import unittest
from unittest.mock import patch
import pandas as pd
import test_campaign
from campaign_engine import features,run_campaign


class CompletionTests(unittest.TestCase):
    def asset(self):
        a=test_campaign.CampaignTests().asset();idx=a['raw'].index
        a['raw'].loc[:,['open','high','low','close']]=100.
        a['raw']['volume']=10000.;a['raw'].loc[idx[240]:,'volume']=1e7
        a['lot']=10;a['signal']=a['raw'].copy()
        return a

    def fixed_features(self,a):
        f=features(a);f['atr']=2.;f['upper']=99.;f['ma']=0.;f['strength']=1.;f['trend_exit']=False
        return f

    def run_case(self,a,fx=None,feature=None):
        idx=a['raw'].index
        with patch('campaign_engine.fx_series',fx or (lambda index:pd.Series(1.,index=index))),patch('campaign_engine.features',feature or self.fixed_features):
            return run_campaign({'a':a},start=str(idx[240].date()),entry='breakout',exit_mode='trend',
                pyramid=False,max_positions=1,complete_initial=True)

    def test_split_fx_dividend_and_original_budget(self):
        a=self.asset();idx=a['raw'].index;a['currency']='HKD'
        a['raw'].loc[idx[241]:,['open','high','low','close']]/=2
        a['splits']=[dict(date=str(idx[241].date()),ratio=2)]
        a['raw'].loc[idx[242]:,['open','high','low','close']]-=1
        a['dividends']=[dict(ex_date=str(idx[242].date()),pay_date=str(idx[245].date()),amount=1)]
        def fx(index):
            result=pd.Series(1.,index=index);result.loc[idx[241]:]=2.;return result
        _,p,orders,_,state=self.run_case(a,fx)
        buys=[o for o in orders if o['units']>0]
        self.assertEqual([o['type'] for o in buys],['entry','complete'])
        self.assertEqual([o['units'] for o in buys],[100.,520.])
        self.assertEqual(buys[0]['completion_budget'],buys[1]['completion_budget'])
        self.assertEqual(buys[0]['stop'],buys[1]['stop'])
        risk=sum(o['units']*(o['adjusted_open']-o['stop'])/o['factor']*o['fx'] for o in buys)
        self.assertAlmostEqual(risk,buys[0]['completion_budget'])
        self.assertAlmostEqual(state['a']['committed_risk'],risk)
        self.assertAlmostEqual(p.loc[idx[242],'nav'],p.loc[idx[241],'nav'])
        self.assertAlmostEqual(p.loc[idx[245],'cash']-p.loc[idx[244],'cash'],720*2*.999)
        self.assertTrue((p.cash>=0).all())

    def test_no_average_down_and_exit_priority(self):
        a=self.asset();idx=a['raw'].index
        a['raw'].loc[idx[241]:,['open','high','low','close']]=99.
        _,_,o,_,_=self.run_case(a)
        self.assertFalse(any(x['type']=='complete' for x in o))
        a=self.asset();a['raw'].loc[idx[241],'volume']=0
        def exits(asset):
            f=self.fixed_features(asset);f.loc[idx[240],'trend_exit']=True;return f
        _,_,o,_,_=self.run_case(a,feature=exits)
        first=[x for x in o if x['campaign_id']==1]
        self.assertEqual([x['type'] for x in first],['entry','exit'])
        self.assertEqual(first[1]['date'],str(idx[242].date()))

    def test_future_prices_cannot_change_earlier_completion(self):
        a=self.asset();idx=a['raw'].index;_,p,o,_,_=self.run_case(a)
        a['raw'].loc[idx[260]:,['open','high','low','close']]*=.5
        _,q,oo,_,_=self.run_case(a)
        pd.testing.assert_frame_equal(p.loc[:idx[259]],q.loc[:idx[259]])
        cutoff=str(idx[260].date())
        self.assertEqual([x for x in o if x['date']<cutoff],[x for x in oo if x['date']<cutoff])


if __name__=='__main__':unittest.main()
