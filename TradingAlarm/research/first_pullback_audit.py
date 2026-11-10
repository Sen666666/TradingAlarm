"""First short-negative event inside a known original long episode, no fitted rule."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from trend_exit_disagreement import features
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/first-pullback-audit')
FEATURES=['drawdown21','down_volume_share5','volume_ratio5_21']

def first_events(base,fast):
 if not base.index.equals(fast.index):raise ValueError('Misaligned inputs')
 armed=False;previous=None;result=[]
 for value,direction in zip(base,fast):
  current=bool(value)
  if not current:armed=False
  elif previous is False:armed=True
  event=armed and pd.notna(direction) and direction<=0
  result.append(bool(event))
  if event:armed=False
  previous=current
 return pd.Series(result,index=base.index)

def labels(close,date,horizon):
 i=close.index.get_loc(date)
 if i+horizon>=len(close):return None
 forward=close.iloc[i+1:i+horizon+1]/close.iloc[i]-1
 return dict(forward_return=float(forward.iloc[-1]),forward_mfe=float(forward.max()),forward_mae=float(forward.min()),label_end=str(forward.index[-1].date()))

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(event='First fast5 <=0 while original pairwise-volume exposure is still1; one per known 0-to-1 original episode. Exclude initially active left-censored episode.',features=FEATURES,horizons=[5,21],split='Same-date within-feature median, minimum6 complete-label events, >=3 each side; only A485 can generally support this. Natural volume states down_volume_share5>0.5 and volume_ratio5_21>1 also reported allmarkets/year.',hypothesis='At the first short-negative event, high down-day volume share or expanding volume predicts more sustained deterioration; smaller drawdown predicts better recovery. No trained cutoff or strategy adoption.',limits=['Selected survivor development data, no independent holdout.','Future observed-close labels are descriptive, not executable exit profits.','Same-date splits condition on label availability; diagnostics only, not deployable filters.','Overlapping horizons and common market events are not independent samples; no nominal significance claims.','Sparse ETF/HK events cannot establish broad cross-market generalization.'])
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2))
 rows=[];hashes={};prefix=0;incomplete=0;total_events=0
 def collect(group,symbol,c,f,base,start):
  nonlocal prefix,incomplete,total_events
  event=first_events(base,f.fast5)
  for n in [len(base)//2,len(base)-1]:
   pd.testing.assert_series_equal(first_events(base.iloc[:n],f.fast5.iloc[:n]),event.iloc[:n]);prefix+=1
  for date in event.index[event]:
   if date<pd.Timestamp(start):continue
   total_events+=1
   for h in protocol['horizons']:
    label=labels(c,date,h)
    if label is None:incomplete+=1;continue
    rows.append(dict(group=group,symbol=symbol,date=date,year=date.year,horizon=h,**f.loc[date,FEATURES].to_dict(),**label))
 root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());cachepath=Path('results/broad-exit-disagreement/all-observed-signals.parquet');cache=pd.read_parquet(cachepath);hashes[str(cachepath)]=hashlib.sha256(cachepath.read_bytes()).hexdigest()
 for r in manifest['records']:
  p=root/f"{r['ths_symbol']}-signal.parquet";digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest==r['signal_sha256'];hashes[str(p)]=digest
  raw=pd.read_parquet(p);c=raw.loc[raw.observed_bar&raw.volume.gt(0),'signal_close'].loc[:'2026-10-16'];f=cache[cache.symbol.eq(r['symbol'])].set_index('date').sort_index();collect('a485',r['symbol'],c,f,f.zero,'2024-01-01')
 from hk_extension import load_extended
 from hk_in_kind_campaign import load_assets
 etf,_=load_extended();hk,_=load_assets()
 for group,assets in [('etf17',etf),('hk7',hk)]:
  for symbol,a in assets.items():
   valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);c=a['signal'].close.reindex(valid).loc[:'2026-10-16'];v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(c.index);f=features(c,v);base=strength_exposure(pairwise_frame(c,v).strength);collect(group,symbol,c,f,base,'2022-01-01')
 table=pd.DataFrame(rows);assert not table.duplicated(['group','symbol','date','horizon']).any();assert table.label_end.le('2026-10-16').all();table.to_parquet(OUT/'events.parquet',index=False)
 natural=[]
 for (group,year,h),g in table.groupby(['group','year','horizon']):
  for feature,cut in [('down_volume_share5',.5),('volume_ratio5_21',1.)]:
   hi=g[g[feature]>cut];lo=g[g[feature]<=cut]
   natural.append(dict(group=group,year=int(year),horizon=int(h),feature=feature,high_n=len(hi),low_n=len(lo),missing_n=int(g[feature].isna().sum()),high_return=float(hi.forward_return.mean()),low_return=float(lo.forward_return.mean()),high_minus_low=float(hi.forward_return.mean()-lo.forward_return.mean()),high_negative=float(hi.forward_return.lt(0).mean()),low_negative=float(lo.forward_return.lt(0).mean())))
 pd.DataFrame(natural).to_json(OUT/'natural-volume-contrasts.json',orient='records',indent=2)
 daily=[]
 for (group,date,h),g in table.groupby(['group','date','horizon']):
  if len(g)<6:continue
  for feature in FEATURES:
   cut=g[feature].median();lo=g[g[feature]<=cut];hi=g[g[feature]>cut]
   if min(len(lo),len(hi))<3:continue
   daily.append(dict(group=group,date=date,year=date.year,horizon=h,feature=feature,n=len(lo)+len(hi),missing_n=int(g[feature].isna().sum()),cut=float(cut),high_minus_low=float(hi.forward_return.mean()-lo.forward_return.mean()),negative_probability_diff=float(hi.forward_return.lt(0).mean()-lo.forward_return.lt(0).mean())))
 daily=pd.DataFrame(daily);daily.to_parquet(OUT/'same-date-contrasts.parquet',index=False)
 summary=daily.groupby(['group','year','horizon','feature']).agg(dates=('date','size'),mean_difference=('high_minus_low','mean'),positive_fraction=('high_minus_low',lambda x:float(x.gt(0).mean()))).reset_index();summary.to_json(OUT/'date-balanced-summary.json',orient='records',indent=2)
 (OUT/'validation.json').write_text(json.dumps(dict(input_hashes=hashes,prefix_checks=prefix,events=total_events,complete_horizon_rows=len(table),immature_horizon_rows=incomplete,assets=509,group_counts=table.groupby('group').size().to_dict()),indent=2));print(summary[summary.horizon.eq(21)].to_string(index=False));print(pd.DataFrame(natural).query('horizon==21 and group!="a485"').to_string(index=False))
if __name__=='__main__':main()
