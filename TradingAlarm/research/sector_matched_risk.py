"""Exploratory paired block bootstrap, no post-selection significance claim."""
import json
import numpy as np
import pandas as pd
from sector_factors import OUT
records=json.loads((OUT/'results.json').read_text())
baseframe=pd.read_csv(OUT/'none-top0-passive-path.csv',index_col=0,parse_dates=True)
years=(baseframe.index[-1]-baseframe.index[0]).days/365.25
base=baseframe.return_daily.to_numpy()
rng=np.random.default_rng(20261017);n=len(base)
indices=np.concatenate([(np.arange(20)[None,:]+rng.integers(0,n,(2000,int(np.ceil(n/20))))[:,:,None]).reshape(2000,-1)],axis=1)[:,:n]%n
out=[]
for row in records:
 r=pd.read_csv(OUT/(row['case']+'-path.csv'),index_col=0).return_daily.to_numpy()
 target=min(r.std(),base.std());a=r*target/r.std();b=base*target/base.std()
 diff=a-b;samples=diff[indices].mean(axis=1)*252
 nav=np.cumprod(1+a);peak=np.maximum.accumulate(np.r_[1,nav])[1:]
 out.append({'case':row['case'],'active_scale':target/r.std(),'passive_scale':target/base.std(),
  'equal_vol_cagr':float(nav[-1]**(1/years)-1),
  'annualized_mean_excess':float(diff.mean()*252),'paired_95pct_interval':np.quantile(samples,[.025,.975]).tolist()})
(OUT/'matched-risk.json').write_text(json.dumps({'method':'Scale both realized return streams down to lower observed volatility; full-sample diagnostic, not tradable allocation. Paired circular20day bootstrap2000 runs. Postselection, not confirmatory inference.','records':out},indent=2))
for r in out:print(r['case'],round(r['annualized_mean_excess']*100,2),[round(x*100,2) for x in r['paired_95pct_interval']])
