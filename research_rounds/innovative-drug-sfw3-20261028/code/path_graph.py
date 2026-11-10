from audit import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
cs=pd.read_csv(O/'S0/analysis/campaigns.csv');fig,axs=plt.subplots(3,2,figsize=(15,10),sharex='col',gridspec_kw={'height_ratios':[2,2,1]})
for col,(sid,name) in enumerate([('688336.SH','三生国健'),('002821.SZ','凯莱英')]):
 f=pd.read_parquet(PREP/'signals'/f'{sid}.parquet').loc['2025-01-01':'2025-08-01']
 for row,scenario in enumerate(['base','delay1']):
  ax=axs[row,col];ax.plot(f.index,f.close,c='#444');ax.fill_between(f.index,f.low,f.high,color='#bbb',alpha=.2);g=cs[(cs.account=='SW3F__S0_'+scenario)&(cs.symbol==sid)]
  for _,r in g.iterrows():
   for field,color,mark in [('entry_at','green','^'),('exit_at','red','v')]:
    if pd.isna(r[field]):continue
    day=pd.Timestamp(r[field][:10])
    if day in f.index:ax.scatter(day,f.loc[day,'close'],c=color,marker=mark,s=40);ax.annotate(day.strftime('%m-%d'),(day,f.loc[day,'close']),fontsize=7,xytext=(0,8),textcoords='offset points')
  ax.set_title(name+' '+('正常' if row==0 else '延迟')+'；标记为成交日，纵坐标为收盘价格')
 axs[2,col].bar(f.index,f.amount/1e8,color='#7a8fa6');axs[2,col].set_ylabel('成交额/亿元')
 for ax in axs[:,col]:ax.tick_params(axis='x',rotation=25);ax.grid(alpha=.15)
fig.tight_layout();fig.savefig(O/'actual-path-review.png',dpi=125)
