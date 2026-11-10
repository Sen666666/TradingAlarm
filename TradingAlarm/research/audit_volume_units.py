import json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl');os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from geometric_strength import geometric_frame,strength_exposure
from adaptive_geometric_strength import adaptive_frame
from volume_units import split_consistent_volume
ROOT=Path(__file__).resolve().parent

def main():
    out=ROOT/'results/strength-volume-units';rows=[]
    for group,assets in [('etf17',load_extended()[0]),('hk7',load_assets()[0])]:
        for symbol,a in assets.items():
            if not a['splits']:continue
            raw=a['raw'];p=a['signal'].close;volume=raw.volume;corrected=split_consistent_volume(volume,a['splits']);valid=raw.index[volume.gt(0)].intersection(p.index)
            series={}
            for model in ('geometry','linear','adaptive'):
                scores=[]
                for v in (volume,corrected):
                    f=adaptive_frame(p.loc[valid],raw.close.loc[valid],v.loc[valid]) if model=='adaptive' else geometric_frame(p.loc[valid],raw.close.loc[valid],v.loc[valid],degree=1 if model=='linear' else 2)
                    scores.append(f.strength)
                before,after=scores;old=strength_exposure(before);new=strength_exposure(after);ix=before.loc['2022-01-01':'2026-10-16'].index
                changed=ix[old.loc[ix].ne(new.loc[ix])];rows.append({'group':group,'symbol':symbol,'model':model,'split_events':a['splits'],'changed_state_days':len(changed),'changed_dates':[str(d.date()) for d in changed],'max_score_difference':float((before.loc[ix]-after.loc[ix]).abs().max())})
                series[model]=(before,after)
            if symbol=='USHJ512480':
                ix=p.loc['2026-06-01':'2026-08-15'].index
                fig,axs=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
                axs[0].plot(ix,(volume/volume.shift().rolling(21).median()).loc[ix],label='Raw share units',color='#dc2626')
                axs[0].plot(ix,(corrected/corrected.shift().rolling(21).median()).loc[ix],label='Split-consistent share units',color='#2563eb');axs[0].set_title('512480: July split volume-unit correction (no parameter changes)');axs[0].set_ylabel('Volume / prior median');axs[0].legend()
                b,c=series['adaptive'];axs[1].plot(ix,b.loc[ix],label='Original adaptive strength',color='#dc2626');axs[1].plot(ix,c.loc[ix],label='Corrected volume input',color='#2563eb',ls='--');axs[1].axhline(5,color='gray',ls=':');axs[1].set_ylabel('Strength');axs[1].legend()
                for ax in axs:ax.axvline(pd.Timestamp('2026-07-03'),color='gray',ls=':');ax.grid(alpha=.2)
                fig.savefig(out/'512480-volume-correction.png',dpi=150);plt.close(fig)
    (out/'signal-audit.json').write_text(json.dumps({'rows':rows,'scope':'All explicit split events in selectedETF17/HK7,not an exhaustive sharecapital audit. Causal cumulative split normalization only;cashdividends do not change shareunits. Original rawvolumes retained for actual order participation/accounting.'},indent=2)+'\n')
    for r in rows:print(r)
if __name__=='__main__':main()
