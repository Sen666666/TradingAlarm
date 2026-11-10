import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl');os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from volume_units import split_consistent_volume
from markov_trend_strength import markov_frame
from geometric_strength import strength_exposure
OUT=Path('results/strength-markov-state');assets,_=load_extended();reports=[]
for symbol in ('USHJ512480','HK03033'):
 a=assets[symbol];raw=a['raw'];p=a['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index);p=p.reindex(valid);v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid);yy=p.loc['2026-01-01':'2026-10-16'];peak=yy.idxmax();models={};rows=[]
 for name,joint,memory in [('memoryless',False,False),('price',False,True),('volume',True,True)]:
  f=markov_frame(p,v,joint,memory);models[name]=f.strength;state=strength_exposure(f.strength);changes=state.diff().reindex(yy.index).fillna(0);off=f.strength.loc[peak:].loc[lambda s:s.le(5)]
  row=dict(model=name,signals=[dict(date=str(d.date()),side='enter' if changes.loc[d]>0 else 'exit',score=float(f.strength.loc[d])) for d in changes.index[changes.ne(0)]],june_held_fraction=float(state.loc['2026-06'].mean()),peak_strength=float(f.strength.loc[peak]),held_at_peak=bool(state.loc[peak]),first_le5_after_peak=str(off.index[0].date()) if len(off) else None,peak_to_exit_signal_return=float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None);rows.append(row)
 reports.append(dict(symbol=symbol,models=rows));print(symbol,json.dumps(rows));pd.DataFrame(models).loc[yy.index].to_parquet(OUT/f'{symbol}-scores.parquet')
 fig,ax=plt.subplots(2,1,figsize=(13,7),sharex=True,layout='constrained');ax[0].plot(yy.index,yy/p.loc[:'2025-12-31'].iloc[-1]*100,color='black');ax[0].set_title(symbol+' | fixed Markov-state experiment, 2026 development')
 for name,score in models.items():ax[1].plot(yy.index,score.reindex(yy.index),label=name)
 ax[1].axhline(5,color='red',ls='--');ax[1].axhline(5+5*np.tanh(1),color='green',ls='--');ax[1].legend()
 for a in ax:a.grid(alpha=.2)
 fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(reports,indent=2)+'\n')
