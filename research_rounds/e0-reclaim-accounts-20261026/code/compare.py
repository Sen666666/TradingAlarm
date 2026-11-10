from pathlib import Path
import pandas as pd,numpy as np,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1]
a=pd.read_csv(O/'ON/analysis/summary.csv').set_index('account');b=pd.read_csv(O/'OFF/analysis/summary.csv').set_index('account');rows=[]
for aid in a.index:
 r=dict(account=aid)
 for c in ['net_return','max_drawdown','mean_exposure','fees','closed','tail_profit','ordinary_profit','open_profit','all_closed_losses','tail_over_all_losses']:
  r['on_'+c]=a.loc[aid,c];r['off_'+c]=b.loc[aid,c];r['delta_'+c]=b.loc[aid,c]-a.loc[aid,c]
 rows.append(r)
x=pd.DataFrame(rows);x.to_csv(O/'comparison.csv',index=False)
s1=pd.read_csv(O/'ON/analysis/stocks.csv');s2=pd.read_csv(O/'OFF/analysis/stocks.csv');s=s1.merge(s2,on=['account','symbol'],how='outer',suffixes=('_on','_off'));s['delta']=s.net_profit_off.fillna(0)-s.net_profit_on.fillna(0);s.to_csv(O/'stock-differences.csv',index=False)
fig,axes=plt.subplots(2,3,figsize=(16,8),sharex=True)
for v,color in [('ON','#347ca2'),('OFF','#bf633d')]:
 c=pd.read_csv(O/v/'analysis/curves.csv');c['date']=pd.to_datetime(c.date)
 for i,pol in enumerate(['E0','I']):
  for j,st in enumerate(['base','cost2','delay1']):
   q=c[c.account==f'{pol}__S0_{st}'];axes[i,j].plot(q.date,q.nav/1e6,label=v,color=color);axes[i,j].set_title(f'{pol} / {st}');axes[i,j].grid(alpha=.2);axes[i,j].tick_params(axis='x',rotation=30,labelsize=8);axes[i,j].legend()
fig.suptitle('E0 reclaim ON vs OFF | start NAV = 1 million CNY | after costs');fig.tight_layout();fig.savefig(O/'comparison.png',dpi=150)
print(x[['account','on_net_return','off_net_return','on_max_drawdown','off_max_drawdown','on_tail_profit','off_tail_profit','on_ordinary_profit','off_ordinary_profit','on_fees','off_fees']].to_string(index=False))
for aid in a.index:
 q=s[s.account==aid].sort_values('delta');print('\n',aid);print(pd.concat([q.head(3),q.tail(3)])[['symbol','name_on','name_off','net_profit_on','net_profit_off','delta']].to_string(index=False))
