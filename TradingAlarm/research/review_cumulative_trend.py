import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from volume_units import split_consistent_volume
from cumulative_trend_strength import cumulative_frame
from geometric_strength import strength_exposure

OUT=Path('results/strength-cumulative');assets,_=load_extended();rows=[]
for symbol in ['USHJ512480','HK03033']:
 a=assets[symbol];raw=a['raw'];valid=raw.index[raw.volume.gt(0)].intersection(a['signal'].index)
 p=a['signal'].close.reindex(valid);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid);yy=p.loc['2026'];peak=yy.idxmax()
 fig,ax=plt.subplots(3,1,figsize=(13,9),sharex=True,layout='constrained');ax[0].plot(yy.index,yy/p.loc[:'2025-12-31'].iloc[-1]*100,color='black');ax[0].set_title(symbol+' | capped cumulative evidence | development2026')
 for name,joint in [('price',False),('volume',True)]:
  f=cumulative_frame(p,v,joint);state=strength_exposure(f.strength);change=state.diff().reindex(yy.index).fillna(0);off=state.loc[peak:].loc[lambda x:x.eq(0)]
  rows.append(dict(symbol=symbol,model=name,june_held_fraction=float(state.loc['2026-06'].mean()),held_at_peak=bool(state.loc[peak]),first_flat_after_peak=str(off.index[0].date()) if len(off) else None,peak_to_flat=float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit',score=float(f.strength.loc[d])) for d in change.index[change.ne(0)]]))
  ax[1].plot(yy.index,f.strength.reindex(yy.index),label=name);ax[2].step(yy.index,state.reindex(yy.index),where='post',label=name)
 ax[1].axhline(5+5*np.tanh(1),ls=':',color='gray');ax[1].axhline(5,ls=':',color='gray');ax[1].set_ylim(0,10);ax[1].legend();ax[2].legend()
 for axis in ax:axis.grid(alpha=.2)
 fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
