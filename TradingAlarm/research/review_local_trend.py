import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from volume_units import split_consistent_volume
from local_trend_strength import local_trend_frame
from geometric_strength import strength_exposure

OUT=Path('results/strength-local-trend')
etf,_=load_extended();hk,_=load_assets();phases=[];errors=[]
for group,assets in [('etf17',etf),('hk7',hk)]:
 for symbol,a in assets.items():
  raw=a['raw'];p=a['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index)
  p=p.reindex(valid);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
  frames={name:local_trend_frame(p,v,joint) for name,joint in [('price',False),('volume',True)]}
  for name,f in frames.items():
   for year in range(2022,2027):
    e=pd.DataFrame(dict(model=(f.innovation/f.scale)**2,random_walk=(np.log(p).diff()/f.scale)**2)).loc[str(year)].dropna()
    errors.append(dict(group=group,symbol=symbol,model=name,year=year,n=len(e),model_sse=float(e.model.sum()),rw_sse=float(e.random_walk.sum())))
  if symbol not in ('USHJ512480','HK03033'):continue
  yy=p.loc['2026'];peak=yy.idxmax();fig,ax=plt.subplots(3,1,figsize=(13,9),sharex=True,layout='constrained')
  ax[0].plot(yy.index,yy/p.loc[:'2025-12-31'].iloc[-1]*100,color='black');ax[0].set_title(symbol+' | causal local linear trend | development 2026')
  for name,f in frames.items():
   state=strength_exposure(f.strength);change=state.diff().reindex(yy.index).fillna(0);off=state.loc[peak:].loc[lambda x:x.eq(0)]
   phases.append(dict(symbol=symbol,model=name,june_held_fraction=float(state.loc['2026-06'].mean()),held_at_peak=bool(state.loc[peak]),peak_date=str(peak.date()),first_flat_after_peak=str(off.index[0].date()) if len(off) else None,peak_to_flat=float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit',score=float(f.strength.loc[d])) for d in change.index[change.ne(0)]]))
   negative=f.velocity.loc[peak:].loc[lambda x:x.le(0)]
   phases[-1].update(first_nonpositive_slope_after_peak=str(negative.index[0].date()) if len(negative) else None,peak_to_nonpositive_slope=float(p.loc[negative.index[0]]/p.loc[peak]-1) if len(negative) else None)
   ax[1].plot(yy.index,f.strength.reindex(yy.index),label=name);ax[2].step(yy.index,state.reindex(yy.index),where='post',label=name)
  ax[1].axhline(5+5*np.tanh(1),ls=':',color='gray');ax[1].axhline(5,ls=':',color='gray');ax[1].set_ylim(0,10)
  ax[1].set_ylabel('strength');ax[2].set_ylabel('long state')
  for axis in ax:axis.grid(alpha=.2)
  ax[1].legend();ax[2].legend();fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(phases,indent=2))
pd.DataFrame(errors).to_csv(OUT/'forecast-errors.csv',index=False)
summary=pd.DataFrame(errors).groupby(['group','model','year'])[['n','model_sse','rw_sse']].sum();summary['mse_ratio']=summary.model_sse/summary.rw_sse
summary.to_csv(OUT/'forecast-summary.csv')
print(summary.to_string())
print(json.dumps(phases,indent=2))
