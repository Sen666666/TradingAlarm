"""Fixed-bin tail distribution across ETF/HK; descriptive, no fitted thresholds."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from volume_units import split_consistent_volume
OUT=Path('results/trend-tail-distribution')
def main():
 OUT.mkdir(exist_ok=True);parts=[];checks=[]
 protocol={'horizons':[21,63],'bins':[0,2,4,6,8,10],'tail_cutoffs':[.3,.8],'sample':'ETF17/HK7 2022-2026Oct16 development','paired_comparison':'8-10 versus6-8, same market/date/horizon, at least2 assets per bin; equal date weights','limits':['Small survivor universe; all data previously inspected.','Overlapping horizons and correlated assets; no independent observations or p-values claimed.','Future close returns are evaluation labels, not executable portfolio outcomes.','Stronger score does not necessarily imply higher expected return.']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 etf,_=load_extended();hk,_=load_assets()
 for group,assets in [('etf17',etf),('hk7',hk)]:
  for symbol,a in assets.items():
   ix=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);ix=ix[ix<=pd.Timestamp('2026-10-16')]
   c=a['signal'].close.reindex(ix);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(ix);s=pairwise_frame(c,v).strength
   k=len(c)//2;pd.testing.assert_series_equal(pairwise_frame(c.iloc[:k],v.iloc[:k]).strength,s.iloc[:k]);checks.append(symbol)
   for h in protocol['horizons']:
    f=pd.DataFrame({'date':ix,'score':s.to_numpy(),'return':(c.shift(-h)/c-1).to_numpy(),'label_end':pd.Series(ix,index=ix).shift(-h).to_numpy()})
    f=f.loc[f.date.ge('2022-01-01')].dropna();assert (f.label_end>f.date).all();assert f.label_end.max()<=pd.Timestamp('2026-10-16')
    f['group']=group;f['symbol']=symbol;f['horizon']=h;parts.append(f)
 d=pd.concat(parts,ignore_index=True);d['year']=d.date.dt.year;d['bin']=pd.cut(d.score,[-1e-12,2,4,6,8,10],labels=['0-2','2-4','4-6','6-8','8-10']).astype(str)
 d['tail30']=d['return'].ge(.3);d['tail80']=d['return'].ge(.8);d['loss']=d['return'].lt(0);d['loss30']=d['return'].le(-.3)
 d.to_parquet(OUT/'labeled.parquet',index=False)
 summary=d.groupby(['group','year','horizon','bin']).agg(n=('return','size'),mean=('return','mean'),median=('return','median'),p90=('return',lambda x:x.quantile(.9)),tail30=('tail30','mean'),tail80=('tail80','mean'),loss=('loss','mean'),loss30=('loss30','mean')).reset_index();summary.to_csv(OUT/'distribution.csv',index=False)
 daily=d.groupby(['group','year','horizon','date','bin']).agg(n=('return','size'),mean=('return','mean'),tail30=('tail30','mean'),tail80=('tail80','mean'),loss30=('loss30','mean')).reset_index();paired=[]
 for (g,y,h),f in daily.groupby(['group','year','horizon']):
  f=f.loc[f.n.ge(2)&f.bin.isin(['6-8','8-10'])]
  p=f.pivot(index='date',columns='bin',values=['mean','tail30','tail80','loss30']).dropna()
  if p.empty or not all(b in p.columns.get_level_values(1) for b in ['6-8','8-10']):continue
  row=dict(group=g,year=int(y),horizon=int(h),paired_dates=len(p))
  for metric in ['mean','tail30','tail80','loss30']:row[metric+'_high_minus_moderate']=float((p[metric]['8-10']-p[metric]['6-8']).mean())
  paired.append(row)
 pd.DataFrame(paired).to_csv(OUT/'paired-summary.csv',index=False)
 report={'prefix_checks':len(checks),'labeled_rows':len(d),'paired':paired,'status':'development_diagnostic','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(OUT/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(pd.DataFrame(paired).to_string(index=False))
if __name__=='__main__':main()
