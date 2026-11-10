import unittest
from unittest.mock import patch
import test_campaign_completion as completion
from campaign_engine import run_campaign


class USDAccountTests(unittest.TestCase):
    def setup_asset(self):
        a=completion.CompletionTests().asset();a['currency']='USD';a['commission_min']=0.
        return a

    def run_asset(self,a,scenario=False):
        idx=a['raw'].index
        with patch('campaign_engine.fx_series',side_effect=AssertionError('USD must not request HKD FX')),patch('campaign_engine.features',completion.CompletionTests().fixed_features):
            return run_campaign({'a':a},start=str(idx[240].date()),base_currency='USD',settlement_scenario=scenario,
                pyramid=False,exit_mode='trend',cost_bps=15,max_positions=1)

    def test_cash_receivable_is_not_spendable_until_payday(self):
        a=self.setup_asset();idx=a['raw'].index
        a['raw'].loc[idx[242]:,['open','high','low','close']]-=1
        a['dividends']=[dict(ex_date=str(idx[242].date()),pay_date=str(idx[245].date()),amount=1.,settlement_verified=True)]
        _,p,orders,_,_=self.run_asset(a)
        self.assertEqual(len(orders),1)
        self.assertEqual(orders[0]['fx'],1.)
        self.assertAlmostEqual(orders[0]['fee'],orders[0]['units']*100*.0015)
        self.assertAlmostEqual(p.loc[idx[242],'cash'],p.loc[idx[241],'cash'])
        self.assertAlmostEqual(p.loc[idx[242],'nav'],p.loc[idx[241],'nav'])
        self.assertAlmostEqual(p.loc[idx[245],'cash']-p.loc[idx[244],'cash'],orders[0]['units'])

    def test_reject_ambiguous_currency_and_missing_payment(self):
        a=self.setup_asset();idx=a['raw'].index
        a['dividends']=[dict(ex_date=str(idx[242].date()),amount=1.)]
        with self.assertRaisesRegex(ValueError,'Unverified'):self.run_asset(a)
        a=self.setup_asset();a['currency']='HKD'
        with self.assertRaisesRegex(ValueError,'USD assets'):self.run_asset(a)
        a=self.setup_asset()
        with self.assertRaisesRegex(ValueError,'CNY account'):run_campaign({'a':a})

    def test_provisional_settlement_requires_explicit_scenario(self):
        a=self.setup_asset();idx=a['raw'].index
        a['dividends']=[dict(ex_date=str(idx[242].date()),pay_date=str(idx[245].date()),
                             amount=1.,settlement_verified=False,settlement_scenario=True)]
        with self.assertRaisesRegex(ValueError,'Unverified'):self.run_asset(a)
        self.run_asset(a,scenario=True)
        a['dividends'][0]['pay_date']=None
        with self.assertRaisesRegex(ValueError,'Unverified'):self.run_asset(a,scenario=True)


if __name__=='__main__':unittest.main()
