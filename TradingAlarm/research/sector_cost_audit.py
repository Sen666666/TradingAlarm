"""Post-result mechanism diagnostic, not a candidate search."""
import json
from portfolio_data import load_assets
from portfolio_engine import run_portfolio
from sector_experiment import OUT,fast_gate,rotation_allocator
assets,_=load_assets(); records=[]
for name,gate,alloc in [('slow',None,None),('fast_rotation',fast_gate,rotation_allocator)]:
 for budget in [True,False]:
  m,p,t,d=run_portfolio(assets,cost_bps=0,fx_bps=0,minimum_fees=False,participation=.01,scenario_budget=budget,drawdown_target=.20,gate_fn=gate,allocator_fn=alloc)
  records.append(dict(case=name,diagnostic='unrealistic zero-cost counterfactual',**m))
  p.to_csv(OUT/f'audit-{name}-budget-{budget}-path.csv')
  print(name,budget,round(m['cagr']*100,2),round(m['max_drawdown']*100,2),flush=True)
(OUT/'zero-cost-audit.json').write_text(json.dumps(records,indent=2))
