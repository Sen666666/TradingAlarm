from study import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
snap=Path(read(O/'input.json')['snapshot']);fig,ax=plt.subplots(2,2,figsize=(14,9),sharex='col',gridspec_kw={'height_ratios':[3,1]})
for j,(sid,start,end,title) in enumerate([('300570.SZ','2025-06-01','2025-08-15','实际新增成交：太辰光'),('600563.SH','2024-02-01','2024-04-10','仅结构示例：法拉电子（账户未买入）')]):
 f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];g=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);a=ax[0,j];a.plot(f.index,f.close,label='因果复权收盘',color='#444');a.fill_between(f.index,f.low,f.high,color='#999',alpha=.2);a.plot(g.index,g.e0_floor.where(g.e0_target.astype(bool)),label='E0保护',color='#b18b43')
 if j==0:
  a.axhline(182.40172306926408,color='#b8352f',ls='--',label='冻结局部保护');dates=[('2025-06-27','信号','#777'),('2025-06-30','实际买入','#2468a1'),('2025-07-04','收盘止损','#b8352f'),('2025-07-07','实际卖出','#833')]
 else:
  a.axhline(124.381088905012,color='#b8352f',ls='--',label='局部保护（近似绘图）');dates=[('2024-03-06','结构信号','#777'),('2024-03-08','E0保护接管','#2468a1'),('2024-03-26','E0结构失败','#833')]
 for d,label,col in dates:a.axvline(pd.Timestamp(d),color=col,lw=.8,ls=':');a.text(pd.Timestamp(d),a.get_ylim()[1],label,rotation=90,va='top',fontsize=8,color=col)
 a.set_title(title);a.legend(fontsize=8,loc='lower right');ax[1,j].bar(f.index,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('金额/亿元');ax[1,j].tick_params(axis='x',rotation=25)
fig.suptitle('左图实际现金交易，右图仅解释保护位交接，不能当成模拟盈利');fig.tight_layout();fig.savefig(O/'cases.png',dpi=125)
