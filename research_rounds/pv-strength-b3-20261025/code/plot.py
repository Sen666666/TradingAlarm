"""Read-only plots: descriptive temperature is not exposure or trading."""
import os,sys
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/pvs-b3-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
from matplotlib.ticker import FuncFormatter
import numpy as np,pandas as pd
from common import ROOT,B2,NAMES,read,write,sha,now
plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':10})
COLORS=['#37579e','#72a7bd','#ddd9cf','#e5b367','#cb6147']
CMAP=ListedColormap(COLORS);NORM=BoundaryNorm([-2.5,-1.5,-.5,.5,1.5,2.5],5)

def draw(f,title,path):
    fig,axs=plt.subplots(6,1,figsize=(15,12.5),sharex=True,
        gridspec_kw={'height_ratios':[3.1,.85,1.5,1.25,1.1,1.1]})
    ax=axs[0];ax.plot(f.index,f.close,color='#243f50',lw=1.2,label='研究收盘（对数轴）')
    if 'e0_target' in f:
        ax.fill_between(f.index,0,1,where=f.e0_target.eq(1),transform=ax.get_xaxis_transform(),color='#dd8c4e',alpha=.13,label='E0有效（非持仓）')
        ax.plot(f.index,f.e0_floor.where(f.e0_target.eq(1)),color='#a77958',lw=.75,label='E0保护点')
    freeze=f.grade.eq(-2);ax.scatter(f.index[freeze],f.close[freeze],s=11,color=COLORS[0],label='B3 freeze观察',zorder=3)
    ax.set_yscale('log');ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:,.4g}'));ax.minorticks_off()
    ax.set_title(title,loc='left',fontsize=13,pad=12);ax.legend(loc='upper left',ncol=3,fontsize=8);ax.set_ylabel('研究价')
    axs[1].bar(f.index,f.volume/1e6,width=1,color='#93a8af');axs[1].set_ylabel('量 / 百万')
    ax=axs[2]
    if 'price_grade' in f:ax.step(f.index,f.price_grade,where='post',color='#b5b5b5',lw=.9,ls='--',label='去量创建条件对照')
    ax.step(f.index,f.grade,where='post',color='#4a545c',lw=.8)
    ax.scatter(f.index,f.grade,c=f.grade,cmap=CMAP,norm=NORM,s=13,zorder=3)
    ax.set_yticks([-2,-1,0,1,2],['freeze 急破','cold 下行','neutral 中性','warm 建立/整理','hot 双尺度上行'])
    ax.set_ylim(-2.45,2.45);ax.set_ylabel('B3 上行证据\n有序类别，非等距收益')
    if 'price_grade' in f:ax.legend(loc='upper left',fontsize=8)
    ax=axs[3];ax.axhspan(-.5,.5,color='#dbdcd6',alpha=.5)
    for y in [-1,1]:ax.axhline(y,color='#999',ls='--',lw=.8)
    ax.plot(f.index,f.z_21,color='#215f92',lw=1.2,label='月尺度 z21')
    ax.plot(f.index,f.z_63,color='#a76843',lw=1,label='季尺度 z63');ax.axhline(0,color='#aaa',lw=.6)
    ax.set_ylabel('推进 / 自身波动\n±1进入，±0.5释放');ax.legend(loc='upper left',ncol=2,fontsize=8)
    ax=axs[4];ax.bar(f.index,f.shock,width=1,color=np.where(f.shock.ge(0),'#83a899','#89a3c0'),label='原始日冲击 q')
    ax.plot(f.index,f.effective_shock,color='#643c6f',lw=.65,label='参与调整 q_eff');ax.axhline(-2,color='#37579e',ls='--',lw=.8)
    ax.set_ylabel('即时冲击\n非统计显著性');ax.legend(loc='upper left',ncol=2,fontsize=8)
    ax=axs[5]
    if 'b1_strength' in f:ax.plot(f.index,f.b1_strength,color='#9b77b2',lw=.9,label='B1旧分数')
    if 'b2_signed_retention' in f:ax.plot(f.index,f.b2_signed_retention,color='#93aaa0',lw=.75,label='B2方向×结构保留（非强度）')
    if 'b1_strength' not in f:ax.plot(f.index,f.amplitude_21,color='#215f92',lw=.9,label='月尺度拟合log百分点幅度')
    ax.axhline(0,color='#aaa',lw=.6);ax.set_ylabel('旧描述对照' if 'b1_strength' in f else '原单位幅度');ax.legend(loc='upper left',ncol=2,fontsize=8)
    for ax in axs:ax.grid(alpha=.17);ax.margins(x=.01)
    fig.text(.99,.008,'只描述已知量价；已见开发历史；E0未改；无账户回测',ha='right',fontsize=9,color='#666')
    fig.tight_layout(rect=(0,.02,1,1));fig.savefig(path,dpi=120);plt.close(fig)

def main(kind):
    target=ROOT/'figures'/kind;target.mkdir(parents=True,exist_ok=False);records=[]
    if kind=='real':
        for w in read(B2/'figures/real-manifest.json')['plots']:
            f=pd.read_parquet(ROOT/'results'/(w['asset']+'.parquet')).loc[w['start']:w['end']]
            p=target/(w['id']+'.png');draw(f,f"{w['name']} {w['asset']} · {f.index[0].date()}—{f.index[-1].date()}",p)
            records.append({**{k:w[k] for k in ['id','asset','name','start','end']},'path':str(p),'sha256':sha(p)})
        assert len(records)==22
    else:
        for p in sorted((ROOT/'validation').glob('*.parquet')):
            if 'prefix' in p.stem:continue
            f=pd.read_parquet(p)
            if 'grade' not in f:continue
            out=target/(p.stem+'.png');draw(f,'固定合成 · '+p.stem,out)
            records.append(dict(id=p.stem,path=str(out),sha256=sha(out)))
        assert len(records)==24,len(records)
    write(ROOT/'figures'/(kind+'-manifest.json'),dict(recorded_at=now(),plots=records));print({'kind':kind,'plots':len(records)})
if __name__=='__main__':main(sys.argv[1])
