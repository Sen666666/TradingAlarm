"""Fixed leave-one-feature-out refits, not selection of the best tested variant."""
import json
import numpy as np
import pandas as pd
from stock_walkforward_rank import ROOT,OUT as BASE,FEATURES,training_rows
OUT=ROOT/'results/stock-rank-ablation'

def fit_features(train,features):
 x=train[features].to_numpy();y=(train.forward_21-train.groupby('date').forward_21.transform('mean')).to_numpy();w=1/train.groupby('date').date.transform('size').to_numpy()
 return np.linalg.solve(x.T@(w[:,None]*x)+np.eye(len(features)),x.T@(w*y))

def main():
 OUT.mkdir(exist_ok=True)
 variants={'full':FEATURES,**{'without_'+f:[x for x in FEATURES if x!=f] for f in FEATURES},'atr_only':['atr_fraction']}
 protocol={'variants':variants,'method':'Refit every version with ridge alpha1, identical60month matured labels and dates; no hyperparameter tuning','purpose':'Conditional contribution diagnostic, not choosing maximum historical result','limitations':['Correlated features mean leave-one-out effects are not causal attribution','Reused history and multiple variants; no untouched holdout','Signal return only, missing outcomes, no execution/account validation']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');d=d[d.active20.eq(20)].sort_values(['date','symbol']).reset_index(drop=True);raw=d.copy()
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();ends={dt:cal[i+22] for i,dt in enumerate(cal) if i+22<len(cal)};d['label_end']=d.date.map(ends);d[FEATURES]=d.groupby('date')[FEATURES].rank(method='average',pct=True)-.5
 rows=[];coeff=[]
 for dt,g in d.groupby('date'):
  train=training_rows(d,dt)
  if train.date.nunique()<36:continue
  original=raw.loc[g.index]
  for name,features in variants.items():
   beta=fit_features(train,features);score=g[features].to_numpy()@beta;ix=np.lexsort((original.symbol.to_numpy(),-original.turnover60.to_numpy(),-score))[:10];selected=original.iloc[ix]
   coeff.append(dict(date=dt,variant=name,**dict(zip(features,beta))))
   for h in [10,21,63,126]:
    if dt>cal[-(h+2)]:continue
    values=selected[f'forward_{h}'].dropna();rows.append(dict(date=dt,variant=name,horizon=h,selected=len(selected),labels=len(values),mean=float(values.mean()),period='pre2022' if dt.year<2022 else '2022+'))
 table=pd.DataFrame(rows);table.to_csv(OUT/'by-date.csv',index=False);pd.DataFrame(coeff).to_csv(OUT/'coefficients.csv',index=False)
 old=pd.read_csv(BASE/'by-date.csv',parse_dates=['date']);old=old[old.strategy.eq('ridge')].set_index(['date','horizon'])['mean'];current=table[table.variant.eq('full')].set_index(['date','horizon'])['mean'];np.testing.assert_allclose(current,old.reindex(current.index),atol=1e-12)
 report=[]
 for (period,h),g in table.groupby(['period','horizon']):
  for coverage,part in [('available',g),('complete_dates',g[g.selected.eq(g.labels)])]:
   wide=part.pivot(index='date',columns='variant',values='mean')
   for name in variants:
    pair=wide[['full',name]].dropna() if name!='full' else wide[['full']].dropna()
    delta=pair[name]-pair['full']
    report.append(dict(period=period,horizon=int(h),coverage=coverage,variant=name,dates=len(pair),mean=float(pair[name].mean()),difference_from_full=float(delta.mean()),positive_years=int(delta.groupby(delta.index.year).mean().gt(0).sum())))
 (OUT/'summary.json').write_text(json.dumps(report,indent=2));print(pd.DataFrame(report).query("horizon==21 and coverage=='available'").to_string(index=False))
if __name__=='__main__':main()
