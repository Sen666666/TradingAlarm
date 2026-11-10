import json
import unittest
import pandas as pd
from build_stock_features import ROOT
from global_usd_ledger_audit import load_asset,reconcile


class RealLedgerTests(unittest.TestCase):
    def fixture(self):
        folder=ROOT/'results/global-usd-ledger'
        return (load_asset('SPY'),pd.read_parquet(folder/'SPY-path.parquet'),
                json.loads((folder/'SPY-orders.json').read_text()))

    def test_real_dividend_account_reconciles(self):
        check,_=reconcile(*self.fixture())
        self.assertGreater(check['entitlement_events'],0)
        self.assertGreater(check['final_receivable'],0)
        self.assertLess(check['maximum_errors']['nav'],1e-6)

    def test_invented_cash_is_detected(self):
        asset,path,orders=self.fixture();path.iloc[100,path.columns.get_loc('cash')]+=1
        with self.assertRaises(AssertionError):reconcile(asset,path,orders)

    def test_wrong_fee_is_detected(self):
        asset,path,orders=self.fixture();orders[0]['fee']+=1
        with self.assertRaises(AssertionError):reconcile(asset,path,orders)


if __name__=='__main__':unittest.main()
