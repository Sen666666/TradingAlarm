from pathlib import Path
import json,gzip
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1]
PATHS=[('NR1',O/'CONTROL')]+[(f'{v}-{p}',O/v/p) for v in ['R1','R2','R3','P1'] for p in ['H','C']]
PERIODS=[('2024','2024-01-01','2024-12-31'),('2025','2025-01-01','2025-12-31'),('2026H1','2026-01-01','2026-06-30'),('2026H2','2026-07-01','2026-10-26')]
if __name__=='__main__':
 sums=[];periods=[];stocks=[];contrib=[];held=[]
 for label,root in PATHS:
  if not (root/'analysis/summary.csv').exists():continue
  s=pd.read_csv(root/'analysis/summary.csv');s['version']=label;s['key']=label+'-'+s.account;sums.append(s)
  c=pd.read_csv(root/'analysis/curves.csv');c.date=pd.to_datetime(c.date)
  for aid,q in c.groupby('account'):
   for tag,start,end in PERIODS:
    part=q[(q.date>=start)&(q.date<=end)];prior=q[q.date<start];base=float(prior.nav.iloc[-1]) if len(prior) else 1e6;nav=part.nav.to_numpy();peaks=np.maximum.accumulate(np.r_[base,nav])[1:]
    periods.append(dict(version=label,account=aid,period=tag,starting_nav=base,ending_nav=nav[-1],net_return=nav[-1]/base-1,pnl=nav[-1]-base,max_drawdown=float((1-nav/peaks).max()),mean_exposure=float((part.market_value/part.nav).mean())))
  x=pd.read_csv(root/'analysis/stocks.csv');x['version']=label;stocks.append(x)
  x=pd.read_csv(root/'analysis/contributions.csv');x['version']=label;contrib.append(x)
  with gzip.open(root/'accounts-v2/daily.jsonl.gz','rt') as f:
   for line in f:
    r=json.loads(line)
    if r['account'].endswith('base') and r['at'][:10]>='2024-01-01':
     for sid,qty in r['positions'].items():
      if float(qty)>0:held.append(dict(version=label,account=r['account'],date=r['at'][:10],symbol=sid))
 pd.concat(sums).to_csv(O/'all-summary.csv',index=False);pd.DataFrame(periods).to_csv(O/'periods.csv',index=False);pd.concat(stocks).to_csv(O/'all-stocks.csv',index=False);pd.concat(contrib).to_csv(O/'all-contributions.csv',index=False);pd.DataFrame(held).to_csv(O/'held-days.csv',index=False)
 full=pd.concat(sums);base=full[full.scenario=='base'].copy();h2=pd.DataFrame(periods);h2=h2[h2.period=='2026H2'][['version','account','net_return','pnl']].rename(columns=dict(net_return='h2_return',pnl='h2_pnl'));base=base.merge(h2,on=['version','account']);print(base[['version','account','net_return','max_drawdown','h2_return','h2_pnl','mean_exposure','tail_profit','ordinary_profit']].to_string(index=False))
