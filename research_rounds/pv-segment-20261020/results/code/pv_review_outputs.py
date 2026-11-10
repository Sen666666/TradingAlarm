"""Generate fixed review views and attribution; no model or parameter selection."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_pv_segment_round import assets,write


def main(out):
    groups,_=assets();all_assets={**groups['etf17'],**groups['hk7']};protocol=json.loads((out/'protocol.json').read_text());results=json.loads((out/'accounts.json').read_text());diagnostics={}
    for group in groups:
        fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
        for name in ['pv','price','half_slow','buyhold']:
            p=pd.read_parquet(out/f'{group}-{name}-base-path.parquet');axes[0].plot(p.index,p.nav,label=name)
        axes[0].legend();axes[0].set_title(group+' fixed-account comparisons, development 2022-2026')
        p=pd.read_parquet(out/f'{group}-pv-base-path.parquet');axes[1].plot(p.index,p.cash/(p.nav*1e6),label='PV cash weight');axes[1].plot(p.index,p.drawdown,label='PV drawdown');axes[1].legend();fig.tight_layout();fig.savefig(out/f'{group}-account.png',dpi=130);plt.close(fig)
        episodes=json.loads((out/f'{group}-pv-base-episodes.json').read_text())
        by_symbol={s:dict(pnl=sum(e['pnl'] for e in episodes if e['symbol']==s),n=sum(e['symbol']==s for e in episodes),tail=sum(e['label']=='tail' and e['symbol']==s for e in episodes)) for s in groups[group]}
        closed=[e for e in episodes if e['status']=='closed']
        trades=pd.DataFrame(closed)
        diagnostics[group]={'by_symbol':by_symbol,'closed_median_sessions':float(trades.sessions.median()),'closed_under10_sessions':int(trades.sessions.le(10).sum()),'ordinary_gross':sum(e['pnl']+e['fees'] for e in closed if e['label']=='ordinary'),'tail_erosion':-sum(e['pnl'] for e in closed if e['label']=='ordinary')/sum(e['pnl'] for e in closed if e['label']=='tail')}
        # Explain quantity-based participation, gaps and state duration, not signal-line returns.
        for s,start,end in [x for x in protocol['cases'] if x[0] in groups[group]]:
            a=all_assets[s];d=pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True).loc[start:end];orders=json.loads((out/f'{group}-pv-base-orders.json').read_text());fills=[o for o in orders if o['symbol']==s and start<=o['date']<=end]
            fig,axes=plt.subplots(4,1,figsize=(12,9),sharex=True,gridspec_kw={'height_ratios':[3,1,2,1]})
            axes[0].plot(d.index,d.close,color='black',label='Signal total-return close')
            for sign,color,marker in [(1,'green','^'),(-1,'red','v')]:
                part=[o for o in fills if np.sign(o['units'])==sign];dates=pd.to_datetime([o['date'] for o in part]);values=[o['raw_open']*a['signal'].loc[o['date'],'close']/a['raw'].loc[o['date'],'close'] for o in part]
                axes[0].scatter(dates,values,color=color,marker=marker,s=25,label='Buy fills' if sign==1 else 'Sell fills')
            axes[0].set_title(s+' actual fills (open mapped to signal-price scale for display)');axes[0].legend(fontsize=8)
            axes[1].bar(d.index,d.volume,width=1,color='grey');axes[1].set_ylabel('Volume')
            axes[2].plot(d.index,d.strength,label='PV strength');axes[2].plot(d.index,d.price_strength,label='Price strength',alpha=.6);axes[2].axhline(1,color='green',lw=.5);axes[2].axhline(0,color='black',lw=.5);axes[2].legend()
            pp=p.loc[start:end];axes[3].plot(d.index,d.target*.9/len(groups[group]),label='Entry budget fraction (not rebalance)');axes[3].plot(pp.index,pp['w_'+s],label='Actual account weight');axes[3].legend(fontsize=8);fig.tight_layout();fig.savefig(out/f'{s}-fills.png',dpi=130);plt.close(fig)
    write(out/'review-diagnostics.json',diagnostics)
    print(json.dumps(diagnostics,ensure_ascii=False,indent=2))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
