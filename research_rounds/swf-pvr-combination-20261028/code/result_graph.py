from audit import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(2,3,figsize=(17,9),sharex='col')
colors={'RS-ACT':'#777777','RS-SF':'#245bb0','RS-SW3F':'#7d82c9','RS-SW10F':'#bba9e4','PVR-SF':'#aa6b22','PVR-SW3F':'#15906d','PVR-SW10F':'#d34446'}
for j,c in enumerate(STARTS):
 for rank in ['RS','PVR']:
  data=rows(O/rank/c/'accounts-v2/daily.jsonl.gz')
  for i,scenario in enumerate(['base','delay1']):
   aids=sorted({r['account'] for r in data if r['account'].endswith('_'+scenario)})
   for aid in aids:
    rr=[r for r in data if r['account']==aid];strategy=rank+'-'+aid.split('__')[0];axs[i,j].plot([pd.Timestamp(r['at'][:10]) for r in rr],[float(r['nav'])/1e6 for r in rr],label=strategy,color=colors[strategy],lw=1.4 if strategy.startswith('PVR-SW') else .9,alpha=.9)
   axs[i,j].set_title(c+' '+('正常执行' if i==0 else '执行延迟'));axs[i,j].set_ylabel('净值 / 初始100万元');axs[i,j].grid(alpha=.2);axs[i,j].tick_params(axis='x',rotation=30)
handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=7);fig.tight_layout(rect=[0,.05,1,1]);fig.savefig(O/'equity-paths.png',dpi=125)
