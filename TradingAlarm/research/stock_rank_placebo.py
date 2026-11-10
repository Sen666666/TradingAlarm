"""Fixed within-date training-label permutation control, not formal significance."""
import json
import numpy as np
import pandas as pd
from stock_walkforward_rank import ROOT,OUT as BASE,FEATURES,training_rows,fit
OUT=ROOT/'results/stock-rank-placebo'
N=100

def shuffled_targets(d,seed=20261018,n=N):
 rng=np.random.default_rng(seed);y=d.forward_21.to_numpy(float);matrix=np.tile(y[:,None],(1,n+1))
 for _,g in d[d.forward_21.notna()].groupby('date',sort=True):
  idx=g.index.to_numpy();values=y[idx]
  for trial in range(1,n+1):matrix[idx,trial]=rng.permutation(values)
  matrix[idx]-=values.mean()
 return matrix

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'trials':N,'seed':20261018,'shuffle':'Training labels permuted within original signal date among nonmissing labels; same permutation history reused across rolling fits per trial','unchanged':'Current features, alpha1, rolling60months, maturity gate, top10 ranking, future evaluation labels','limitations':['Descriptive random-label controls, not formal pvalues: heteroskedasticity and repeated stock dependence break exchangeability','Does not account for all earlier research trials or repair universe/label omissions','No executable cost/cash account; controls can have different future-label availability']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');d=d[d.active20.eq(20)].sort_values(['date','symbol']).reset_index(drop=True);original=d.copy()
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();ends={dt:cal[i+22] for i,dt in enumerate(cal) if i+22<len(cal)};d['label_end']=d.date.map(ends)
 d[FEATURES]=d.groupby('date')[FEATURES].rank(method='average',pct=True)-.5;Y=shuffled_targets(d);rows=[]
 for dt,g in d.groupby('date'):
  train=training_rows(d,dt)
  if train.date.nunique()<36 or dt>cal[-23]:continue
  x=train[FEATURES].to_numpy();w=1/train.groupby('date').date.transform('size').to_numpy();B=np.linalg.solve(x.T@(w[:,None]*x)+np.eye(len(FEATURES)),x.T*w)
  betas=B@Y[train.index];np.testing.assert_allclose(betas[:,0],fit(train),atol=1e-12)
  score=g[FEATURES].to_numpy()@betas;raw=original.loc[g.index];labels=raw.forward_21.to_numpy();liquidity=raw.turnover60.to_numpy();symbols=raw.symbol.to_numpy()
  for trial in range(N+1):
   ix=np.lexsort((symbols,-liquidity,-score[:,trial]))[:10];valid=labels[ix];valid=valid[np.isfinite(valid)]
   rows.append(dict(date=dt,trial=trial,selected=len(ix),labels=len(valid),mean=float(valid.mean()) if len(valid) else np.nan))
 t=pd.DataFrame(rows);t.to_csv(OUT/'by-date.csv',index=False)
 actual=pd.read_csv(BASE/'by-date.csv',parse_dates=['date']).query("strategy=='ridge' and horizon==21").set_index('date')['mean']
 observed=t[t.trial.eq(0)].set_index('date')['mean'];np.testing.assert_allclose(observed,actual.reindex(observed.index),atol=1e-12)
 report=[]
 for period,g in [('pre2022',t[t.date.dt.year<2022]),('2022+',t[t.date.dt.year>=2022])]:
  wide=g.pivot(index='date',columns='trial',values='mean');diff=wide.iloc[:,1:].rsub(wide[0],axis=0).mean();randommeans=wide.iloc[:,1:].mean()
  report.append(dict(period=period,dates=len(wide),actual=float(wide[0].mean()),control_mean=float(randommeans.mean()),actual_minus_control_mean=float(diff.mean()),controls_at_least_actual=float(diff.le(0).mean()),control_p05=float(randommeans.quantile(.05)),control_p95=float(randommeans.quantile(.95)),min_priced_dates=int(wide.notna().sum().min()),max_priced_dates=int(wide.notna().sum().max())))
 (OUT/'summary.json').write_text(json.dumps(report,indent=2));print(pd.DataFrame(report).to_string(index=False))
if __name__=='__main__':main()
