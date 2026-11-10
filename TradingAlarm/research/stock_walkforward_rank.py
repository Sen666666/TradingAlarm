"""Fixed ridge cross-sectional ranking with strictly matured training labels."""
import json
import numpy as np
import pandas as pd
from stock_entry_diagnostic import ROOT,select
OUT=ROOT/'results/stock-walkforward-rank'
FEATURES=['momentum126_21','momentum252_21','atr_fraction','extension_atr','turnover60']

def fit(train):
 x=train[FEATURES].to_numpy(float);y=(train.forward_21-train.groupby('date').forward_21.transform('mean')).to_numpy()
 weights=1/train.groupby('date').date.transform('size').to_numpy()
 return np.linalg.solve(x.T@(weights[:,None]*x)+np.eye(len(FEATURES)),x.T@(weights*y))

def training_rows(d,dt):
 return d[d.date.lt(dt)&d.date.ge(dt-pd.DateOffset(months=60))&d.label_end.lt(dt)&d.forward_21.notna()]

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'features':FEATURES,'transform':'Within-date percentile rank minus0.5; current features only','model':'Ridge alpha1, no intercept; target21session price return minus training-date available-label mean; total weight1 per training date','training':'Trailing60calendar months, minimum36 distinct labeled signal dates; t+22 label end strictly before prediction date','selection':'Top10 predicted score; comparator RS/lowATR/all from exactly same prediction dates and current pool','limitations':['Reused historical universe and revised price factors, not untouched holdout','Missing training labels can omit failed/retired companies; no terminal-payout repair','Training fits21session signal returns, not80%accountcampaign objective','Overlapping dependent labels, no execution/cost/portfolio model','No hyperparameter tuning; still a new hypothesis in a large prior research search']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');d=d[d.active20.eq(20)].copy()
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
 ends={dt:cal[i+22] for i,dt in enumerate(cal) if i+22<len(cal)};d['label_end']=d.date.map(ends)
 ranked=d.copy();ranked[FEATURES]=d.groupby('date')[FEATURES].rank(method='average',pct=True)-.5
 predictions=[];coeff=[];selected=[]
 for dt,g in ranked.groupby('date'):
  train=training_rows(ranked,dt)
  if train.date.nunique()<36:continue
  beta=fit(train);g=g.copy();g['predicted_score']=g[FEATURES].to_numpy()@beta
  coeff.append(dict(date=dt,training_dates=int(train.date.nunique()),training_rows=len(train),max_label_end=train.label_end.max(),**dict(zip(FEATURES,beta))))
  predictions.append(g[['symbol','date','predicted_score']])
  original=d[d.date.eq(dt)].merge(g[['symbol','predicted_score']],on='symbol',validate='one_to_one')
  original['negative_score']=-original.predicted_score
  for name,p in [('ridge',select(original,'negative_score')),('rs',select(original,'rs_order')),('low_atr',select(original,'atr_fraction')),('all',original)]:selected.append(p.assign(strategy=name))
 selected=pd.concat(selected);selected.to_parquet(OUT/'selected.parquet',index=False);pd.DataFrame(coeff).to_csv(OUT/'coefficients.csv',index=False);pd.concat(predictions).to_parquet(OUT/'predictions.parquet',index=False)
 rows=[]
 for h in [10,21,63,126]:
  mature=selected[selected.date.le(cal[-(h+2)])]
  for (strategy,dt),g in mature.groupby(['strategy','date']):
   v=g[f'forward_{h}'].dropna();rows.append(dict(strategy=strategy,date=dt,period='pre2022' if dt.year<2022 else '2022+',horizon=h,selected=len(g),labels=len(v),mean=float(v.mean())))
 t=pd.DataFrame(rows);t.to_csv(OUT/'by-date.csv',index=False);summary=[]
 for (period,h),g in t.groupby(['period','horizon']):
  wide=g.pivot(index='date',columns='strategy',values='mean').dropna()
  summary.append(dict(period=period,horizon=int(h),dates=len(wide),**{name:float(wide[name].mean()) for name in ['ridge','rs','low_atr','all']},ridge_minus_all=float((wide.ridge-wide['all']).mean()),ridge_minus_low_atr=float((wide.ridge-wide.low_atr).mean())))
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':main()
