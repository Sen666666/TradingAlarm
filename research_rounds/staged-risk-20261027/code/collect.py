from pathlib import Path
import json,gzip
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 out=O/'results';out.mkdir(exist_ok=False);summaries=[];curves=[];periods=[];campaigns=[]
 for root in sorted(O.iterdir()):
  p=root/'analysis/summary.csv'
  if not p.exists():continue
  s=pd.read_csv(p);s['version']=root.name;summaries.append(s);c=pd.read_csv(root/'analysis/curves.csv',parse_dates=['date']);c['version']=root.name;curves.append(c);x=pd.read_csv(root/'analysis/campaigns.csv');x['version']=root.name;campaigns.append(x)
  for aid,a in c.groupby('account'):
   a=a.set_index('date').sort_index()
   for label,start,end in [('2024','2024-01-01','2024-12-31'),('2025','2025-01-01','2025-12-31'),('2026H1','2026-01-01','2026-06-30'),('2026H2','2026-07-01','2026-10-26')]:
    b=a.loc[start:end];prior=a.loc[a.index<pd.Timestamp(start)];n0=prior.nav.iloc[-1] if len(prior) else 1e6;expo=b.market_value/b.nav;dd=1-b.nav/np.maximum(b.nav.cummax(),n0);periods.append(dict(version=root.name,account=aid,period=label,start_nav=n0,end_nav=b.nav.iloc[-1],net_return=b.nav.iloc[-1]/n0-1,drawdown=dd.max(),mean_exposure=expo.mean(),max_exposure=expo.max(),low_days=int(expo.le(.2).sum()),empty_days=int(expo.le(.001).sum()),days=len(b)))
 s=pd.concat(summaries);c=pd.concat(curves);p=pd.DataFrame(periods);s.to_csv(out/'summary.csv',index=False);c.to_csv(out/'curves.csv',index=False);p.to_csv(out/'periods.csv',index=False);pd.concat(campaigns).to_csv(out/'campaigns.csv',index=False)
 h1=p[p.period=='2026H1'][['version','account','end_nav']].rename(columns={'end_nav':'pre_nav'});h2=p[p.period=='2026H2'][['version','account','net_return','mean_exposure','low_days','empty_days']].rename(columns={'net_return':'h2_return','mean_exposure':'h2_exposure'});score=s.merge(h1,on=['version','account']).merge(h2,on=['version','account']);refs=score[score.version=='CONTROL'].set_index('scenario').pre_nav;score['pre_profit_retention']=[(n-1e6)/(refs[k]-1e6) for n,k in zip(score.pre_nav,score.scenario)];score.to_csv(out/'scoreboard.csv',index=False)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
 base=c[c.scenario=='base'];fig,ax=plt.subplots(3,1,figsize=(15,12),sharex=True)
 for v,z in base.groupby('version'):
  z=z.set_index('date');ax[0].plot(z.index,z.nav/1e6,label=v,lw=2 if v=='CONTROL' else 1);ax[1].plot(z.index,z.market_value/z.nav,label=v,alpha=.7);ax[2].plot(z.index,z.drawdown,label=v,alpha=.8)
 ax[0].set_title('2024—2026-10-26 基础账户：净值 / 实际仓位 / 回撤');ax[0].legend(ncol=4);ax[0].set_ylabel('初始100万=1');ax[1].set_ylabel('实际仓位');ax[2].set_ylabel('回撤')
 for a in ax:a.axvspan(pd.Timestamp('2026-07-01'),pd.Timestamp('2026-10-26'),alpha=.06,color='red');a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(out/'accounts.png',dpi=130)
 print(score[score.scenario=='base'][['version','net_return','max_drawdown','pre_nav','pre_profit_retention','h2_return','h2_exposure','low_days','empty_days']].to_string(index=False))
