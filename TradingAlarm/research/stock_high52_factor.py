"""One prespecified 252-session closing-high factor; matched-pool ridge ablation."""
import itertools,json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_walkforward_rank import ROOT,FEATURES,training_rows
from stock_entry_diagnostic import select
from build_stock_features import grouped
OUT=ROOT/'results/stock-high52-factor'
def high_ratio(close):
 return close/close.rolling(252,min_periods=252).max()
def fit(train,features):
 x=train[features].to_numpy();y=(train.forward_21-train.groupby('date').forward_21.transform('mean')).to_numpy();w=1/train.groupby('date').date.transform('size').to_numpy()
 return np.linalg.solve(x.T@(w[:,None]*x)+np.eye(len(features)),x.T@(w*y))
def main():
 OUT.mkdir(exist_ok=True)
 protocol=dict(source='https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2004.00695.x',hypothesis='Near52weekhigh adds selection information beyond existing momentum/risk/liquidity features',factor='current signalclose / trailing252market-session maximum signalclose includingcurrent; closing-high proxy, not exact paper replication',features=FEATURES+['high52'],models=['base_matched','plus_high52'],training='Original ridgealpha1,60months,min36dates,labelend<t; same eligiblepool andtrainingrows for both models',limitations=['Reusedsurvivor-dominatedhistory,not pristineoutofsample','Closehighproxy, not intradayhigh; missing observedprices forwardfilled forsignalonly','Existingbreakoutcandidatepool alreadyconditionson55dayhigh; tests incrementalinfo only','Price labels, not verifiedaccountreturn; missinglabels andterminalcorporateactions remain'],parameter_search=False)
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 raw=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');raw=raw[raw.active20.eq(20)].copy();wanted=set(raw.symbol);feature=[]
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.set_index('date').sort_index();h=high_ratio(f.signal_close);ds=raw.loc[raw.symbol.eq(symbol),'date'];feature.append(pd.DataFrame(dict(symbol=symbol,date=ds.to_numpy(),high52=h.reindex(ds).to_numpy())))
 features=pd.concat(feature);assert not features.duplicated(['symbol','date']).any();d=raw.merge(features,on=['symbol','date'],validate='one_to_one').dropna(subset=['high52']);assert d.high52.between(0,1).all()
 (OUT/'coverage.json').write_text(json.dumps(dict(original_candidates=len(raw),matched_candidates=len(d),excluded_missing_high52=len(raw)-len(d))))
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();d['label_end']=d.date.map({dt:cal[i+22] for i,dt in enumerate(cal) if i+22<len(cal)})
 allfeatures=FEATURES+['high52'];ranked=d.copy();ranked[allfeatures]=d.groupby('date')[allfeatures].rank(pct=True)-.5;selected=[];coeff=[]
 for dt,g in ranked.groupby('date'):
  train=training_rows(ranked,dt)
  if train.date.nunique()<36:continue
  assert train.label_end.max()<dt
  for name,fs in [('base_matched',FEATURES),('plus_high52',allfeatures)]:
   beta=fit(train,fs);original=d[d.date.eq(dt)].copy();original['negative_score']=-(g[fs].to_numpy()@beta);selected.append(select(original,'negative_score').assign(strategy=name));coeff.append(dict(date=dt,strategy=name,training_rows=len(train),max_label_end=train.label_end.max(),**dict(zip(fs,beta))))
 s=pd.concat(selected);s.to_parquet(OUT/'selected.parquet',index=False);pd.DataFrame(coeff).to_csv(OUT/'coefficients.csv',index=False);rows=[]
 for h in [21,126]:
  mature=s[s.date.le(cal[-(h+2)])]
  for (model,dt),g in mature.groupby(['strategy','date']):
   rows.append(dict(strategy=model,date=dt,period='pre2022' if dt.year<2022 else '2022+',horizon=h,selected=len(g),labels=int(g[f'forward_{h}'].notna().sum()),mean=float(g[f'forward_{h}'].mean())))
 t=pd.DataFrame(rows);t.to_csv(OUT/'by-date.csv',index=False);summary=[]
 for (period,h),g in t.groupby(['period','horizon']):
  for coverage,part in [('available',g),('complete_dates',g[g.selected.eq(g.labels)])]:
   w=part.pivot(index='date',columns='strategy',values='mean').dropna();summary.append(dict(period=period,horizon=int(h),coverage=coverage,dates=len(w),base=float(w.base_matched.mean()),plus=float(w.plus_high52.mean()),difference=float((w.plus_high52-w.base_matched).mean())))
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':main()
