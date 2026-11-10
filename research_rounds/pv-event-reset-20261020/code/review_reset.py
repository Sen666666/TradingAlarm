from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path(__file__).resolve().parents[1];p=b/'results';pr=json.loads((p/'protocol.json').read_text());old=Path(pr['source']);a=json.loads((p/'accounts.json').read_text());previous={x['case']:x for x in json.loads((old/'accounts.json').read_text())};rows=[]
for x in a:
 e=x['episodes'];o=previous[x['case']];assert abs(sum(e[k]['net_pnl'] for k in ['tail','ordinary','open_or_claim'])/1e6-x['total_return'])<1e-10
 rows.append(dict(case=x['case'],return_pct=x['total_return']*100,old_return=o['total_return']*100,change_pp=(x['total_return']-o['total_return'])*100,dd_pct=abs(x['max_drawdown'])*100,closed=e['closed_n'],tail_n=e['tail']['n'],tail_pp=e['tail']['net_pnl']/1e4,ordinary_pp=e['ordinary']['net_pnl']/1e4,ordinary_gross_pp=e['ordinary']['gross_pnl_same_labels']/1e4,open_pp=e['open_or_claim']['net_pnl']/1e4,fees_pp=x['fees']/1e4,cash_pct=x['average_cash_weight']*100))
pd.DataFrame(rows).to_csv(p/'account-comparison.csv',index=False);print(pd.DataFrame(rows).round(3).to_string(index=False))
for group in ['etf17','hk7']:
 fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True)
 for path,label in [(old/f'{group}-pv-base-path.parquet','original PV'),(p/f'{group}-pv-base-path.parquet','reset PV'),(p/f'{group}-price-base-path.parquet','reset price')]:
  f=pd.read_parquet(path);ax[0].plot(f.index,f.nav,label=label);ax[1].plot(f.index,1-f.cash/(1e6*f.nav),label=label)
 ax[0].set_title(group+' one-change reset comparison');ax[0].legend();ax[1].set_ylabel('Actual invested NAV');fig.tight_layout();fig.savefig(p/f'{group}-review.png',dpi=110);plt.close(fig)
for s,g,start,end in [('HK09618','hk7','2024-08-01','2025-01-31'),('USHJ510300','etf17','2023-05-01','2023-10-01'),('USHJ512480','etf17','2024-08-01','2025-03-31')]:
 f=pd.read_csv(p/f'{s}-signals.csv',index_col='date',parse_dates=True).loc[start:end];fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True);ax[0].plot(f.index,f.close,color='black');ax[0].set_yscale('log');ax[0].set_title(s+' signal close and actual account exposure')
 for directory,label in [(old,'original'),(p,'reset')]:
  f=pd.read_parquet(directory/f'{g}-pv-base-path.parquet').loc[start:end];ax[1].step(f.index,f['w_'+s],where='post',label=label)
 ax[1].legend();ax[1].set_ylabel('Actual NAV weight');fig.tight_layout();fig.savefig(p/f'{s}-execution-review.png',dpi=110);plt.close(fig)
