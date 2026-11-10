"""Run frozen rules and predeclared stresses; retain every result."""
import json
import numpy as np
import pandas as pd
from portfolio_data import ROOT,load_assets
from portfolio_engine import run_portfolio

OUT=ROOT/'results/portfolio-v3'
OUT.mkdir(parents=True,exist_ok=True)

def summarize_returns(r):
    nav=np.cumprod(1+np.asarray(r))
    peak=np.maximum.accumulate(np.r_[1.,nav])[1:]
    return dict(total_return=float(nav[-1]-1),max_drawdown=float((nav/peak-1).min()))

def main():
    assets,audit=load_assets()
    (OUT/'portfolio-data-audit.json').write_text(json.dumps(audit,indent=2))
    cases={'frozen_trend_guard':{},'trend_without_guard':{'guard':False},
           'passive_same_allocation':{'passive':True,'guard':False},
           'passive_without_budget':{'passive':True,'guard':False,'scenario_budget':False},
           'high_cost':{'cost_bps':30,'fx_bps':30},
           'delay_one_session':{'extra_delay':1},
           'cost_and_delay':{'extra_delay':2,'cost_bps':30,'fx_bps':30},
           'small_capital':{'initial':100000}}
    results=[];basepath=None;basedecisions=None
    for name,kwargs in cases.items():
        m,p,trades,decisions=run_portfolio(assets,minimum_fees=True,participation=.01,**{'scenario_budget':True,**kwargs})
        results.append(dict(case=name,**m))
        p.to_csv(OUT/f'portfolio-{name}-path.csv')
        (OUT/f'portfolio-{name}-orders.json').write_text(json.dumps(trades,indent=2))
        (OUT/f'portfolio-{name}-decisions.json').write_text(json.dumps(decisions,indent=2))
        if name=='frozen_trend_guard':basepath=p;basedecisions=decisions
        print(name,m,flush=True)
    # Injected mark-to-market shock at each observed closing allocation; not a
    # claim that an overnight stop can execute before the gap.
    shocks=pd.Series(0.,index=basepath.index)
    for n,a in assets.items():
        move=-.30 if a['kind']=='equity' else (-.10 if a['sector']=='gold' else -.05)
        if a['currency']=='HKD':move=(1+move)*.90-1
        shocks+=basepath['w_'+n]*move
    stressed_nav=basepath.nav*(1+shocks)
    previous_peak=basepath.nav.cummax().clip(lower=1)
    gap_dd=stressed_nav/previous_peak-1
    r=basepath.return_daily.copy()
    r.loc[r.nlargest(10).index]=0
    rng=np.random.default_rng(20261017);original=basepath.return_daily.to_numpy();n=len(original)
    draws=[]
    for _ in range(1000):
        starts=rng.integers(0,n,size=int(np.ceil(n/20)))
        sample=np.concatenate([original[(np.arange(20)+s)%n] for s in starts])[:n]
        draws.append(summarize_returns(sample)['max_drawdown'])
    stress={'gap_scenario':'equities -30%, gold -10%, bonds -5%, HKD -10%; applied to every observed closing holding',
            'worst_single_gap_loss':float(shocks.min()),'worst_gap_from_prior_peak':float(gap_dd.min()),
            'worst_gap_date':str(gap_dd.idxmin().date()),
            'remove_best_10_days':summarize_returns(r),
            'bootstrap':{'seed':20261017,'runs':1000,'block_days':20,'drawdown_quantiles':
              {str(q):float(np.quantile(draws,q)) for q in [.01,.05,.5,.95]},
              'fraction_drawdown_beyond_25pct':float(np.mean(np.array(draws)<-.25)),
              'limitation':'Resamples realized strategy returns, does not rerun signals/guards on synthetic market paths; not a probability forecast.'}}
    output={'status':'Preliminary raw-share portfolio research; no live performance claim',
            'records':results,'stress':stress,'scope':'11 ETFs, including 3 directly HK-listed ETFs; mandate-based conservative industry bounds',
            'limits':['Current survivor universe','Broad and mixed-technology ETF weights count fully in each industry risk bucket; upper bounds, not historical constituent estimates',
                      'Reference FX, prefunded fungible cross-venue cash approximation','Minimum fees and lagged-ADV participation modeled as assumptions; no exact spread or price-limit queue model',
                      'Corporate action tables sampled against primary announcements, not comprehensively audited',
                      'All historical data already observed; not fresh OOS performance']}
    (OUT/'portfolio-results.json').write_text(json.dumps(output,indent=2,allow_nan=False))
    print(json.dumps(stress,indent=2))

if __name__=='__main__':main()
