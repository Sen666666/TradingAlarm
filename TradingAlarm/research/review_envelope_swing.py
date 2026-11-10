import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl');os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from swing_structure_strength import swing_frame
from geometric_strength import strength_exposure
OUT=Path('results/strength-envelope-swing');assets,_=load_extended();report=[]
for symbol in ['USHJ512480','HK03033']:
 a=assets[symbol];raw=a['raw'];p=a['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index);p=p.reindex(valid);f,events=swing_frame(p,envelope=True);state=strength_exposure(f.strength);yy=p.loc['2026-01-01':'2026-10-16'];peak=yy.idxmax();changes=state.diff().reindex(yy.index).fillna(0);off=f.strength.loc[peak:].loc[lambda s:s.le(5)]
 r=dict(symbol=symbol,signals=[dict(date=str(d.date()),side='enter' if changes.loc[d]>0 else 'exit',score=float(f.strength.loc[d])) for d in changes.index[changes.ne(0)]],june_held_fraction=float(state.loc['2026-06'].mean()),peak_strength=float(f.strength.loc[peak]),held_at_peak=bool(state.loc[peak]),first_le5_after_peak=str(off.index[0].date()) if len(off) else None,peak_to_exit_signal_return=float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None);report.append(r);print(r)
 (OUT/f'{symbol}-pivots.json').write_text(json.dumps(events,indent=2)+'\n');f.loc[yy.index].to_parquet(OUT/f'{symbol}-scores.parquet')
 fig,ax=plt.subplots(2,1,figsize=(13,7),sharex=True,layout='constrained');scale=p.loc[:'2025-12-31'].iloc[-1];ax[0].plot(yy.index,yy/scale*100,color='black',label='Price');ax[0].plot(yy.index,np.exp(f.last_high.reindex(yy.index))/scale*100,label='Latest confirmed high');ax[0].plot(yy.index,np.exp(f.last_low.reindex(yy.index))/scale*100,label='Latest confirmed low');ax[0].legend();ax[0].set_title(symbol+' | provisional envelope score; displayed levels are confirmed')
 ax[1].plot(yy.index,f.strength.reindex(yy.index));ax[1].axhline(5,color='red',ls='--');ax[1].axhline(5+5*np.tanh(1),color='green',ls='--')
 for a in ax:a.grid(alpha=.2)
 fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(report,indent=2)+'\n')
