"""Complete trajectories and fixed windows. No trading markers or returns."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/pvs-b1-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np,pandas as pd
from data import HERE,read,write,now,sha,NAMES
plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':9})
def draw(f,title,target,synthetic=False):
 if f.empty:return
 fig,axs=plt.subplots(5,1,figsize=(15,10),sharex=True,gridspec_kw={'height_ratios':[3,1,2,1,1]})
 ax=axs[0];ax.plot(f.index,f.close,color='#20394d',lw=1,label='信号坐标收盘')
 if 'e0_target'in f:
  ax.fill_between(f.index,0,1,where=f.e0_target.eq(1),transform=ax.get_xaxis_transform(),color='#e5a06c',alpha=.19,label='原E0有效（非实际持仓）')
  ax.plot(f.index,f.e0_floor.where(f.e0_target.eq(1)),color='#b56b41',lw=.9,label='原E0支持')
 ax.set_yscale('log');ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:,.4g}'));ax.minorticks_off();ax.set_title(title,loc='left');ax.legend(loc='upper left',fontsize=8,ncol=3);ax.set_ylabel('信号价格 / 对数轴')
 axs[1].bar(f.index,f.volume/1e6,width=1.2,color='#9fb0ba');axs[1].set_ylabel('量 / 百万原单位')
 ax=axs[2];ax.plot(f.index,f.strength,color='#703ab2',lw=1.2,label='PVS-B1：持续推进S')
 p='price_only' if synthetic else 'price_only_strength'
 if p in f:ax.plot(f.index,f[p],color='#8797a5',lw=.7,ls='--',label='去量对照 a=1')
 if 'total_21_strength'in f:ax.plot(f.index,f.total_21_strength,color='#1599a0',lw=.65,alpha=.65,label='诊断：含暂时项的21期拟合位移')
 ax.axhline(0,color='#999',lw=.6);ax.set_ylim(-105,105);ax.set_yticks([-100,-50,0,50,100]);ax.set_ylabel('强度 / 非概率');ax.legend(loc='upper left',fontsize=8,ncol=3)
 axs[3].plot(f.index,f.drift_21_pct,color='#3c876b',lw=.9);axs[3].axhline(0,color='#999',lw=.6);axs[3].set_ylabel('底层推进速度\n21期幅度单位 %')
 axs[4].plot(f.index,f.temporary_sigma,color='#b76c71',lw=.9);axs[4].axhline(0,color='#999',lw=.6);axs[4].set_ylabel('暂时偏离 T/σ')
 for ax in axs:ax.grid(alpha=.18);ax.margins(x=.01)
 fig.tight_layout();fig.savefig(target,dpi=120);plt.close(fig)
def main():
 out=HERE/'figures';out.mkdir(exist_ok=False);records=[]
 windows=read(HERE/'reviews/raw/windows.json')
 for sid in NAMES:
  f=pd.read_parquet(HERE/'results'/(sid+'.parquet'));f.index=pd.to_datetime(f.index)
  for start,end,key in [('2021-01-01','2026-10-23',sid.replace('.','_')+'_full')]+[(w['start'],w['end'],w['id']) for w in windows if w['asset']==sid]:
   p=out/(key+'.png');g=f.loc[start:end];draw(g,f'{sid} {NAMES[sid]} | {str(g.index[0].date())}—{str(g.index[-1].date())} | 已见历史开发；无账户/买卖门槛',p)
   records.append(dict(asset=sid,name=NAMES[sid],start=start,end=end,id=key,path=str(p),sha256=sha(p)))
 for p in sorted((HERE/'validation').glob('*.parquet')):
  f=pd.read_parquet(p);draw(f,'合成反例 '+p.stem+' | 固定参数；不是市场预测',(out/(p.stem+'.png')),True)
 write(out/'manifest.json',dict(recorded_at=now(),plots=records,synthetic_figures=9))
 print({'real_figures':len(records),'synthetic_figures':9},flush=True)
if __name__=='__main__':main()
