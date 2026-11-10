"""Audit existing policies against the user's clarified account-level objective.
Best historical windows are ex-post opportunities, not tradable market-cycle labels.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
out=[]
for version in ['sector-v1','sector-v2','sector-v3','sector-v4']:
 for row in json.loads((ROOT/f'results/{version}/results.json').read_text()):
  p=pd.read_csv(ROOT/f"results/{version}/{row['case']}-path.csv",index_col=0,parse_dates=True)
  r=p.return_daily;cum=(1+r).cumprod()
  running_low=np.minimum.accumulate(np.r_[1.,cum.to_numpy()])[1:]
  rebound=cum.to_numpy()/running_low-1
  entry={'version':version,'case':row['case'],'cagr':row['cagr'],'max_drawdown':row['max_drawdown'],
         'best_hindsight_low_to_later_high':float(rebound.max()),
         'positive_daily_return_concentration_top10':float(r.nlargest(10).sum()/r.clip(lower=0).sum()),
         'caution':'Daily-return sum share is not geometric P&L attribution. Best windows overlap and use hindsight; neither statistic forecasts future opportunities.'}
  for h in [63,126,252]:
   roll=(1+r).rolling(h).apply(np.prod,raw=True)-1
   best=roll.idxmax();entry[f'best_{h}_session_return']=float(roll.loc[best]);entry[f'best_{h}_end']=str(best.date())
  out.append(entry)
(ROOT/'results/account-tail-audit.json').write_text(json.dumps(out,indent=2))
for row in sorted(out,key=lambda x:-x['best_252_session_return'])[:8]:
 print(row['version'],row['case'],round(row['best_252_session_return']*100,2),'trough_rebound',round(row['best_hindsight_low_to_later_high']*100,2))
