from study import *
from audit import rows
from collections import Counter
risk=[];diff=[]
for cohort in STARTS:
 stocks=pd.read_csv(O/cohort/'analysis/stocks.csv')
 for seed in range(3):
  old=stocks[stocks.account==f'ACT{seed}__S0_base'].set_index('symbol')
  for v in ['BUF','COR']:
   new=stocks[stocks.account==f'{v}{seed}__S0_base'].set_index('symbol');ids=old.index.union(new.index)
   for sid in ids:
    a=float(old.loc[sid,'net_profit']) if sid in old.index else 0;b=float(new.loc[sid,'net_profit']) if sid in new.index else 0
    diff.append(dict(cohort=cohort,strategy=v,seed=seed,symbol=sid,name=old.loc[sid,'name'] if sid in old.index else new.loc[sid,'name'],act_pnl=a,new_pnl=b,delta=b-a))
  for v in ['ACT','BUF','COR']:
   obj=read(O/cohort/'accounts-v2'/f'{v}{seed}__S0_base.json')
   for r in obj['audit_log']:
    if r['kind']=='risk_checkpoint' and r['event']:risk.append(dict(cohort=cohort,strategy=v,seed=seed,at=r['at'],event=r['event'],nav=r['nav'],episode=r['episode']))
pd.DataFrame(diff).to_csv(O/'stock-attribution.csv',index=False);pd.DataFrame(risk).to_csv(O/'risk-events.csv',index=False)
# Illustrative existing COR pair, chosen as first actual pair in the latest start,
# not selected by subsequent winner/loser returns.
pairs=pd.read_csv(O/'pairs.csv');q=pairs[(pairs.cohort=='S2')&(pairs.account=='COR0__S0_base')&pairs.actual_buy].sort_values('signal_at')
if len(q):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 r=q.iloc[0];t=pd.Timestamp(r.signal_at[:10]);snap=Path(read(O/'input.json')['snapshot']);fig,ax=plt.subplots(3,2,figsize=(14,9),sharex='col',gridspec_kw={'height_ratios':[3,1,1]})
 for j,sid in enumerate([r.victim,r.candidate]):
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[t-pd.Timedelta(days=60):t+pd.Timedelta(days=100)];z=pd.read_parquet(O/'signals'/f'{sid}.parquet').reindex(f.index);ax[0,j].plot(f.index,f.close,label='收盘');ax[0,j].plot(z.index,z.ema21,label='EMA21');ax[0,j].fill_between(f.index,f.low,f.high,alpha=.2,color='#999');ax[0,j].axvline(t,color='#b33',ls=':');ax[0,j].set_title(('换出 ' if j==0 else '换入 ')+sid);ax[0,j].legend();ax[1,j].bar(f.index,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('金额/亿元');ax[2,j].plot(z.index,z.up_amount10);ax[2,j].axhline(.5,color='#888',ls=':');ax[2,j].axhline(.6,color='#888',ls='--');ax[2,j].tick_params(axis='x',rotation=25)
 fig.suptitle('最新起点COR首笔换仓，竖线为信号日；局部条件成立不保证整户路径改善');fig.tight_layout();fig.savefig(O/'case-first-correction.png',dpi=120);plt.close(fig)
print('attribution completed')
