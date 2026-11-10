from drug_common import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
local=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True).loc['2024':];broad=pd.read_csv(PREP/'recovery.csv',index_col=0,parse_dates=True).reindex(local.index);cov=pd.read_csv(O/'coverage.csv',index_col=0,parse_dates=True).reindex(local.index)
fig,axes=plt.subplots(4,1,figsize=(15,11),sharex=True,gridspec_kw={'height_ratios':[3,2,1,1]})
for frame,label,color in [(local,'创新药48股','#c24d3c'),(broad,'大盘1709股','#3475ae')]:
 axes[0].plot(frame.index,frame.market/frame.market.iloc[0],label=label,color=color);axes[1].plot(frame.index,frame.breadth,label=label,color=color,lw=.8)
 axes[0].legend();axes[0].set_ylabel('合成价格参考/首日值');axes[1].axhline(.6,ls='--',color='grey');axes[1].set_ylabel('方向金额正广度')
for k,(frame,label,color) in enumerate([(local,'创新药恢复条件成立','#c24d3c'),(broad,'大盘恢复条件成立','#3475ae')]):
 idx=frame.index[frame.breakout];axes[2].scatter(idx,[k]*len(idx),s=12,c=color,label=label)
axes[2].set_yticks([0,1],['创新药','大盘']);axes[2].set_ylabel('环境条件成立\n非账户实际恢复')
axes[3].plot(cov.index,cov.valid_sectors,color='#795da5');axes[3].axhline(3,ls='--',color='grey');axes[3].set_yticks([0,1,2,3,4]);axes[3].set_ylabel('创新药有效行业数')
for ax in axes:ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(O/'recovery-review.png',dpi=120)
