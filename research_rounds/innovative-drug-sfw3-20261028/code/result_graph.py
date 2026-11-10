from audit import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(2,3,figsize=(16,9),sharex='col')
colors={'I':'#888888','ACT':'#2056ae','S':'#ab8c39','F':'#ab6a87','SF':'#8b5ba8','SW3F':'#18936b','BH':'#c84835'}
for j,c in enumerate(STARTS):
 data=rows(O/c/'accounts-v2/daily.jsonl.gz')
 for i,scenario in enumerate(['base','delay1']):
  for mode in MODES if c=='S0' else ['ACT','SW3F']:
   rr=[r for r in data if r['account']==mode+'__S0_'+scenario];axs[i,j].plot([pd.Timestamp(r['at'][:10]) for r in rr],[float(r['nav'])/1e6 for r in rr],label=mode,color=colors[mode],lw=1.6 if mode=='SW3F' else .9)
  axs[i,j].set_title(c+' '+('正常执行' if i==0 else '执行延迟'));axs[i,j].set_ylabel('净值/初始100万元');axs[i,j].grid(alpha=.2);axs[i,j].tick_params(axis='x',rotation=25)
h,l=axs[0,0].get_legend_handles_labels();fig.legend(h,l,loc='lower center',ncol=7);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(O/'equity-paths.png',dpi=125)
