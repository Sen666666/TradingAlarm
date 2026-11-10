import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent.parent/'results'
rows=json.loads((p/'accounts.json').read_text()); summary=[];yearly=[]
for r in rows:
 e=r['episodes'];assert abs(sum(e[k]['net_pnl'] for k in ['tail','ordinary','open_or_claim'])/1e6-r['total_return'])<1e-10
 summary.append(dict(case=r['case'],return_pct=100*r['total_return'],dd_pct=100*abs(r['max_drawdown']),closed=e['closed_n'],tail_pp=e['tail']['net_pnl']/1e4,ordinary_pp=e['ordinary']['net_pnl']/1e4,open_pp=e['open_or_claim']['net_pnl']/1e4,ordinary_gross_pp=e['ordinary']['gross_pnl_same_labels']/1e4,fees_pp=r['fees']/1e4,cash_pct=100*r['average_cash_weight']))
 d=pd.read_csv(p/f"{r['case']}-daily-episodes.csv",parse_dates=['date']);d['year']=d.date.dt.year
 for (year,label),g in d.groupby(['year','label']):yearly.append(dict(case=r['case'],year=int(year),label=label,pp=g.pnl.sum()/1e4))
pd.DataFrame(summary).to_csv(p/'account-summary.csv',index=False);pd.DataFrame(yearly).to_csv(p/'year-attribution.csv',index=False)
for group in ['etf17','hk7']:
 fig,ax=plt.subplots(2,1,figsize=(11,6),sharex=True)
 for model in ['pv','price','momentum']:
  f=pd.read_parquet(p/f'{group}-{model}-base-path.parquet');ax[0].plot(f.index,f.nav,label=('event_exit' if model=='momentum' else model));ax[1].plot(f.index,1-f.cash/(f.nav*1e6),label=('event_exit' if model=='momentum' else model))
 ax[0].legend();ax[0].set_title(group+' fixed entry budget; net NAV');ax[1].set_ylabel('Invested NAV fraction');fig.tight_layout();fig.savefig(p/f'{group}-account-review.png',dpi=110);plt.close(fig)
for group,s,start,end in [('etf17','USHJ518880','2024-01-01','2026-10-16'),('etf17','USHJ512480','2024-08-01','2026-10-16'),('hk7','HK09618','2024-08-01','2025-01-01')]:
 f=pd.read_csv(p/f'{s}-signals.csv',index_col='date',parse_dates=True).loc[start:end];fig,ax=plt.subplots(3,1,figsize=(11,7),sharex=True)
 ax[0].plot(f.index,f.close,color='black');ax[0].set_yscale('log');ax[0].set_title(s+' signal price; markers are execution dates, not execution prices')
 for model,color in [('pv','blue'),('momentum','orange')]:
  orders=json.loads((p/f'{group}-{model}-base-orders.json').read_text());orders=[o for o in orders if o['symbol']==s and start<=o['date']<=end]
  for sign,marker in [(1,'^'),(-1,'v')]:
   dates=[pd.Timestamp(o['date']) for o in orders if o['units']*sign>0];ax[0].scatter(dates,f.close.reindex(dates),marker=marker,color=color,label=f'{model} {marker}',s=25)
  path=pd.read_parquet(p/f'{group}-{model}-base-path.parquet').loc[start:end];ax[2].step(path.index,path['w_'+s],where='post',label=('event_exit' if model=='momentum' else model),color=color)
 ax[0].legend(fontsize=7);ax[1].bar(f.index,f.volume,color='gray');ax[1].set_ylabel('Volume');ax[2].set_ylabel('Actual NAV weight');ax[2].legend();fig.tight_layout();fig.savefig(p/f'{s}-execution-review.png',dpi=110);plt.close(fig)
print(pd.DataFrame(summary).round(3).to_string(index=False))
print(pd.DataFrame(yearly).query("case in ['etf17-pv-base','hk7-pv-base']").pivot(index=['case','year'],columns='label',values='pp').round(3).to_string())
