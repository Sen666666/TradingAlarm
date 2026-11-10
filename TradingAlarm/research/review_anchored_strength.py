import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from anchored_trend_strength import anchored_strength_frame
from adaptive_geometric_strength import adaptive_frame
from geometric_strength import strength_exposure
from volume_units import split_consistent_volume
OUT=Path('results/strength-anchored')
a,_=load_extended();report=[]
for symbol in ('USHJ512480','HK03033'):
    asset=a[symbol];raw=asset['raw'];p=asset['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index)
    p=p.reindex(valid);v=split_consistent_volume(raw.volume,asset.get('splits',[])).reindex(valid)
    neutral=anchored_strength_frame(p,v,True)
    models={'adaptive':adaptive_frame(p,raw.close.reindex(valid),v).strength,'anchored':anchored_strength_frame(p,v).strength,'anchored_neutral':neutral.strength}
    yy=p.loc['2026-01-01':'2026-10-16'];peak=yy.idxmax();rows=[]
    for name,score in models.items():
        state=strength_exposure(score);change=state.diff().reindex(yy.index).fillna(0);off=score.loc[peak:].loc[lambda s:s.le(5)]
        rows.append({'model':name,'events':[{'date':str(d.date()),'side':'enter' if change.loc[d]>0 else 'exit','score':float(score.loc[d])} for d in change.index[change.ne(0)]],'held_fraction_june':float(state.loc['2026-06'].mean()),'peak_score':float(score.loc[peak]),'held_at_peak':bool(state.loc[peak]),'first_le5_after_peak':str(off.index[0].date()) if len(off) else None,'peak_to_exit_signal_return':float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None})
    report.append({'symbol':symbol,'models':rows});pd.DataFrame(models).loc[yy.index].to_parquet(OUT/f'{symbol}-scores.parquet')
    fig,axes=plt.subplots(3,1,figsize=(13,9),sharex=True,layout='constrained')
    axes[0].plot(yy.index,yy/p.loc[:'2025-12-31'].iloc[-1]*100,color='black');axes[0].set_title(symbol+' | 2026 anchored expert experiment (development)');axes[0].set_ylabel('Price index')
    for name,score in models.items():axes[1].plot(yy.index,score.reindex(yy.index),label=name)
    axes[1].axhline(5,color='red',ls='--');axes[1].axhline(5+5*np.tanh(1),color='green',ls='--');axes[1].legend();axes[1].set_ylabel('Trend strength')
    for c in ('linear_weight','quadratic_weight','neutral_weight'):axes[2].plot(yy.index,neutral[c].reindex(yy.index),label=c)
    axes[2].legend();axes[2].set_ylabel('Relative expert weights')
    for ax in axes:ax.grid(alpha=.2)
    fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(report,indent=2)+'\n')
for row in report:
    print(row['symbol'])
    for m in row['models']:print(json.dumps(m))
