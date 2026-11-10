"""Fixed21/126 horizon comparison with shared matured training observations."""
import json
import numpy as np
import pandas as pd
from stock_walkforward_rank import ROOT,FEATURES
from stock_entry_diagnostic import select
OUT=ROOT/'results/stock-forecast-horizon'

def fit_label(train,label):
 x=train[FEATURES].to_numpy();y=(train[label]-train.groupby('date')[label].transform('mean')).to_numpy();w=1/train.groupby('date').date.transform('size').to_numpy()
 return np.linalg.solve(x.T@(w[:,None]*x)+np.eye(len(FEATURES)),x.T@(w*y))

def train_sets(d,dt):
 window=d[d.date.lt(dt)&d.date.ge(dt-pd.DateOffset(months=60))]
 short=window[window.end21.lt(dt)&window.forward_21.notna()]
 common=window[window.end126.lt(dt)&window.forward_126.notna()&window.forward_21.notna()]
 return short,common

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'models':['short_latest','short_matched','long_matched'],'targets':[21,126],'fit':'Same rank features, alpha1, trailing60months, equal-date weight, min36common labeled dates','shared_training':'short_matched and long_matched use identical rows with both labels known and126session label end strictly before prediction date','control':'short_latest keeps usual21session maturity but same prediction dates','limitations':['Previously researched history; not pristine validation','Common training cases can favor survivors with available endpoints','126session labels overlap heavily and adjust-price factors can be revised','Price-label ranking, no account or execution proof; not a parameter search']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 raw=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');raw=raw[raw.active20.eq(20)].copy();d=raw.copy();d[FEATURES]=d.groupby('date')[FEATURES].rank(method='average',pct=True)-.5
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
 for h in [21,126]:d[f'end{h}']=d.date.map({dt:cal[i+h+1] for i,dt in enumerate(cal) if i+h+1<len(cal)})
 selected=[];coeff=[]
 for dt,g in d.groupby('date'):
  short,common=train_sets(d,dt)
  if common.date.nunique()<36:continue
  for name,train,label in [('short_latest',short,'forward_21'),('short_matched',common,'forward_21'),('long_matched',common,'forward_126')]:
   beta=fit_label(train,label);original=raw[raw.date.eq(dt)].copy();original['negative_score']=-(g[FEATURES].to_numpy()@beta)
   selected.append(select(original,'negative_score').assign(strategy=name));coeff.append(dict(date=dt,strategy=name,train_rows=len(train),train_dates=train.date.nunique(),max_label_end=train['end126' if name!='short_latest' else 'end21'].max(),**dict(zip(FEATURES,beta))))
  selected.append(select(raw[raw.date.eq(dt)],'atr_fraction').assign(strategy='low_atr'))
 s=pd.concat(selected);s.to_parquet(OUT/'selected.parquet',index=False);pd.DataFrame(coeff).to_csv(OUT/'coefficients.csv',index=False)
 rows=[]
 for h in [10,21,63,126]:
  mature=s[s.date.le(cal[-(h+2)])]
  for (strategy,dt),g in mature.groupby(['strategy','date']):
   v=g[f'forward_{h}'].dropna();rows.append(dict(strategy=strategy,date=dt,period='pre2022' if dt.year<2022 else '2022+',horizon=h,selected=len(g),labels=len(v),mean=float(v.mean())))
 t=pd.DataFrame(rows);t.to_csv(OUT/'by-date.csv',index=False);report=[]
 for (period,h),g in t.groupby(['period','horizon']):
  for coverage,part in [('available',g),('complete_dates',g[g.selected.eq(g.labels)])]:
   w=part.pivot(index='date',columns='strategy',values='mean').dropna();report.append(dict(period=period,horizon=int(h),coverage=coverage,dates=len(w),**{c:float(w[c].mean()) for c in w.columns},target_effect=float((w.long_matched-w.short_matched).mean()),training_lag_effect=float((w.short_matched-w.short_latest).mean())))
 (OUT/'summary.json').write_text(json.dumps(report,indent=2));print(pd.DataFrame(report).query("coverage=='available'").to_string(index=False))
if __name__=='__main__':main()
