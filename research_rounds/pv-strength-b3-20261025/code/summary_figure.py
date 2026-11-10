"""Compact user-facing figure from saved outputs; does not run the model."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/pvs-b3-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
from common import ROOT
from plot import COLORS,CMAP,NORM
f=pd.read_parquet(ROOT/'results/AU0.parquet').loc['2025-01-01':]
fig,ax=plt.subplots(2,1,figsize=(13,7),sharex=True,gridspec_kw={'height_ratios':[2.5,1.4]})
ax[0].plot(f.index,f.close,color='#284b5c',lw=1.5)
ax[0].fill_between(f.index,0,1,where=f.e0_target.eq(1),transform=ax[0].get_xaxis_transform(),color='#d89d67',alpha=.18,label='E0有效（非持仓）')
ax[0].set_yscale('log');ax[0].yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:,.0f}'));ax[0].minorticks_off();ax[0].legend(loc='upper left')
ax[0].set_title('沪金主连 · PVS-B3：整理更稳、急跌及时，缓慢走弱仍会漏判',loc='left',pad=14,fontsize=15)
ax[0].set_ylabel('研究收盘 / 对数轴')
ax[1].step(f.index,f.grade,where='post',color='#56676d',lw=.8)
ax[1].scatter(f.index,f.grade,c=f.grade,cmap=CMAP,norm=NORM,s=9,zorder=3)
ax[1].set_yticks([-2,-1,0,1,2],['freeze','cold','neutral','warm','hot']);ax[1].set_ylim(-2.4,2.6)
ax[1].set_ylabel('当前上行证据类别')
for a in ax:
    a.axvspan(pd.Timestamp('2025-05-27'),pd.Timestamp('2025-08-29'),color='#d9e7e1',alpha=.35)
    a.axvspan(pd.Timestamp('2026-04-13'),pd.Timestamp('2026-06-05'),color='#e7c7c0',alpha=.25)
    a.grid(alpha=.2);a.margins(x=.015)
ax[0].annotate('平稳整理',xy=(pd.Timestamp('2025-07-15'),790),xytext=(pd.Timestamp('2025-05-20'),1000),arrowprops={'arrowstyle':'->','color':'#5b7b6c'},fontsize=11)
ax[0].annotate('1/30：hot → freeze',xy=(pd.Timestamp('2026-01-30'),1161.42),xytext=(pd.Timestamp('2025-09-20'),1280),arrowprops={'arrowstyle':'->','color':'#37579e'},fontsize=11)
ax[0].annotate('4/13—6/5：下跌6.65%\n仍被标为neutral',xy=(pd.Timestamp('2026-05-15'),999),xytext=(pd.Timestamp('2026-05-02'),760),arrowprops={'arrowstyle':'->','color':'#b56552'},fontsize=11)
fig.text(.99,.015,'仅状态图检；旧算法保留；无买卖或账户回测；全部为已见开发历史',ha='right',fontsize=9,color='#677')
fig.tight_layout(rect=(0,.035,1,1));p=ROOT/'figures/gold-summary.png'
if p.exists():raise FileExistsError(p)
fig.savefig(p,dpi=130);plt.close(fig);print(p)
