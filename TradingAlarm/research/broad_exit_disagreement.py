"""Frozen exit-disagreement audit on validated485A shares, without execution selection."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from trend_exit_disagreement import features,forward_label
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from ths_volume_units import ths_split_consistent_volume
OUT=Path('results/broad-exit-disagreement')
FEATURES=['fast5','drawdown21','down_volume_share5','volume_ratio5_21']
def contrasts(data):
 rows=[]
 for year,g in data.groupby('year'):
  for feature in FEATURES:
   cut=g[feature].median();lo=g.loc[g[feature].le(cut)];hi=g.loc[g[feature].gt(cut)]
   rows.append(dict(year=int(year),feature=feature,n=len(g),cutoff=float(cut),low_count=len(lo),high_count=len(hi),low_forward21=float(lo.forward21.mean()),high_forward21=float(hi.forward21.mean()),high_minus_low=float(hi.forward21.mean()-lo.forward21.mean())))
 return pd.DataFrame(rows)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(manifest='data/ths-refresh-20261018/validated-input-balanced-second500.json',start='2024-01-01',end='2026-10-16',events='All observed positivevolume pairwisevolume zeroexit signals while symmetric variant remainslong; no executablefillselection',features=FEATURES,horizon=21,comparison='Same frozen annualmedian diagnostic as ETF/HK. Additional same-date median contrasts with >=6events, datebalanced yearmeans to diagnose marketcalendar concentration.',limits='No adoptedthreshold. Annualmedians and outcome labels retrospective. Surviving covered universe.21observedbars not calendar days; lateevents immature excluded with counts. NoaccountPNL orcausalproof.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));root=Path('data/ths-refresh-20261018');manifest=json.loads(Path(protocol['manifest']).read_text());rows=[];cache=[];immature=0
 for n,r in enumerate(manifest['records']):
  p=root/f"{r['ths_symbol']}-signal.parquet";q=root/'rights'/f"{r['ths_symbol']}.json";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];assert hashlib.sha256(q.read_bytes()).hexdigest()==r['rights_sha256']
  f=pd.read_parquet(p).loc[:protocol['end']];v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f.loc[f.observed_bar&f.volume.gt(0)];c=obs.signal_close;v=v.reindex(c.index);score=pairwise_frame(c,v).strength;zero=strength_exposure(score);wide=strength_exposure(score,5-5*np.tanh(1));feat=features(c,v);event=zero.diff().lt(0)&wide.eq(1)
  saved=feat.assign(strength=score,zero=zero,wide=wide,symbol=r['symbol']);saved.index.name='date';cache.append(saved.loc[protocol['start']:].reset_index())
  for i in np.flatnonzero(event.to_numpy()):
   dt=c.index[i]
   if dt<pd.Timestamp(protocol['start']):continue
   label=forward_label(c,i)
   if label is None:immature+=1;continue
   rows.append(dict(symbol=r['symbol'],date=str(dt.date()),year=dt.year,**feat.iloc[i].to_dict(),**label))
  if (n+1)%100==0:print('symbols',n+1,flush=True)
 data=pd.DataFrame(rows);assert not data.duplicated(['symbol','date']).any();assert data.label_end.le(protocol['end']).all();data.to_parquet(OUT/'events.parquet',index=False);pd.concat(cache,ignore_index=True).to_parquet(OUT/'all-observed-signals.parquet',index=False);report=contrasts(data);report.to_csv(OUT/'feature-contrasts.csv',index=False)
 daily=[]
 for date,g in data.groupby('date'):
  if len(g)<6:continue
  for feature in FEATURES:
   cut=g[feature].median();lo=g.loc[g[feature].le(cut)];hi=g.loc[g[feature].gt(cut)]
   if len(lo) and len(hi):daily.append(dict(date=date,year=int(date[:4]),feature=feature,high_minus_low=float(hi.forward21.mean()-lo.forward21.mean()),n=len(g)))
 d=pd.DataFrame(daily);d.to_csv(OUT/'same-date-contrasts.csv',index=False);d.groupby(['year','feature']).agg(dates=('date','size'),mean_difference=('high_minus_low','mean'),positive_fraction=('high_minus_low',lambda x:float(x.gt(0).mean()))).to_csv(OUT/'date-balanced-summary.csv')
 (OUT/'validation.json').write_text(json.dumps(dict(verified_hashes=970,complete_events=len(data),immature_events=immature,year_counts=data.groupby('year').size().to_dict(),unique_events=True,all_labels_within_cutoff=True),indent=2));print(report.to_string(index=False))
if __name__=='__main__':main()
