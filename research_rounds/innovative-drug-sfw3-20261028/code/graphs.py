from drug_common import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
CASES=[('600276.SH','2024-01-01','2026-10-27'),('688235.SH','2024-01-01','2026-10-27'),('688180.SH','2024-01-01','2026-10-27'),('300347.SZ','2024-01-01','2026-10-27'),('600566.SH','2024-01-01','2026-10-27'),('000661.SZ','2024-01-01','2026-10-27')]
def graphs(overlay):
 meta=read(POOL)['meta'];fig,axs=plt.subplots(4,3,figsize=(18,12),gridspec_kw={'height_ratios':[3,1,3,1]})
 for k,(sid,start,end) in enumerate(CASES):
  i,j=2*(k//3),k%3;f=pd.read_parquet(PREP/'signals'/f'{sid}.parquet').loc[start:end];ax=axs[i,j];ax.plot(f.index,f.close,c='#333',lw=1);ax.fill_between(f.index,f.low,f.high,color='#aaa',alpha=.25);ax.set_title(meta[sid]['name']+' '+sid);axs[i+1,j].bar(f.index,f.amount/1e8,color='#7892a1');axs[i+1,j].set_ylabel('成交额/亿元')
  if overlay:
   g=pd.read_parquet(PREP/'facts'/f'{sid}.parquet').reindex(f.index);ss=pd.read_parquet(PREP/'strict'/f'{sid}.parquet').reindex(f.index);z=pd.read_parquet(PREP/'fast'/f'{sid}.parquet').reindex(f.index);ax.plot(g.index,g.i_floor,label='原I保护',c='#b88624',lw=.9);mask=z.event.eq(1);ax.scatter(z.index[mask],z.loc[mask,'pivot'],s=9,label='F低点确认',color='#237aab');mask=g.i_buy.fillna(False)&ss.strict_target.fillna(False);ax.scatter(f.index[mask],f.close[mask],s=9,c='#dd4444',label='S买点');ax.legend(fontsize=7)
  for a in [ax,axs[i+1,j]]:a.tick_params(axis='x',rotation=20,labelsize=7)
 fig.tight_layout();fig.savefig(O/('overlay.png' if overlay else 'raw.png'),dpi=115)
if __name__=='__main__':graphs(sys.argv[1]=='overlay')
