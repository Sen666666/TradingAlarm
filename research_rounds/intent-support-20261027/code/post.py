from audit import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
s=pd.read_csv(O/'summary.csv');channels=pd.read_csv(O/'extra-entry-contribution.csv');winner=[];paired=[]
for c in STARTS:
 root=O/c;cs=pd.read_csv(root/'analysis/campaigns.csv');stocks=pd.read_csv(root/'analysis/stocks.csv');ds=rows(root/'accounts-v2/daily.jsonl.gz');lookup={(r['account'],r['at'][:10]):r for r in ds};calendar=sorted({r['at'][:10] for r in ds})
 for scenario in ['base','delay1']:
  ref=f'ACT__S0_{scenario}';tail=cs[(cs.account==ref)&cs.tail_closed]
  for mode in MODES:
   aid=f'{mode}__S0_{scenario}';held=0;possible=0
   for _,cy in tail.iterrows():
    for day in calendar:
     if cy.entry_at[:10]<=day<cy.exit_at[:10]:possible+=1;held+=cy.symbol in lookup[aid,day]['positions']
   winner.append(dict(cohort=c,scenario=scenario,mode=mode,held_stock_days=held,baseline_tail_stock_days=possible))
  a=stocks[stocks.account==ref].set_index('symbol')
  for mode in MODES[1:]:
   b=stocks[stocks.account==f'{mode}__S0_{scenario}'].set_index('symbol')
   for sid in a.index.union(b.index):
    x=float(a.loc[sid,'net_profit']) if sid in a.index else 0;y=float(b.loc[sid,'net_profit']) if sid in b.index else 0
    paired.append(dict(cohort=c,scenario=scenario,mode=mode,symbol=sid,name=(a if sid in a.index else b).loc[sid,'name'],base=x,new=y,difference=y-x))
pd.DataFrame(winner).to_csv(O/'winner-participation.csv',index=False);pd.DataFrame(paired).to_csv(O/'stock-difference.csv',index=False)
fig,ax=plt.subplots(1,3,figsize=(16,4.5));colors={'ACT':'#333333','W3':'#329653','W10':'#267cb8','F':'#ce7a26','W10F':'#a345a4'}
for j,c in enumerate(STARTS):
 f=pd.read_csv(O/c/'analysis/curves.csv')
 for mode in MODES:
  z=f[f.account==f'{mode}__S0_base'];ax[j].plot(pd.to_datetime(z.date),z.nav/1e6,label=mode,color=colors[mode],lw=1.2)
 ax[j].set_title(c+' 起点 '+STARTS[c]);ax[j].tick_params(axis='x',rotation=25);ax[j].set_ylabel('净值/初始资金');ax[j].legend(fontsize=8)
fig.tight_layout();fig.savefig(O/'paths.png',dpi=120);plt.close(fig)
# Actual F protected holdings, including signals that precede next-open fills.
snap=Path(read(PRIOR/'input.json')['snapshot']['path']);a=read(O/'S0/accounts-v2/F__S0_base.json');fig,ax=plt.subplots(2,2,figsize=(14,8))
for j,(sid,start,end) in enumerate([('688498.SH','2025-09-01','2026-08-01'),('688048.SH','2025-09-01','2026-08-01')]):
 f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];g=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);ax[0,j].plot(f.index,f.close,c='#333',label='收盘');ax[0,j].plot(g.index,g.i_floor,c='#b88b35',label='原I保护');rs=[r for r in a['audit_log'] if r['kind']=='fast_support_raise' and r['sid']==sid and start<=r['at'][:10]<=end]
 if rs:ax[0,j].scatter(pd.to_datetime([r['at'][:10] for r in rs]),[r['floor'] for r in rs],s=12,label='F实际持仓保护上移')
 for r in a['audit_log']:
  if r['kind']=='fast_support_exit' and r['sid']==sid and start<=r['at'][:10]<=end:ax[0,j].axvline(pd.Timestamp(r['at'][:10]),color='#c33',ls=':',lw=.8)
 ax[0,j].set_title(sid+' 红竖线=F退出决策（非成交）');ax[0,j].legend(fontsize=8);ax[1,j].bar(f.index,f.amount/1e8,color='#7892a1');ax[1,j].set_ylabel('成交额/亿元')
 for i in [0,1]:ax[i,j].tick_params(axis='x',rotation=20)
fig.tight_layout();fig.savefig(O/'actual-support.png',dpi=120);plt.close(fig)
print('post complete')
