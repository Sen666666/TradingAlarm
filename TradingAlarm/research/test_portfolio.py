import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from portfolio_data import total_return_frame
from portfolio_engine import allocate,trend_gate,run_portfolio,industry_groups,constrain_scenario,remaining_scenario_budget,scenario_coefficients

class PortfolioTests(unittest.TestCase):
    def test_scenario_budget_is_derived_from_global_drawdown(self):
        assets={'a':dict(kind='equity',currency='CNY',sector='banks'),
                'b':dict(kind='equity',currency='HKD',sector='medicine')}
        proposed=pd.Series({'a':.4,'b':.3})
        for equity in [100,90,80,75,70]:
            w=constrain_scenario(proposed,assets,equity,100)
            loss=float((w*scenario_coefficients(assets)).sum())
            self.assertLessEqual(loss,remaining_scenario_budget(equity,100)+1e-12)
            if equity>=75:self.assertGreaterEqual(equity/100*(1-loss),.75-1e-12)
            if equity<=75:self.assertEqual(w.sum(),0)
            self.assertTrue((w<=proposed).all())
    def test_split_signal_continuity(self):
        idx=pd.bdate_range('2023-01-01',periods=4)
        raw=pd.DataFrame({c:[100.,100.,50.,51.] for c in ['open','high','low','close']},index=idx)
        tr=total_return_frame(raw,[],[dict(date=str(idx[2].date()),ratio=2)])
        self.assertEqual(tr.close.tolist(),[100,100,100,102])

    def test_correlated_assets_cannot_exceed_cluster_cap(self):
        r=np.sin(np.arange(70))*.01
        returns=pd.DataFrame({n:r for n in ['a','b','c']})
        assets={n:dict(kind='equity',currency='CNY') for n in returns}
        w,groups=allocate(returns,{n:True for n in returns},assets)
        self.assertLessEqual(w.sum(),.35000001)
        self.assertTrue((w<=.20).all())

    def test_future_prices_do_not_change_trend_gate(self):
        idx=pd.bdate_range('2020-01-01',periods=400)
        df=pd.DataFrame({'close':np.linspace(100,200,400)},index=idx)
        a=trend_gate(df);df.iloc[350:]*=.2
        pd.testing.assert_series_equal(a.iloc[:350],trend_gate(df).iloc[:350])

    def test_raw_split_account_and_lag(self):
        idx=pd.bdate_range('2020-01-01',periods=310)
        prices=np.ones(len(idx))*100;prices[280:]=50
        raw=pd.DataFrame({c:prices for c in ['open','high','low','close']},index=idx)
        splits=[dict(date=str(idx[280].date()),ratio=2)]
        a=dict(raw=raw,signal=total_return_frame(raw,[],splits),splits=splits,
               dividends=[],lot=1,currency='CNY',kind='defensive',sector='test')
        with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)):
            m,p,orders,decisions=run_portfolio({'a':a},start=str(idx[260].date()),
                                              passive=True,guard=False,cost_bps=0,fx_bps=0)
        self.assertAlmostEqual(m['total_return'],0)
        self.assertTrue((p.cash>=0).all())
        self.assertTrue(all(d['signal_cutoff']<d['date'] for d in decisions))
        self.assertTrue(all(o['date']!=str(idx[280].date()) for o in orders))

    def test_guard_waits_in_cash_and_never_resets_reported_drawdown(self):
        idx=pd.bdate_range('2020-01-01',periods=340)
        prices=np.ones(len(idx))*100; prices[280:]=50
        raw=pd.DataFrame({c:prices for c in ['open','high','low','close']},index=idx)
        a=dict(raw=raw,signal=raw,splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test')
        with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)),patch(
            'portfolio_engine.allocate',lambda *args:(pd.Series({'a':.8}),[['a']])):
            m,p,orders,_=run_portfolio({'a':a},start=str(idx[260].date()),passive=True,guard=True,cost_bps=0)
        sales=[pd.Timestamp(o['date']) for o in orders if o['units']<0]
        first_sale=sales[0]
        buys_after=[pd.Timestamp(o['date']) for o in orders if o['units']>0 and pd.Timestamp(o['date'])>first_sale]
        self.assertTrue(buys_after)
        self.assertGreater(idx.get_loc(buys_after[0])-idx.get_loc(first_sale),20)
        self.assertLess(m['max_drawdown'],-.39)
        self.assertLess(p.drawdown.iloc[-1],-.39)

    def test_full_portfolio_future_prices_do_not_change_past(self):
        idx=pd.bdate_range('2020-01-01',periods=360)
        price=np.linspace(100,180,len(idx))
        raw=pd.DataFrame({c:price.copy() for c in ['open','high','low','close']},index=idx)
        def asset(raw):
            return dict(raw=raw,signal=raw,splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test')
        with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)):
            _,before,_,_=run_portfolio({'a':asset(raw)},start=str(idx[260].date()),scenario_budget=True)
            changed=raw.copy();changed.iloc[330:]*=.3
            _,after,_,_=run_portfolio({'a':asset(changed)},start=str(idx[260].date()),scenario_budget=True)
        pd.testing.assert_frame_equal(before.loc[:idx[329]],after.loc[:idx[329]])

    def test_industry_bounds_include_broad_and_cross_market_healthcare(self):
        rng=np.random.default_rng(7)
        sectors=['broad_cn','broad_hk','medicine','medicine','banks','gold']
        assets={str(i):dict(kind='defensive' if s=='gold' else 'equity',currency='CNY',sector=s) for i,s in enumerate(sectors)}
        returns=pd.DataFrame(rng.normal(0,.01,(100,6)),columns=assets)
        w,_=allocate(returns,{n:True for n in assets},assets)
        groups=industry_groups(assets)
        self.assertEqual(set(groups['healthcare']),{'0','1','2','3'})
        self.assertLessEqual(max(w.loc[g].sum() for g in groups.values()),.35000001)

    def test_liquidity_partial_fills_retry_without_future_volume(self):
        idx=pd.bdate_range('2020-01-01',periods=280)
        raw=pd.DataFrame({c:100. for c in ['open','high','low','close']},index=idx)
        raw['volume']=10.
        a=dict(raw=raw,signal=raw,splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test',volume_multiplier=1)
        with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)):
            _,p,orders,_=run_portfolio({'a':a},start=str(idx[260].date()),passive=True,guard=False,
                                       participation=.1,minimum_fees=True)
        self.assertGreater(len(orders),1)
        self.assertTrue(all(abs(o['units'])<=1 for o in orders))
        self.assertTrue(all(o['fee']>=5 for o in orders))
        self.assertTrue((p.cash>=0).all())

    def test_zero_volume_placeholder_never_fills(self):
        idx=pd.bdate_range('2020-01-01',periods=280)
        raw=pd.DataFrame({c:100. for c in ['open','high','low','close']},index=idx)
        raw['volume']=10000.;raw.loc[idx[260:265],'volume']=0.
        a=dict(raw=raw,signal=raw,splits=[],dividends=[],lot=1,currency='CNY',kind='equity',sector='test')
        with patch('portfolio_engine.fx_series',lambda index:pd.Series(1.,index=index)):
            _,_,orders,_=run_portfolio({'a':a},start=str(idx[260].date()),passive=True,guard=False)
        self.assertTrue(orders)
        self.assertTrue(all(raw.loc[o['date'],'volume']>0 for o in orders))

if __name__=='__main__': unittest.main()
