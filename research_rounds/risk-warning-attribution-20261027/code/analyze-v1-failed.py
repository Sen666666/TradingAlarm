from pathlib import Path
import pandas as pd,numpy as np,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];R=O.parents[1];A=R/'research_rounds/actual-risk-recovery-20261027';P=R/'research_rounds/tech-drawdown-regime-20261027'
out=O/'results';out.mkdir(exist_ok=False)
c=pd.read_csv(A/'ACT20_BREAK/analysis/curves.csv',parse_dates=['date'])
s=pd.read_csv(A/'ACT20_BREAK/analysis/stocks.csv');x=s.pivot_table(index=['symbol','name'],columns='scenario',values='net_profit',aggfunc='sum',fill_value=0);x['base_minus_delay']=x.base-x.delay1;x.sort_values('base_minus_delay',ascending=False).to_csv(out/'delay-contributions.csv')
pd.read_csv(A/'ACT20_BREAK/analysis/campaigns.csv').to_csv(out/'campaigns.csv',index=False)
b=pd.read_csv(P/'signals-v1/breadth.csv',index_col=0,parse_dates=True);g=pd.read_csv(A/'recovery.csv',index_col=0,parse_dates=True)
h=pd.read_csv(A/'ACT20_BREAK/analysis/contributions.csv',parse_dates=['date']); held=[]
for symbol,z in h.groupby('symbol'):
 t=pd.read_parquet(P/f'diagnostic-v1/traces/{symbol}.parquet');z=z.merge(t[['m','warm','cold','r','q']],left_on='date',right_index=True,how='left');held.append(z)
h=pd.concat(held);h['negative_mv']=h.market_value.where(h.m.le(0),0);h['notwarm_mv']=h.market_value.where(~h.warm.fillna(False),0)
rows=[]
for aid,z in c.groupby('account'):
 z=z.set_index('date');m=h[h.account==aid].groupby('date')[['market_value','negative_mv','notwarm_mv']].sum();z=z.join(m[['negative_mv','notwarm_mv']]).join(b.add_prefix('market_')).join(g[['fast_on','breakout']]);z['held_negative_fraction']=z.negative_mv/z.market_value.replace(0,np.nan);z['held_notwarm_fraction']=z.notwarm_mv/z.market_value.replace(0,np.nan);z['exposure']=z.market_value/z.nav;rows.append(z)
z=pd.concat(rows);z.to_csv(out/'daily-warning.csv');z.loc['2026-06-22':'2026-07-20'].to_csv(out/'july-warning.csv')
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(4,1,figsize=(14,12),sharex=True)
for scenario in ['base','delay1']:
 d=z[z.scenario==scenario].sort_index();ax[0].plot(d.index,d.nav/1e6,label=scenario);ax[1].plot(d.index,d.exposure,label=scenario);ax[2].plot(d.index,d.held_negative_fraction,label=scenario)
a=b.loc['2024':];ax[3].plot(a.index,a.m21,label='市场金额方向广度');ax[3].axhline(.4,ls='--',color='gray')
for aa,title in zip(ax,['ACT20_BREAK：基础与延迟账户净值','股票市值/净值','持仓中金额方向非正的市值占比','全科技市场金额方向广度']):aa.set_title(title);aa.legend();aa.grid(alpha=.2)
fig.tight_layout();fig.savefig(out/'warning.png',dpi=120)
# Entire comparison contributions reconcile, not only cherry-picked winners.
sumdiff=float(x.base_minus_delay.sum());navdiff=float(c[c.scenario=='base'].iloc[-1].nav-c[c.scenario=='delay1'].iloc[-1].nav)
assert abs(sumdiff-navdiff)<1e-6
(O/'verification.json').write_text(json.dumps({'passed':True,'contribution_difference':sumdiff,'final_nav_difference':navdiff,'economic_runs':0},indent=2))
print(x.sort_values('base_minus_delay',ascending=False).head(10).to_string());print(z[(z.scenario=='base') & (z.index>='2026-06-29') & (z.index<='2026-07-20')][['nav','exposure','held_negative_fraction','held_notwarm_fraction','market_m21','fast_on']].to_string())
