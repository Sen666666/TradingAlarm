"""Dated diagnostic of frozen multi-scale score; no threshold selection."""
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
from volume_units import split_consistent_volume
from multiscale_trend_strength import multiscale_frame
from adaptive_geometric_strength import adaptive_frame
from geometric_strength import strength_exposure
OUT=Path('results/strength-multiscale-structure')
def main():
    assets,_=load_extended();report=[]
    for symbol in ('USHJ512480','HK03033'):
        a=assets[symbol];p=a['signal'].close;raw=a['raw'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(p.index)
        v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
        f=multiscale_frame(p.reindex(valid),v)
        old=adaptive_frame(p.reindex(valid),raw.close.reindex(valid),v).strength
        yy=p.loc['2026-01-01':'2026-10-16'];peak=yy.idxmax();models={}
        for name,score in [('adaptive',old),('multiscale',f.strength)]:
            held=strength_exposure(score);changes=held.diff().reindex(yy.index).fillna(0)
            events=[dict(date=str(d.date()),side='enter' if changes.loc[d]>0 else 'exit',score=float(score.loc[d])) for d in changes.index[changes.ne(0)]]
            off=score.loc[peak:].loc[lambda s:s.le(5)]
            monthly={str(m):float(g.mean()) for m,g in held.loc[yy.index].groupby(yy.index.to_period('M'))}
            models[name]={'events':events,'monthly_held_fraction':monthly,'score_at_peak':float(score.loc[peak]),'held_at_peak':bool(held.loc[peak]),'first_le5_after_peak':str(off.index[0].date()) if len(off) else None,'peak_to_exit_signal_return':float(p.loc[off.index[0]]/p.loc[peak]-1) if len(off) else None}
        report.append({'symbol':symbol,'peak_hindsight':str(peak.date()),'models':models})
        f.join(old.rename('adaptive')).loc[yy.index].to_parquet(OUT/f'{symbol}-scores.parquet')
        fig,ax=plt.subplots(3,1,figsize=(13,9),sharex=True,layout='constrained')
        ax[0].plot(yy.index,yy/p.loc[:'2025-12-31'].iloc[-1]*100,color='black');ax[0].set_title(symbol+' | 2026 structural diagnosis (development sample)');ax[0].set_ylabel('Price index')
        for name,score in [('adaptive',old),('multiscale',f.strength)]:ax[1].plot(yy.index,score.reindex(yy.index),label=name)
        ax[1].axhline(5,color='red',ls='--');ax[1].axhline(5+5*np.tanh(1),color='green',ls='--');ax[1].legend();ax[1].set_ylabel('Strength (different definitions)')
        for col in ('weekly','monthly','quarterly'):ax[2].plot(yy.index,f[col].reindex(yy.index),label=col)
        ax[2].axhline(0,color='grey');ax[2].legend();ax[2].set_ylabel('Signed path components')
        for axis in ax:axis.grid(alpha=.2)
        fig.savefig(OUT/f'{symbol}.png',dpi=130);plt.close(fig)
    (OUT/'phase-review.json').write_text(json.dumps(report,indent=2)+'\n')
    for row in report:
        print(row['symbol'])
        for name,m in row['models'].items():print(name,json.dumps(m))
if __name__=='__main__':main()
