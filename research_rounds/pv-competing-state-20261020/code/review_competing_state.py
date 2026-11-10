import argparse,json
from pathlib import Path
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(out):
    rows=[]
    for group in ['etf17','hk7']:
        daily=pd.read_csv(out/f'{group}-pv-base-daily-episodes.csv');daily['year']=pd.to_datetime(daily.date).dt.year
        for (year,label),v in daily.groupby(['year','label']).pnl.sum().items():rows.append(dict(group=group,year=int(year),label=label,contribution_initial_capital=float(v/1e6)))
    pd.DataFrame(rows).to_csv(out/'period-attribution.csv',index=False)
    review=[]
    for symbol,start,end,group in [('USHJ512480','2025-07-01','2026-09-15','etf17'),('HK02820','2025-01-01','2025-10-01','etf17'),('HK09618','2024-08-01','2024-12-01','hk7')]:
        d=pd.read_csv(out/f'{symbol}-signals.csv',index_col='date',parse_dates=True).loc[start:end];path=pd.read_parquet(out/f'{group}-pv-base-path.parquet').loc[start:end];orders=[o for o in json.loads((out/f'{group}-pv-base-orders.json').read_text()) if o['symbol']==symbol and start<=o['date']<=end]
        fig,ax=plt.subplots(4,1,figsize=(12,9),sharex=True);ax[0].plot(d.index,d.close,color='black')
        for o in orders:
            day=pd.Timestamp(o['date']);ax[0].scatter(day,d.loc[day,'close'],color='green' if o['units']>0 else 'red',marker='^' if o['units']>0 else 'v');ax[3].axvline(day,color='gray',alpha=.3)
        ax[0].set_title(symbol+' post-account review; markers at execution date on signal-close price (not fill price)');ax[1].bar(d.index,d.volume,color='gray');ax[2].plot(d.index,d.strength,label='strength');ax[2].axhline(0,color='black',lw=.5);ax[2].axhline(1,color='black',ls=':');ax[2].plot(d.index,d.jump_weight,label='jump');ax[2].plot(d.index,d.shock_weight,label='shock');ax[2].legend();ax[3].plot(path.index,path['w_'+symbol],label='actual NAV weight');ax[3].step(d.index,d.target*.9/(17 if group=='etf17' else 7),where='post',label='initial-budget reference');ax[3].legend();fig.tight_layout();fig.savefig(out/f'{symbol}-post-account.png',dpi=120);plt.close(fig)
        review.append(dict(symbol=symbol,start=start,end=end,orders=orders))
    (out/'reviewed-orders.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for i,g in enumerate(['etf17','hk7']):
        for model in ['pv','price','pairwise','sma63','buyhold']:
            p=pd.read_parquet(out/f'{g}-{model}-base-path.parquet');axes[i].plot(p.index,p.nav,label=model)
        axes[i].set_title(g);axes[i].legend()
    fig.tight_layout();fig.savefig(out/'account-overview.png',dpi=120);plt.close(fig)
    accounts=json.loads((out/'accounts.json').read_text());sector=json.loads((out/'sector/accounts.json').read_text());validation=dict(main_cases=len(accounts),sector_cases=len(sector),max_ledger_error=max(max(r['ledger'].values()) for r in accounts+sector),max_episode_error=max(r['episodes']['max_daily_error'] for r in accounts+sector),period_labels='Final whole-episode net labels used retrospectively; contribution allocated by daily PNL, not exit-year total',account_target_achieved=False)
    (out/'account-validation.json').write_text(json.dumps(validation,indent=2));print(validation)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
