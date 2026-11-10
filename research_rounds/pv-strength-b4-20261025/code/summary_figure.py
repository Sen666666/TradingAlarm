"""Compact illustration from stored outputs, with no model execution."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/pvs-b4-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from common import ROOT
plt.rcParams.update({'font.family':'Arial Unicode MS','font.size':10,'axes.unicode_minus':False})
specs=[('AU0','2025-05-01','2025-08-29','黄金整理：幅度小，仍有过零'),
       ('AU0','2026-01-15','2026-06-30','黄金急跌与阴跌：分量分开读'),
       ('688981.SH','2024-09-01','2024-10-31','中芯快启动：新证据可直接确认')]
fig,axs=plt.subplots(4,3,figsize=(15,9),gridspec_kw={'height_ratios':[2.7,.65,1.7,.8]},sharex='col')
for c,(sid,start,end,title) in enumerate(specs):
    f=pd.read_parquet(ROOT/'results'/(sid+'.parquet')).loc[start:end]
    ax=axs[0,c];ax.plot(f.index,f.close,color='#294c5e',lw=1.4)
    ax.fill_between(f.index,0,1,where=f.e0_target.eq(1),transform=ax.get_xaxis_transform(),color='#d6a770',alpha=.16)
    ax.scatter(f.index[f.acute_down.eq(1)],f.close[f.acute_down.eq(1)],marker='v',color='#356da8',s=22,label='当日急跌')
    ax.set_yscale('log');ax.set_yticks(np.geomspace(f.close.min(),f.close.max(),4));ax.yaxis.set_major_formatter(FuncFormatter(lambda y,_:f'{y:,.0f}'));ax.minorticks_off()
    ax.set_title(title+'\n'+str(f.index[0].date())+'—'+str(f.index[-1].date()),fontsize=11,loc='left');ax.legend(loc='upper left',fontsize=8)
    axs[1,c].bar(f.index,f.volume/1e6,color='#91a7ad',width=1)
    ax=axs[2,c];ax.plot(f.index,f.mu5_bp,color='#b86233',lw=.9,label='μ5')
    ax.plot(f.index,f.mu21_bp,color='#3579a1',lw=1.3,label='μ21');ax.axhline(0,color='#8a979b',lw=.65)
    ax.legend(loc='upper left',ncol=2,fontsize=8)
    ax=axs[3,c]
    for h,offset,color in [(21,.07,'#b86233'),(63,-.07,'#3579a1')]:
        ax.step(f.index,f[f'S{h}']+offset,where='post',color=color,lw=.9,label=f'S{h}')
        m=f[f'confirmed_{h}'].eq(1);ax.scatter(f.index[m],f.loc[m,f'S{h}']+offset,color=color,s=15)
    ax.set_yticks([-1,1],['下','上']);ax.set_ylim(-1.35,1.35);ax.legend(loc='center right',ncol=2,fontsize=7)
    ax.xaxis.set_major_locator(md.AutoDateLocator(minticks=3,maxticks=4));ax.xaxis.set_major_formatter(md.DateFormatter('%m-%d'))
    for a in axs[:,c]:a.grid(alpha=.15);a.margins(x=.02)
axs[0,0].set_ylabel('研究价格 · 对数轴');axs[1,0].set_ylabel('量 / 百万')
axs[2,0].set_ylabel('平滑净推进\nlog基点 / 观察');axs[3,0].set_ylabel('结构可陈旧\n不是热度')
fig.suptitle('PVS-B4：方向看符号，推进看大小，结构转向要新增量价证据',x=.04,ha='left',fontsize=15)
fig.text(.04,.026,'底纹为原E0结构有效，非持仓；三列纵轴独立。μ仍可能迟滞/过零；S同上不等于强。完整7标的22窗见交互报告。',fontsize=10,color='#56686d')
fig.tight_layout(rect=(0,.05,1,.96));fig.savefig(ROOT/'figures/summary.png',dpi=125);plt.close(fig)
