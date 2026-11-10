"""Case-study diagnosis, selected by tech exposure, not parameter fitting."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
os.makedirs(os.environ['XDG_CACHE_HOME'],exist_ok=True)
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from hk_extension import load_extended
from geometric_strength import geometric_frame,strength_exposure
from adaptive_geometric_strength import adaptive_frame
from neutral_trend_strength import neutral_frame
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/tech-2026-review'

def period_return(p,start,end):
    w=p.loc[start:end];before=p.loc[p.index<w.index[0]]
    return float(w.iloc[-1]/before.iloc[-1]-1)

def main():
    assets,_=load_extended();reports=[]
    for symbol,title in [('USHJ512480','512480 | Semiconductor ETF'),('HK03033','03033.HK | Hang Seng TECH ETF')]:
        a=assets[symbol];raw=a['raw'];p=a['signal'].close;valid=raw.index[raw.volume.gt(0)].intersection(p.index)
        models={'adaptive':adaptive_frame(p.loc[valid],raw.close.loc[valid],raw.volume.loc[valid]).strength,'linear':geometric_frame(p.loc[valid],raw.close.loc[valid],raw.volume.loc[valid],degree=1).strength,'neutral_experimental':neutral_frame(p.loc[valid],raw.close.loc[valid],raw.volume.loc[valid]).bullish_strength}
        scores=pd.DataFrame(models);exposures=pd.DataFrame({k:strength_exposure(s) for k,s in models.items()})
        w=p.loc['2026-01-01':'2026-10-16'];peak=w.idxmax();normal=p/p.loc[:'2025-12-31'].iloc[-1]*100
        periods={label:period_return(p,start,end) for label,start,end in [('Jan-May','2026-01-01','2026-05-31'),('June','2026-06-01','2026-06-30'),('June-Oct16','2026-06-01','2026-10-16'),('July-Oct16','2026-07-01','2026-10-16')]}
        mr=[]
        for model,s in models.items():
            exposure=exposures[model];y=s.loc[w.index];after=y.loc[peak:];off=after.index[after.le(5)]
            monthly=[]
            for date,g in y.groupby(y.index.to_period('M')):
                monthly.append({'month':str(date),'mean_strength':float(g.mean()),'min_strength':float(g.min()),'max_strength':float(g.max()),'occupied_fraction':float(exposure.loc[g.index].mean())})
            transitions=exposure.diff();events=[{'date':str(d.date()),'signal':'enter' if transitions.loc[d]>0 else 'exit','strength':float(s.loc[d])} for d in transitions.loc[w.index].index[transitions.loc[w.index].ne(0)]]
            mr.append({'model':model,'strength_at_peak':float(s.loc[peak]),'active_at_peak':bool(exposure.loc[peak]),'first_score_le5_from_peak':str(off[0].date()) if len(off) else None,'observed_bars_after_peak':int(after.index.get_loc(off[0])) if len(off) else None,'return_peak_to_first_le5':float(p.loc[off[0]]/p.loc[peak]-1) if len(off) else None,'monthly':monthly,'signals':events})
        case='etf17-adaptive_geometry_price_volume-daily-base'
        orders=json.loads((ROOT/'results/trend-strength-ah-transfer'/f'{case}-orders.json').read_text())
        orders=[o for o in orders if o['symbol']==symbol and '2026-01-01'<=o['date']<='2026-10-16']
        fills=[{'date':o['date'],'side':'buy' if o['units']>0 else 'sell','units':o['units'],'raw_open':o['raw_open'],'fee':o['fee']} for o in orders]
        r={'symbol':symbol,'period_returns':periods,'year_peak':str(peak.date()),'peak_to_last':float(w.iloc[-1]/w.loc[peak]-1),'splits_2026':[e for e in a['splits'] if e['date'].startswith('2026')],'models':mr,'actual_adaptive_account_fills':fills}
        reports.append(r);scores.loc[w.index].join(exposures.add_suffix('_held')).join(normal.rename('price_index')).to_parquet(OUT/f'{symbol}-daily.parquet')
        fig,axes=plt.subplots(4,1,figsize=(14,11),sharex=True,gridspec_kw={'height_ratios':[3,2,2,1.4]},layout='constrained')
        axes[0].plot(w.index,normal.loc[w.index],color='#172b4d',lw=1.8,label='Causal adjusted price; 2025 year-end=100')
        for side,color,marker in [('buy','#059669','^'),('sell','#dc2626','v')]:
            ds=pd.to_datetime([f['date'] for f in fills if f['side']==side]);axes[0].scatter(ds,normal.reindex(ds),c=color,marker=marker,s=65,label='Account '+side,zorder=3)
        axes[0].axvline(peak,color='#7c3aed',ls=':',label='2026 peak (hindsight)');axes[0].set_title(title+' — 2026 price, state and actual account decisions',loc='left');axes[0].legend(fontsize=8,loc='upper left');axes[0].set_ylabel('Price index')
        for name,color in [('adaptive','#2563eb'),('linear','#d97706')]:axes[1].plot(w.index,scores.loc[w.index,name],color=color,label=name,lw=1.2)
        axes[1].axhline(5+5*np.tanh(1),color='green',ls='--',lw=.8,label='Fixed entry threshold');axes[1].axhline(5,color='red',ls='--',lw=.8,label='Fixed exit threshold');axes[1].set_ylim(-.2,10.2);axes[1].set_ylabel('Geometry strength');axes[1].legend(fontsize=8,ncol=2)
        axes[2].plot(w.index,scores.loc[w.index,'neutral_experimental'],color='#7c3aed',lw=1.2,label='Experimental: 10 x model P(up), not profit probability')
        axes[2].axhline(5+5*np.tanh(1),color='green',ls='--',lw=.8);axes[2].axhline(5,color='red',ls='--',lw=.8);axes[2].set_ylim(-.2,10.2);axes[2].set_ylabel('Up-state support');axes[2].legend(fontsize=8)
        volume_ratio=raw.volume/raw.volume.shift().rolling(21).median();axes[3].bar(w.index,volume_ratio.reindex(w.index),color='#94a3b8',width=1.2);axes[3].set_ylabel('Raw volume / prior\n21-bar median')
        if symbol=='USHJ512480':
            axes[3].annotate('July 3: 2-for-1 split changes volume units',xy=(pd.Timestamp('2026-07-03'),2),xytext=(pd.Timestamp('2026-04-01'),2.7),fontsize=8,arrowprops={'arrowstyle':'->','color':'#64748b'})
        for ax in axes:
            ax.axvline(pd.Timestamp('2026-06-01'),color='#64748b',ls='--',lw=.8);ax.axvline(pd.Timestamp('2026-07-01'),color='#64748b',ls='--',lw=.8);ax.grid(alpha=.15)
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator());axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        fig.savefig(OUT/f'{symbol}.png',dpi=150);plt.close(fig)
    (OUT/'report.json').write_text(json.dumps({'reports':reports,'scope':'Local-data case study of two tech proxies,not whole科技sector. Selected byexistingsectorlabels. June1/July1 marks are review aids only,never model inputs. Pricepaths use existing causal adjustment,including512480July3split. Geometricstrength andexperimentalposterior score have different semantics. Neutralmodel has not undergone marketaccountbacktest. Accountfillmarkers use adjustedcloseposition fordisplay,actualrawopen stored separately. Allpeakdiagnostics hindsight,not tradable top recognition.'},indent=2)+'\n')
    for r in reports:
        print(r['symbol'],r['period_returns'],'peak',r['year_peak'],'drawdown',r['peak_to_last'])
        for m in r['models']:print(m['model'],{k:v for k,v in m.items() if k not in ('model','monthly','signals')},m['signals'])
        print('fills',r['actual_adaptive_account_fills'])
if __name__=='__main__':main()
