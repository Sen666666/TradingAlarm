from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/conditional_distribution_v1')
c=pd.read_parquet(O/'PREPARED.parquet')
mods=json.loads((O/'MONTHLY_MODELS.json').read_text())
a=c[c.scale.le(1e-8)&c.risk_scale.notna()].copy()
a[['sid','day','native_close','floor','scale','risk_scale','CE']].to_csv(O/'SCALE_FLOOR_ANOMALIES.csv',index=False)
rows=[]
for r in mods:
 if not r['known']:continue
 tr=c[c.t.ge(r['cut']-504)&c.t.add(60).lt(r['cut'])&c.feature_known&c.label60_known&c.state.isin(['C','F','U'])]
 lo,med,hi=tr.risk_scale.quantile([.01,.5,.99]).to_numpy()
 rows.append(dict(month=r['month'],raw_p01=lo,raw_median=med,raw_p99=hi,training_mean=r['mean'][1],training_std=r['sd'][1],central98_standardized_width=(hi-lo)/r['sd'][1],source_floor_rows=int(tr.scale.le(1e-8).sum())))
pd.DataFrame(rows).to_csv(O/'RISK_FEATURE_EFFECTIVE_RANGE.csv',index=False)
def auc(y,x):
 y=np.asarray(y,bool);x=np.asarray(x);n=y.sum()
 if not (0<n<len(y)):return np.nan
 r=pd.Series(x).rank().to_numpy()
 return float((r[y].sum()-n*(n+1)/2)/(n*(len(y)-n)))
f=pd.read_csv(O/'ORIGINAL_ACTUAL_ASSOCIATION.csv');f['signal_year']=f.signal_day.str[:4];res=[]
for yr,g in f.groupby('signal_year'):
 for m in ['MIX_EV_ES','PC','DIRECT_MEAN','HISTORY_MEAN']:
  q=g[g.closed&g[m].notna()]
  res.append(dict(signal_year=yr,method=m,scored_closed=len(q),scored_open=int((~g.closed&g[m].notna()).sum()),auc=auc(q.round_pnl.gt(0),q[m]),source_winrate=float(q.round_pnl.gt(0).mean())))
pd.DataFrame(res).to_csv(O/'ACTUAL_ASSOCIATION_SIGNAL_YEAR.csv',index=False)
alert=dict(status='COMPLETED_FIXED_IMPLEMENTATION_WITH_MATERIAL_INPUT_SEMANTICS_CAVEAT',no_refit_after_results=True,no_posthoc_parameter_change=True,source_scale='PVR 1.4826 * prior63 median abs(log return), numerical lower floor1e-8',floor_rows=len(a),stocks=a.sid.nunique(),affected_training_months=[r['month']for r in rows if r['source_floor_rows']>0],meaning='Finite checks passed but numerical guard was treated as economic volatility. Mean/std were distorted before +/-5 clipping. Do not generalize this implementation result to the theory.',next_step_not_executed='Separately freeze economically meaningful scale and input range audit before any further fit.')
(O/'INPUT_SEMANTICS_ALERT.json').write_text(json.dumps(alert,ensure_ascii=False,indent=2))
print(json.dumps(alert,ensure_ascii=False))
