import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from calibrated_local_trend import calibrated_frame,NAMES
from geometric_strength import strength_exposure

OUT=Path('results/strength-calibrated-local');etf,_=load_extended();hk,_=load_assets();rows=[];phases=[]
for group,assets in [('etf17',etf),('hk7',hk)]:
 for symbol,a in assets.items():
  raw=a['raw'];valid=raw.index[raw.volume.gt(0)].intersection(a['signal'].index);p=a['signal'].close.reindex(valid)
  f=calibrated_frame(p);f['rw_error']=np.log(p).diff()/np.sqrt(np.log(p).diff().shift().pow(2).rolling(21).mean()).clip(lower=1e-8)
  for year in range(2022,2027):
   yy=f.loc[str(year)].dropna();ready=yy.loc[yy.selection_ready.eq(1)]
   rows.append(dict(group=group,symbol=symbol,year=year,n=len(ready),random_walk_days=int(ready.selected.eq(0).sum()),model_sse=float(ready.standardized_error.pow(2).sum()),rw_sse=float(ready.rw_error.pow(2).sum()),nll_delta=float((ready.nll-ready.rw_nll).sum()),selection={NAMES[int(k)]:int(v) for k,v in ready.selected.value_counts().items()}))
  if symbol not in ('USHJ512480','HK03033'):continue
  state=strength_exposure(f.strength);yy=p.loc['2026'];peak=yy.idxmax();change=state.diff().reindex(yy.index).fillna(0);negative=f.velocity.loc[peak:].loc[lambda x:x.le(0)]
  phases.append(dict(symbol=symbol,june_held_fraction=float(state.loc['2026-06'].mean()),june_random_walk_fraction=float(f.selected.loc['2026-06'].eq(0).mean()),held_at_peak=bool(state.loc[peak]),first_nonpositive_after_peak=str(negative.index[0].date()) if len(negative) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit',strength=float(f.strength.loc[d])) for d in change.index[change.ne(0)]]))
  f.loc['2026'].assign(close=yy,exposure=state.reindex(yy.index)).to_csv(OUT/f'{symbol}-review.csv')
(OUT/'calibration-detail.json').write_text(json.dumps(rows,indent=2));(OUT/'phase-review.json').write_text(json.dumps(phases,indent=2))
summary=pd.DataFrame(rows).groupby(['group','year'])[['n','random_walk_days','model_sse','rw_sse','nll_delta']].sum()
summary['random_walk_fraction']=summary.random_walk_days/summary.n;summary['mse_ratio']=summary.model_sse/summary.rw_sse;summary['mean_nll_delta']=summary.nll_delta/summary.n
summary.to_csv(OUT/'calibration-summary.csv');print(summary.to_string());print(json.dumps(phases,indent=2))
