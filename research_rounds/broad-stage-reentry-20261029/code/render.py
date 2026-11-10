"""Original OHLC/amount with actual BSR-1 fills and holding protection."""
from study import *
from raw_review import CASES
import gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.collections import LineCollection
plt.rcParams['font.family']=['Arial Unicode MS','PingFang SC','DejaVu Sans']
def load(p):return json.loads(Path(p).read_text())
def main():
    with gzip.open(O/'results/daily.jsonl.gz','rt') as f:daily=[json.loads(x) for x in f]
    by={k:[r for r in daily if r['account']==k] for k in ['P0','P1','N1']}
    obj=load(O/'results/N1.json');names=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').name
    for sid in CASES:
        f=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet').loc['2024-01-02':'2026-10-27']
        f=f.loc[f.observed_bar & f.price_eligible & ~f.synthetic_event_bar]
        fact=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet').reindex(f.index)
        base=f.close.iloc[0];x=md.date2num(f.index.to_pydatetime());dates=pd.DatetimeIndex([pd.Timestamp(r['at'][:10]) for r in by['N1']])
        fig,axs=plt.subplots(7,1,figsize=(18,15),sharex=True,gridspec_kw={'height_ratios':[4,1,1,1,1,1,1]},layout='constrained')
        colors=np.where(f.close>=f.open,'#c83d48','#248268')
        axs[0].add_collection(LineCollection([[(t,lo/base),(t,hi/base)] for t,lo,hi in zip(x,f.low,f.high)],colors=colors,linewidths=.5))
        axs[0].vlines(x,f.open/base,f.close/base,colors=colors,linewidth=1.1)
        axs[0].plot(f.index,fact.i_floor/base,c='#aaa',lw=.7,label='原I/E0保护')
        for kind,color,label in [('trial','#a653b5','试仓有效保护'),('core','#19764b','核心有效保护'),('mobile','#cf9223','机动最高保护')]:
            values=[]
            for r in by['N1']:
                lines=[float(z['floor'])/base for z in r['layers'] if z['sid']==sid and z['kind']==kind]
                values.append(max(lines) if lines else np.nan)
            axs[0].plot(dates,values,c=color,lw=1.1,label=label)
        first=True
        for t in obj['trades']:
            if t['security_id']!=sid:continue
            day=pd.Timestamp(t['at'][:10]);p=float(t['price'])*float(fact.loc[day].factor)/base
            buy=t['side']=='buy';color='#c83d48' if buy and t['kind']=='trial' else '#d18f16' if buy else '#208c80'
            axs[0].scatter(day,p,c=color,marker='^' if buy else 'v',s=35,zorder=6)
            if first:axs[0].annotate(t['at'][:10],(day,p),fontsize=7,xytext=(3,12),textcoords='offset points');first=False
        for z in obj['audit']:
            if z['kind']=='stage_promote' and z['sid']==sid:
                day=pd.Timestamp(z['at'][:10]);axs[0].scatter(day,f.loc[day].close/base,marker='D',s=19,c='#6f45ae',zorder=7)
        axs[0].set_title(f'{names[sid]} {sid}｜实际买卖与阶段保护：红▲试仓、橙▲机动、青▼卖出、紫◆转核心',loc='left')
        axs[0].set_ylabel('因果价格/期初=1');axs[0].legend(fontsize=8,ncol=4,loc='upper left');axs[0].autoscale_view()
        axs[1].bar(f.index,f.amount/1e8,color=colors,width=1);axs[1].set_ylabel('金额/亿元')
        for n,k in enumerate(['P0','P1','N1'],2):
            weight=[];core=[];raw=fact.raw_close.reindex(dates,method='ffill')
            for d,r in zip(dates,by[k]):
                price=float(raw.loc[d]);weight.append(r['positions'].get(sid,0)*price/float(r['nav'])*100)
                core.append(sum(z['qty'] for z in r['layers'] if z['sid']==sid and z['kind']=='core')*price/float(r['nav'])*100)
            axs[n].fill_between(dates,0,weight,alpha=.4,color=['#248268','#c74848','#4867b0'][n-2]);axs[n].plot(dates,core,c='#333',lw=.7)
            axs[n].set_ylabel(k+'权重%')
        roles=[]
        for r in by['N1']:
            layers=[z for z in r['layers'] if z['sid']==sid]
            roles.append(2 if any(z['kind']=='core' for z in layers) else 1 if layers else 0)
        axs[5].step(dates,roles,where='post',c='#6f45ae');axs[5].set_yticks([0,1,2],['空仓','试仓','有核心']);axs[5].set_ylabel('N1状态')
        axs[6].step(dates,[int(r['on']) for r in by['N1']],where='post',c='#444');axs[6].set_ylabel('ACT开启');axs[6].set_ylim(-.1,1.1)
        for ax in axs:ax.grid(alpha=.15)
        axs[-1].xaxis.set_major_formatter(md.DateFormatter('%Y-%m'))
        fig.savefig(O/'charts'/f'detail-{sid}.png',dpi=135);plt.close(fig)
    print('Rendered 9 complete actual holding paths; no strategy rerun.')
if __name__=='__main__':main()
