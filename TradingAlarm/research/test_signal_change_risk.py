import unittest
import pandas as pd
from signal_change_risk_audit import daily_pnl,summarize


class RiskAuditTests(unittest.TestCase):
    def fixture(self):
        idx=pd.bdate_range('2020-01-01',periods=4)
        raw=pd.DataFrame({'close':[100,100,99,101]},index=idx)
        assets={'A':{'raw':raw,'dividends':[{'ex_date':str(idx[2].date()),'pay_date':'2020-02-01','amount':1.}]}}
        path=pd.DataFrame({'nav':[1.,1.,1.000002],'w_A':[.0001,.000099,.000101]},index=idx[1:])
        orders=[{'date':str(idx[1].date()),'symbol':'A','units':1,'raw_open':100.,'fee':0.}]
        return assets,path,orders

    def test_ex_dividend_claim_offsets_price_drop(self):
        assets,path,orders=self.fixture();pnl=daily_pnl(assets,path,orders)
        self.assertEqual(pnl.A.tolist(),[0.,0.,2.])
        self.assertAlmostEqual(summarize(path,pnl)['variance_contribution']['A'],1.)

    def test_corrupted_nav_is_detected(self):
        assets,path,orders=self.fixture();path.iloc[-1,0]+=.01
        with self.assertRaises(AssertionError):daily_pnl(assets,path,orders)

if __name__=='__main__':unittest.main()
