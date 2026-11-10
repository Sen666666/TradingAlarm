import copy
import unittest
import pandas as pd
import test_monthly_ah
from monthly_ah_engine import run
from campaign_claims import CampaignClaims
from monthly_claim_ledger_audit import reconcile


class MonthlyClaimTests(unittest.TestCase):
    def fixture(self):
        parent=test_monthly_ah.MonthlyAHTests().asset();parent['currency']='HKD';idx=parent['raw'].index
        child=copy.deepcopy(parent);child['dividends']=[dict(ex_date=str(idx[350].date()),pay_date=str(idx[355].date()),amount=1.)]
        parent['in_kind']=[dict(ex_date=str(idx[310].date()),recipient='C',numerator=1,denominator=7)]
        # Force a subsequent flat parent position while claims stay outstanding.
        parent['raw'].loc[idx[330]:,['open','high','low','close']]*=.5;parent['signal']=parent['raw'].copy()
        assets={'P':parent};recipients={'C':child};fx=pd.Series(1.,index=idx);claims=CampaignClaims(assets,recipients)
        result=run(assets,str(idx[280].date()),str(idx[-1].date()),policy='score_change',fx_override=fx,security_claims=claims)
        return assets,recipients,fx,claims,result

    def test_non_cash_claims_survive_parent_exit_and_receive_dividend(self):
        assets,recipients,fx,claims,(_,p,o,_)=self.fixture()
        q=int(o[0]['units'])//7
        self.assertEqual(claims.quantities()['C'],q)
        self.assertGreater(q,0)
        self.assertEqual(p['w_P'].iloc[-1],0)
        self.assertAlmostEqual(p.security_claim_value.iloc[-1],q*recipients['C']['raw'].close.iloc[-1])
        self.assertAlmostEqual(claims.cash_paid,q*.999)
        reconcile(assets,p,o,15,10,recipients,fx_override=fx)

    def test_claim_value_corruption_is_detected(self):
        assets,recipients,fx,claims,(_,p,o,_)=self.fixture()
        p.loc[p.index[-1],'security_claim_value']+=100
        with self.assertRaises(AssertionError):reconcile(assets,p,o,15,10,recipients,fx_override=fx)

    def test_in_kind_cannot_silently_drop_without_ledger(self):
        assets,_,fx,_,_=self.fixture()
        with self.assertRaises(ValueError):run(assets,'2020-01-01','2020-05-01',fx_override=fx)

if __name__=='__main__':unittest.main()
