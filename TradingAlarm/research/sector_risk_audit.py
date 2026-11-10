"""Risk-constraint counterfactuals, not production candidates."""
import json
import numpy as np
from sector_factors import OUT,expanded_assets,allocator_factory
from portfolio_engine import run_portfolio
assets=expanded_assets();records=[]
for name,method,top,passive in [('rotation','short',3,False),('diversified','none',0,True)]:
 for budget in [True,False]:
  m,p,t,d=run_portfolio(assets,allocator_fn=allocator_factory(method,top),passive=passive,
      guard=False,drawdown_target=.20,scenario_budget=budget,rebalance_band=.02,minimum_fees=True,participation=.01)
  m.update(case=f'{name}-budget{budget}-no_guard');records.append(m)
  p.to_csv(OUT/(m['case']+'-path.csv'))
  print(m['case'],round(m['cagr']*100,2),round(m['max_drawdown']*100,2),flush=True)
(OUT/'risk-audit.json').write_text(json.dumps(records,indent=2))
