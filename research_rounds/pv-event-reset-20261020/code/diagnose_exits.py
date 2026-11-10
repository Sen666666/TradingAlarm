"""Frozen-scope retrospective descriptors; no new trading conditions."""
from pathlib import Path
import pandas as pd,numpy as np,json
b=Path(__file__).resolve().parents[1];p=json.loads((b/'results/protocol.json').read_text());source=Path(p['source']);rows=[]
for path in sorted(source.glob('*-signals.csv')):
 f=pd.read_csv(path,index_col='date',parse_dates=True);f=f.loc[f.close.gt(0)&f.volume.gt(0)&np.isfinite(f.close)&np.isfinite(f.volume)];y=np.log(f.close)
 for date,row in f.loc[f.exited.eq(1)].iterrows():
  i=f.index.get_loc(date)
  for horizon in [5,21,63]:
   valid=i+horizon<len(f);future=y.iloc[i+1:i+horizon+1]-y.iloc[i]
   rows.append(dict(symbol=path.name.removesuffix('-signals.csv'),date=str(date.date()),up_detector=bool(row.leg_direction==1),horizon=horizon,complete=valid,log_change=float(future.iloc[-1]) if valid else None,max_log_move=float(future.max()) if valid else None,min_log_move=float(future.min()) if valid else None))
f=pd.DataFrame(rows);f.to_csv(b/'results/exit-futures.csv',index=False)
summary=[]
for (up,h),g in f.groupby(['up_detector','horizon']):
 v=g.loc[g.complete];summary.append(dict(up_detector=bool(up),horizon=int(h),all_n=len(g),complete_n=len(v),positive_n=int(v.log_change.gt(0).sum()),mean_log_pct=float(v.log_change.mean()*100),median_log_pct=float(v.log_change.median()*100)))
(b/'results/exit-futures-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
