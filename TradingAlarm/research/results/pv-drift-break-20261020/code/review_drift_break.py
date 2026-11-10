import argparse,json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(out,old):
    rows=[];fig,ax=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for i,g in enumerate(['etf17','hk7']):
        for directory,model,label in [(out,'pv','drift break'),(out,'duplicate','matched duplicate level'),(old,'pv','prior three modes')]:
            p=pd.read_parquet(directory/f'{g}-{model}-base-path.parquet');ax[i].plot(p.index,p.nav,label=label)
        ax[i].legend();ax[i].set_title(g)
        d=pd.read_csv(out/f'{g}-pv-base-daily-episodes.csv');d['year']=pd.to_datetime(d.date).dt.year
        for (year,label),v in d.groupby(['year','label']).pnl.sum().items():rows.append(dict(group=g,year=int(year),label=label,pnl_initial_fraction=float(v/1e6)))
    fig.tight_layout();fig.savefig(out/'account-comparison.png',dpi=120);plt.close(fig);pd.DataFrame(rows).to_csv(out/'period-attribution.csv',index=False)
    caseinfo=[]
    for sym,g,start,end in [('HK09618','hk7','2024-08-01','2024-11-30'),('USHJ512480','etf17','2025-07-01','2026-08-31')]:
        d=pd.read_csv(out/f'{sym}-signals.csv',index_col='date',parse_dates=True).loc[start:end];prior=pd.read_csv(old/f'{sym}-signals.csv',index_col='date',parse_dates=True).loc[start:end];orders=[o for o in json.loads((out/f'{g}-pv-base-orders.json').read_text()) if o['symbol']==sym and start<=o['date']<=end];fig,ax=plt.subplots(4,1,figsize=(12,9),sharex=True);ax[0].plot(d.index,d.close,color='black');ax[0].set_title(sym+'; execution-day markers on signal close, not actual fill price')
        for o in orders:ax[0].scatter(pd.Timestamp(o['date']),d.loc[o['date'],'close'],color='green' if o['units']>0 else 'red',marker='^' if o['units']>0 else 'v')
        ax[1].bar(d.index,d.volume,color='gray');ax[2].plot(d.index,d.strength,label='new');ax[2].plot(prior.index,prior.strength,label='prior');ax[2].axhline(1,ls=':',color='black');ax[2].axhline(0,lw=.5,color='black');ax[2].legend()
        for col in ['jump_weight','shock_weight','drift_break_weight']:ax[3].plot(d.index,d[col],label=col)
        ax[3].legend();fig.tight_layout();fig.savefig(out/f'{sym}-review.png',dpi=120);plt.close(fig);caseinfo.append(dict(symbol=sym,orders=orders))
    (out/'reviewed-orders.json').write_text(json.dumps(caseinfo,indent=2));a=json.loads((out/'accounts.json').read_text());v=dict(cases=len(a),max_ledger_error=max(max(r['ledger'].values()) for r in a),max_episode_error=max(r['episodes']['max_daily_error'] for r in a),decision='reject promotion: faster onset worsens whole-account ordinary losses',rare_mode_volume_odds='For fixed prior-state mixture and price, all three rare prior masses scale equally with activity; their pairwise posterior odds are independent of current activity. Volume only shifts total rare-vs-ordinary mass, not jump-vs-drift-vs-shock discrimination.',period_label_caveat='Final economic-cycle labels, daily PNL assigned to calendar years; retrospective only.');(out/'review-validation.json').write_text(json.dumps(v,indent=2));print(v)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);a=p.parse_args();main(a.output,a.previous)
