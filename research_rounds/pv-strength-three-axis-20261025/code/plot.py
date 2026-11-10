"""Read-only rendering, no economic engine. Imports no model."""
import os,sys
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/pvs-b2-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np,pandas as pd
from common import ROOT,OLD,NAMES,read,write,sha,now
plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':9})

def draw(f,title,path):
    fig,axs=plt.subplots(7,1,figsize=(15,14),sharex=True,gridspec_kw={'height_ratios':[3,1,1,1.5,1.2,1.2,1.2]})
    ax=axs[0];ax.plot(f.index,f.close,color='#20394d',lw=1,label='研究收盘 / 对数轴')
    if 'e0_target' in f:
        ax.fill_between(f.index,0,1,where=f.e0_target.eq(1),transform=ax.get_xaxis_transform(),color='#e5a06c',alpha=.18,label='E0有效（非持仓）')
        ax.plot(f.index,f.e0_floor.where(f.e0_target.eq(1)),color='#b56b41',lw=.85,label='E0支持')
    ax.plot(f.index,f.support_price.where(f.direction.eq(1)),color='#168c76',lw=.8,label='B2上行支持')
    ax.plot(f.index,f.support_price.where(f.direction.eq(-1)),color='#c84d59',lw=.8,label='B2下行阻力')
    ax.set_yscale('log');ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:,.4g}'));ax.minorticks_off()
    ax.set_title(title,loc='left');ax.legend(loc='upper left',ncol=4,fontsize=8);ax.set_ylabel('研究价')
    axs[1].bar(f.index,f.volume/1e6,width=1,color='#a2b2bc');axs[1].set_ylabel('量 / 百万原单位')
    if 'b1_strength' in f:axs[2].plot(f.index,f.b1_strength,color='#8d65b1',lw=.9,label='旧B1 S（有饱和）')
    else:axs[2].text(.01,.55,'新增合成：未另算B1',transform=axs[2].transAxes,color='#7b8790')
    axs[2].axhline(0,color='#999',lw=.6);axs[2].set_ylim(-105,105);axs[2].set_yticks([-100,0,100]);axs[2].set_ylabel('旧B1分数')
    axs[3].plot(f.index,f.pace_5,color='#93b7bb',lw=.8,label='P5 周观察速度')
    axs[3].plot(f.index,f.pace_21,color='#285f91',lw=1.2,label='P21 月观察速度')
    axs[3].axhline(0,color='#999',lw=.6);axs[3].set_ylabel('P / 自身波动单位\n非概率、无总分');axs[3].legend(loc='upper left',fontsize=8,ncol=2)
    ax=axs[4];ax.fill_between(f.index,0,f.signed_retention.where(f.direction.eq(1)),color='#168c76',alpha=.2)
    ax.fill_between(f.index,0,f.signed_retention.where(f.direction.eq(-1)),color='#c84d59',alpha=.2)
    ax.plot(f.index,f.signed_retention,color='#677b7b',lw=.8);ax.set_ylim(-105,105);ax.set_yticks([-100,0,100]);ax.axhline(0,color='#999',lw=.6)
    ax.set_ylabel('R = 方向 × 保留%\n新腿100≠成熟强势')
    broken=f.structure_broken.eq(1)
    if broken.any():ax.scatter(f.index[broken],np.clip(100*f.pre_direction[broken]*f.old_retention_at_t[broken],-103,103),color='#e18b2b',s=12,zorder=3,label='旧R破坏值（越界置图沿，原值见CSV）');ax.legend(loc='upper left',fontsize=8)
    ax=axs[5];col=np.where(f.shock.ge(0),'#6da698','#c96b75');ax.bar(f.index,f.shock,width=1,color=col)
    ax.axhline(0,color='#999',lw=.6);ax.set_ylabel('D 即时冲击\nr / 滞后σ')
    ax=axs[6];ax.plot(f.index,f.down_zone_log_pct,color='#bf4756',lw=1,label='向下量价位移未收复区域')
    ax.plot(f.index,f.up_zone_log_pct,color='#4b9d8c',lw=.8,label='向上量价位移未收复区域')
    if 'all_price_down_zone_log_pct' in f:ax.plot(f.index,f.all_price_down_zone_log_pct,color='#a5a9af',ls='--',lw=.6,label='去量门槛：所有价格冲击的向下区域')
    ax.set_ylabel('D 区域长度\nlog百分点，非收益');ax.legend(loc='upper left',fontsize=8,ncol=3)
    for ax in axs:ax.grid(alpha=.18);ax.margins(x=.01)
    fig.tight_layout();fig.savefig(path,dpi=120);plt.close(fig)

def main(kind):
    folder=ROOT/'figures'/kind;folder.mkdir(parents=True,exist_ok=False);records=[]
    if kind=='synthetic':
        for p in sorted((ROOT/'validation-v1').glob('*.parquet')):
            if 'physical-prefix' in p.stem:continue
            f=pd.read_parquet(p);target=folder/(p.stem+'.png')
            draw(f,p.stem+' | 固定合成 / 无总分、账户或交易门槛',target)
            records.append(dict(id=p.stem,path=str(target),sha256=sha(target)))
        assert len(records)==17
    elif kind=='real':
        windows=read(OLD/'figures/manifest.json')['plots']+[dict(asset='AU0',name='沪金主连',start='2025-05-01',end='2025-08-29',id='au_user_consolidation'),dict(asset='AU0',name='沪金主连',start='2026-03-01',end='2026-06-30',id='au_user_decline')]
        for w in windows:
            f=pd.read_parquet(ROOT/'results'/(w['asset']+'.parquet')).loc[w['start']:w['end']]
            target=folder/(w['id']+'.png')
            draw(f,f"{w['asset']} {w['name']} | {f.index[0].date()}—{f.index[-1].date()} | P/R/D独立描述；已见历史，无账户",target)
            records.append(dict(asset=w['asset'],name=w['name'],id=w['id'],start=w['start'],end=w['end'],actual_first=str(f.index[0].date()),actual_last=str(f.index[-1].date()),path=str(target),sha256=sha(target)))
        assert len(records)==22
    else:raise ValueError('synthetic or real')
    write(ROOT/'figures'/(kind+'-manifest.json'),dict(recorded_at=now(),plots=records))
    print({'kind':kind,'plots':len(records)},flush=True)
if __name__=='__main__':main(sys.argv[1])
