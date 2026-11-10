from audit import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(2,3,figsize=(16,9),sharex='col')
for j,c in enumerate(STARTS):
 for root,reference in [(O,'创新药恢复'),(PARENT,'大盘恢复')]:
  data=rows(root/c/'accounts-v2/daily.jsonl.gz')
  for i,scenario in enumerate(['base','delay1']):
   for mode,color in [('ACT','#3774ac'),('SW3F','#198364')]:
    rr=[r for r in data if r['account']==mode+'__S0_'+scenario];axs[i,j].plot([pd.Timestamp(r['at'][:10]) for r in rr],[float(r['nav'])/1e6 for r in rr],label=mode+' '+reference,color=color,lw=1.3,ls='-' if root==O else '--',alpha=1 if root==O else .6)
   axs[i,j].set_title(c+' '+('正常执行' if i==0 else '执行延迟'));axs[i,j].set_ylabel('净值/初始100万元');axs[i,j].grid(alpha=.2);axs[i,j].tick_params(axis='x',rotation=25)
h,l=axs[0,0].get_legend_handles_labels();fig.legend(h,l,loc='lower center',ncol=4);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(O/'equity-comparison.png',dpi=125)
