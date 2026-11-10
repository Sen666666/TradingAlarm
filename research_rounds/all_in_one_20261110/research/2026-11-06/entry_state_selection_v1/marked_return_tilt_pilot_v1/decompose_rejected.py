"""Fixed prediction attribution only, no fit or horizon change."""
from pathlib import Path
import pandas as pd,numpy as np,json,importlib.util
O=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('p',O/'run_pilot.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
x=pd.read_parquet(O/'PREDICTIONS_WITH_FINAL_DIAGNOSTICS.parquet');x=x[x.ordinary&x.entered].copy();x['exit_age']=p.CAL.get_indexer(x.exit_day)-p.CAL.get_indexer(x.entry_day)+1
rows=[]
for mo,g in [('ALL',x)]+list(x.groupby('month')):
 for age,flag in [('LE120',g.exit_age<=120),('GT120',g.exit_age>120)]:
  for selected,mask in [('REJECTED',~g.select_marked),('RETAINED',g.select_marked),('ORIGINAL',pd.Series(True,index=g.index))]:
   q=g[flag&mask];rows.append(dict(month=mo,age=age,selected=selected,**p.outcome(q),positive_net_CNY=q.loc[q.net_pnl>0,'net_pnl'].sum(),negative_net_CNY=q.loc[q.net_pnl<0,'net_pnl'].sum(),feature_unknown_n=int((~q.feature_known).sum()),unknown_tail3_n=int((~q.feature_known&q.net_pnl.gt(9000)).sum()),unknown_tail3_net=q.loc[~q.feature_known&q.net_pnl.gt(9000),'net_pnl'].sum(),unknown_tail30_n=int((~q.feature_known&q.net_return_on_buy_cash.ge(.3)).sum()),unknown_tail30_net=q.loc[~q.feature_known&q.net_return_on_buy_cash.ge(.3),'net_pnl'].sum()))
p.csv('MARKED_REJECTED_EARLY_LATE.csv',rows)
print(pd.DataFrame(rows).query("month in ['ALL','2024-09'] and selected=='REJECTED'").to_string(index=False))
print('FALLBACK',p.outcome(x[~x.feature_known]))
