import json
import unittest
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all,reconcile


class CombinedLedgerTests(unittest.TestCase):
    def fixture(self):
        folder=ROOT/'results/global-combined-provisional'
        return load_all(),pd.read_parquet(folder/'noadd-base-path.parquet'),json.loads((folder/'noadd-base-orders.json').read_text())

    def test_all_six_assets_and_real_ledger(self):
        assets,path,orders=self.fixture()
        self.assertEqual(set(assets),{'SPY','EFA','IEF','GLD','VNQ','DBC'})
        check,_=reconcile(assets,path,orders,15)
        self.assertLess(max(check['errors'].values()),1e-6)

    def test_incorrect_weight_is_rejected(self):
        assets,path,orders=self.fixture();path.iloc[100,path.columns.get_loc('w_SPY')]+=.01
        with self.assertRaises(AssertionError):reconcile(assets,path,orders,15)

    def test_vnq_dates_remain_provisional_after_stress(self):
        baseline=load_all()['VNQ']['dividends'];stress=load_all(10)['VNQ']['dividends']
        self.assertEqual(len(baseline),80)
        for a,b in zip(baseline,stress):
            self.assertFalse(a['settlement_verified'])
            self.assertEqual(a['amount'],b['amount'])
            self.assertEqual(a['ex_date'],b['ex_date'])
            self.assertGreater(b['pay_date'],a['pay_date'])


if __name__=='__main__':unittest.main()
