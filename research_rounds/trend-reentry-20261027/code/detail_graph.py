from study import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
f=pd.read_csv(O/'additional-events.csv');f['year']=f.date.str[:4];chosen=f.sort_values(['date','symbol']).groupby(['version','year']).head(1);chosen.to_csv(O/'detail-selection.csv',index=False);snap=Path(read(O/'input.json')['snapshot'])
fig,ax=plt.subplots(2,3,figsize=(18,10))
for a,r in zip(ax.flat,chosen.itertuples()):
 g=pd.read_parquet(snap/'signals'/f'{r.symbol}.parquet');t=pd.Timestamp(r.date);g=g.loc[t-pd.Timedelta(days=40):t+pd.Timedelta(days=35)];a.plot(g.index,g.close,color='#444');a.fill_between(g.index,g.low,g.high,alpha=.2,color='#888');a.axvline(t,color='#2468a1');a.axhline(r.floor,color='#a13226',ls='--');a.set_title(f'{r.version} {r.symbol} {r.date}');a.tick_params(axis='x',rotation=25);b=a.twinx();b.bar(g.index,g.amount/1e8,alpha=.15,color='#2468a1');b.set_ylabel('金额/亿元')
fig.suptitle('按各通道每年首个新增事件选图（不按后续收益挑选）；竖线=信号，虚线=局部保护');fig.tight_layout();fig.savefig(O/'detail-review.png',dpi=115)
