"""Attribution and counterfactual-market stress, never parameter selection."""
import json
from unittest.mock import patch
import numpy as np
import pandas as pd
from portfolio_data import ROOT,load_assets,total_return_frame,fx_series
from portfolio_engine import run_portfolio,industry_groups

OUT=ROOT/'results/portfolio-v3'

def metrics(r):
    nav=(1+r).cumprod();peak=np.maximum.accumulate(np.r_[1,nav.to_numpy()])[1:]
    years=(r.index[-1]-r.index[0]).days/365.25
    return dict(cagr=float(nav.iloc[-1]**(1/years)-1),max_drawdown=float((nav/peak-1).min()),
                realized_vol=float(r.std()*np.sqrt(252)),sharpe=float(r.mean()/r.std()*np.sqrt(252)))

def main():
    result=json.loads((OUT/'portfolio-results.json').read_text())
    base=pd.read_csv(OUT/'portfolio-frozen_trend_guard-path.csv',index_col=0,parse_dates=True)
    passive=pd.read_csv(OUT/'portfolio-passive_without_budget-path.csv',index_col=0,parse_dates=True)
    factor=base.return_daily.std()/passive.return_daily.std()
    matched=passive.return_daily*min(1,factor)
    controls={'ex_post_risk_matched_passive':{'scale':float(min(1,factor)),**metrics(matched),
               'limitation':'Uses full-period realized volatility, diagnostic only; not an investable ex-ante rule. Scales net returns and assumes zero cash return.'}}
    difference=(base.return_daily-matched).to_numpy()
    rng=np.random.default_rng(20261017);samples=[];n=len(difference)
    for _ in range(2000):
        starts=rng.integers(0,n,size=int(np.ceil(n/20)))
        paired=np.concatenate([difference[(np.arange(20)+s)%n] for s in starts])[:n]
        samples.append(float(paired.mean()*252))
    controls['paired_mean_difference_diagnostic']={
        'annualized_mean_daily_difference':float(difference.mean()*252),
        'block_bootstrap_95pct_interval':[float(np.quantile(samples,q)) for q in [.025,.975]],
        'block_sessions':20,'runs':2000,'seed':20261017,
        'limitation':'Exploratory paired interval after model selection and ex-post risk matching; not valid proof of discovery or prospective alpha.'}
    assets,_=load_assets()
    groups=industry_groups(assets)
    decisions=json.loads((OUT/'portfolio-frozen_trend_guard-decisions.json').read_text())
    maxima={}
    for d in decisions:
        w=pd.Series(d['weights'])
        assert w.max()<=.20+1e-9 and w.sum()<=1+1e-9
        assert sum(w[n] for n,a in assets.items() if a['kind']=='equity')<=.70+1e-9
        assert sum(w[n] for n,a in assets.items() if a['currency']=='HKD')<=.30+1e-9
        assert all(w[g].sum()<=.35+1e-9 for g in groups.values())
        assert all(w[g].sum()<=.35+1e-9 for g in d['clusters'])
        assert d['signal_cutoff']<d['date']
    orders=json.loads((OUT/'portfolio-frozen_trend_guard-orders.json').read_text())
    for o in orders:
        assert assets[o['symbol']]['raw'].loc[o['date'],'volume']>0
    for k,g in groups.items(): maxima[k]=float(base[['w_'+n for n in g]].sum(axis=1).max())
    # Choose the next joint session after the worst static-gap observation.
    # Adversarial choice is explicitly a stress; no claim of independent OOS.
    anchor=pd.Timestamp(result['stress']['worst_gap_date'])
    joint=next(iter(assets.values()))['raw'].index
    for a in assets.values():joint=joint.intersection(a['raw'].index)
    shock_date=joint[joint>anchor][0]
    shocked={}
    for n,a in assets.items():
        b=dict(a);raw=a['raw'].copy()
        multiplier=.70 if a['kind']=='equity' else (.90 if a['sector']=='gold' else .95)
        raw.loc[raw.index>=shock_date,['open','high','low','close']]*=multiplier
        b['raw']=raw;b['signal']=total_return_frame(raw,a['dividends'],a['splits']);shocked[n]=b
    def shocked_fx(index):
        fx=fx_series(index);fx.loc[fx.index>=shock_date]*=.90;return fx
    stress_paths=[]
    for label,kwargs in [('recomputed_market_shock',{}),('shock_high_cost_delayed',dict(cost_bps=30,fx_bps=30,extra_delay=2))]:
        with patch('portfolio_engine.fx_series',shocked_fx):
            m,p,trades,decisions=run_portfolio(shocked,minimum_fees=True,participation=.01,scenario_budget=True,**kwargs)
        p.to_csv(OUT/(label+'-path.csv'))
        stress_paths.append(dict(case=label,shock_date=str(shock_date.date()),**m))
        print(label,m,flush=True)
    yearly=[]
    for y,p in base.groupby(base.index.year):yearly.append(dict(year=int(y),total_return=float((1+p.return_daily).prod()-1),days=len(p)))
    output=dict(controls=controls,decision_constraints_verified=len(decisions),
                realized_industry_upper_bound_maxima=maxima,
                drift_note='Caps apply to decisions; realized closing exposure can drift before next rebalance.',
                market_path_stresses=stress_paths,yearly=yearly,
                stress_limits=['Shock date selected adversarially from observed holdings, not random forecast.',
                               'Market levels permanently scaled after shock; subsequent returns otherwise preserved.',
                               'Original cash dividend amounts retained; explicit corporate-action assumptions.',
                               'FX shock is a scenario valuation/execution factor, not a real executable quote.'])
    (OUT/'diagnostics.json').write_text(json.dumps(output,indent=2,allow_nan=False))
    print(json.dumps(controls,indent=2))
    print('Verified decisions',len(decisions),'industry drift maxima',maxima)

if __name__=='__main__':main()
