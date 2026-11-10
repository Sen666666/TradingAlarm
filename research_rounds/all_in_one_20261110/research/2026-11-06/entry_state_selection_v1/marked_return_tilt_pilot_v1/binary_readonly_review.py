"""No new fit: binary-control attribution and historical2022 applicability only."""
from pathlib import Path
import pandas as pd,numpy as np,json,importlib.util
O=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('p',O/'run_pilot.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
x=pd.read_parquet(O/'PREDICTIONS_WITH_FINAL_DIAGNOSTICS.parquet');rows=[];states=[];bydate=[]
for mo,g in [('ALL',x)]+list(x.groupby('month')):
 for label,flag in [('ORIGINAL',pd.Series(True,index=g.index)),('RETAINED_BINARY',g.select_binary),('REJECTED_BINARY',~g.select_binary)]:
  z=g[flag];q=z[z.ordinary&z.entered];rows.append(dict(month=mo,mask=label,**p.outcome(q),positive_net_CNY=q.loc[q.net_pnl>0,'net_pnl'].sum(),negative_net_CNY=q.loc[q.net_pnl<0,'net_pnl'].sum(),unknown_feature_ordinary_n=int((~q.feature_known).sum()),unknown_feature_tail3_n=int((~q.feature_known&q.net_pnl.gt(9000)).sum()),unknown_feature_tail30_n=int((~q.feature_known&q.net_return_on_buy_cash.ge(.3)).sum())))
  states.append(dict(month=mo,mask=label,births=len(z),bought=int(z.entered.sum()),entry_UNKNOWN=int((~z.entered&z.status.str.contains('UNKNOWN')).sum()),held_UNKNOWN=int((z.entered&z.status.str.contains('UNKNOWN')).sum()),normal_unclosed=int((z.entered&~z.complete&~z.status.str.contains('UNKNOWN')).sum()),strict_M_closed_notordinary=int((z.complete&~z.ordinary).sum()),M_financial_known_nonordinary=int((z.complete&~z.ordinary&z.eval_financial_known).sum()),M_financial_unknown=int((z.complete&~z.eval_financial_known).sum()),q0=int(z.status.eq('PRECHECK_Q0_NO_SUBMIT').sum()),feature_UNKNOWN=int((~z.feature_known).sum())))
for day,g in x[x.ordinary&~x.select_binary].groupby('signal_day'):bydate.append(dict(day=str(day.date()),**p.outcome(g),positive_net_CNY=g.loc[g.net_pnl>0,'net_pnl'].sum(),negative_net_CNY=g.loc[g.net_pnl<0,'net_pnl'].sum()))
p.csv('BINARY_REJECTION_REVIEW.csv',rows);p.csv('BINARY_STATE_COVERAGE.csv',states);p.csv('BINARY_REJECTED_BY_DATE.csv',bydate)
legacy=p.R/'closed_price_supervised_pilot_support_v1';old=pd.read_parquet(legacy/'PREDICTIONS.parquet');old=old[old.window_label.eq('2022')&old.ordinary&old.entered];ols=[]
for name in ['original','pvr','interaction']:
 q=old[old['select_'+name]].copy();q['root_cluster']=q.price_root;ols.append(dict(model=name,**p.outcome(q)))
p.csv('LEGACY_2022H2_SAVED_PREDICTION_REFERENCE.csv',ols)
p.dump('BINARY_READONLY_QA.json',dict(refits=0,new_2022_backfill=False,source_hashes={str(legacy/'PREDICTIONS.parquet'):p.sha(legacy/'PREDICTIONS.parquet'),str(p.D/'LABEL_QA.json'):p.sha(p.D/'LABEL_QA.json')},earliest_old_binary_count_gate=json.loads((p.D/'LABEL_QA.json').read_text())['earliest_previous_pilot_count_support'],scope='Saved2022H2 predictions from previous protocol only; new2023/2024 data cannot enter2022 training. H1 not tested; earliest count threshold is not a marked-distribution support gate.'))
print(pd.DataFrame(rows).query("month=='ALL' or mask=='REJECTED_BINARY'").to_string(index=False));print(pd.DataFrame(states).query("month=='ALL'").to_string(index=False));print(pd.DataFrame(ols).to_string(index=False))
