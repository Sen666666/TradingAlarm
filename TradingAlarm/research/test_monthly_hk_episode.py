import unittest
import pandas as pd
from monthly_hk_episode_audit import audit


class EpisodeAuditTests(unittest.TestCase):
    def fixture(self):
        idx=pd.bdate_range('2024-01-02',periods=3)
        a=dict(currency='HKD',splits=[],raw=pd.DataFrame({'close':[100.,110.,100.]},index=idx),
               dividends=[dict(ex_date=str(idx[1].date()),pay_date=str(idx[2].date()),amount=1.)])
        orders=[dict(symbol='A',date=str(d.date()),units=q,raw_open=p,fx=f,fee=0.) for d,q,p,f in zip(idx,[10,-10,1],[100,110,100],[1,2,3])]
        path=pd.DataFrame({'nav':[1.,1.00122,1.00122997]},index=idx)
        return {'A':a},path,orders,pd.Series([1.,2.,3.],index=idx)

    def test_dividend_owned_by_ex_date_episode_after_reopening(self):
        a,p,o,fx=self.fixture();eps,error=audit(a,p,o,10,fx)
        self.assertEqual(len(eps),2)
        self.assertEqual(eps[0]['paid_dividends'],30.)
        self.assertEqual(eps[1]['paid_dividends'],0.)
        self.assertEqual(eps[0]['local_price_pnl'],100.)
        self.assertEqual(eps[0]['security_fx_pnl'],1100.)
        self.assertAlmostEqual(eps[0]['pnl'],1229.97)
        self.assertEqual(eps[1]['pnl'],0.)

    def test_nav_error_is_not_hidden(self):
        a,p,o,fx=self.fixture();p.iloc[1,0]+=.01
        with self.assertRaises(AssertionError):audit(a,p,o,10,fx)

    def test_optional_daily_output_preserves_episodes_and_reconciles(self):
        a,p,o,fx=self.fixture();original,error=audit(a,p,o,10,fx);daily=[]
        observed,error2=audit(a,p,o,10,fx,daily_output=daily)
        self.assertEqual(original,observed);self.assertEqual(error,error2)
        self.assertAlmostEqual(sum(r['pnl'] for r in daily),1229.97)
        self.assertAlmostEqual(daily[-1]['pnl'],9.97)
        self.assertAlmostEqual(daily[-1]['fees'],.03)

    def test_nonzero_in_kind_rejected(self):
        a,p,o,fx=self.fixture();p['security_claim_value']=[0.,1.,1.]
        with self.assertRaises(AssertionError):audit(a,p,o,10,fx)

    def test_claim_owned_after_parent_exit(self):
        idx=pd.bdate_range('2024-01-02',periods=3)
        parent=dict(currency='HKD',splits=[],dividends=[],raw=pd.DataFrame({'close':[100.,90.,90.]},index=idx),
                    in_kind=[dict(ex_date=str(idx[1].date()),recipient='C',numerator=1,denominator=2)])
        child=dict(currency='HKD',splits=[],raw=pd.DataFrame({'close':[20.,20.,30.]},index=idx),
                   dividends=[dict(ex_date=str(idx[2].date()),pay_date=str(idx[2].date()),amount=2.)])
        orders=[dict(symbol='P',date=str(idx[i].date()),units=q,raw_open=price,fx=1.,fee=0.) for i,q,price in [(0,10,100),(1,-10,90)]]
        path=pd.DataFrame({'nav':[1.,1.,1.00005999],'security_claim_value':[0.,100.,150.]},index=idx)
        episodes,error=audit({'P':parent,'C':child},path,orders,10,pd.Series(1.,index=idx),allow_claims=True)
        self.assertEqual(len(episodes),1)
        self.assertEqual(episodes[0]['status'],'closed')
        self.assertEqual(episodes[0]['nontradable_claim_value'],150.)
        self.assertAlmostEqual(episodes[0]['pnl'],59.99)

if __name__=='__main__':unittest.main()
