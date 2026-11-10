"""Rerun frozen rank-buffer policy on an adversarial shifted market path."""
import json
from unittest.mock import patch
import pandas as pd
from portfolio_data import total_return_frame,fx_series
from portfolio_engine import run_portfolio,scenario_coefficients
from sector_factors import expanded_assets,allocator_factory
from sector_persistence import OUT
assets=expanded_assets();base=pd.read_csv(OUT/'pooled_rank_buffer-path.csv',index_col=0,parse_dates=True)
loss=sum(base['w_'+n]*c for n,c in scenario_coefficients(assets).items())
dd=base.nav*(1-loss)/base.nav.cummax().clip(lower=1)-1
joint=next(iter(assets.values()))['raw'].index
for a in assets.values():joint=joint.intersection(a['raw'].index)
anchor=dd.idxmin();date=joint[joint>anchor][0]
shocked={}
for n,a in assets.items():
 b=dict(a);raw=a['raw'].copy();scale=.7 if a['kind']=='equity' else (.9 if a['sector']=='gold' else .95)
 raw.loc[raw.index>=date,['open','high','low','close']]*=scale
 b['raw']=raw;b['signal']=total_return_frame(raw,a['dividends'],a['splits']);shocked[n]=b
def fx(index):
 out=fx_series(index);out.loc[out.index>=date]*=.9;return out
records=[]
for name,kw in [('shock',{}),('shock_cost_delay',{'cost_bps':30,'fx_bps':30,'extra_delay':2})]:
 with patch('portfolio_engine.fx_series',fx):
  m,p,t,d=run_portfolio(shocked,allocator_fn=allocator_factory('short',3,6),drawdown_target=.20,
   scenario_budget=True,rebalance_band=.02,minimum_fees=True,participation=.01,**kw)
 p.to_csv(OUT/(name+'-path.csv'));records.append(dict(case=name,**m));print(name,m['max_drawdown'],flush=True)
(OUT/'market-stress.json').write_text(json.dumps({'anchor':str(anchor.date()),'shock_date':str(date.date()),'static_gap_mdd':float(dd.min()),
 'assumptions':'Permanent price scale equity0.7,gold0.9,bond0.95,HKD0.9; recompute total-return signals with original cash dividend amounts; adversarial date, not independent validation.', 'records':records},indent=2))
