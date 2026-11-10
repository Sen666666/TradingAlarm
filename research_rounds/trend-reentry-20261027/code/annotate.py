from study import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
snap=Path(read(O/'input.json')['snapshot']);windows=read(O/'windows.json')
for page in range(3):
 fig,ax=plt.subplots(2,3,figsize=(18,8),sharex='col',gridspec_kw={'height_ratios':[3,1]})
 for j,(sid,start,end) in enumerate(windows[page*3:page*3+3]):
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];g=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);ax[0,j].plot(f.index,f.close,color='#444444',lw=.8);ax[0,j].fill_between(f.index,f.low,f.high,color='#aaaaaa',alpha=.3);ax[0,j].plot(g.index,g.e0_floor.where(g.e0_target.fillna(False).astype(bool)),label='E0保护',color='#c19b55',lw=.8)
  for v,col,marker in [('PB','#2066ad','^'),('BOX','#c14842','o')]:
   z=pd.read_parquet(O/v/'signals'/f'{sid}.parquet').reindex(f.index);q=z.event.fillna(False)&~g.i_buy.fillna(False).astype(bool);ax[0,j].scatter(f.index[q],f.close[q],s=30,marker=marker,color=col,label=v+'新增');ax[0,j].scatter(f.index[q],z.floor[q],s=20,marker='_',color=col)
  ax[0,j].set_title(sid);ax[0,j].legend(fontsize=8);ax[1,j].bar(f.index,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('金额/亿元');ax[1,j].tick_params(axis='x',rotation=25)
 fig.suptitle('局部新入口标注；短横线=当日冻结局部保护；非实际成交');fig.tight_layout();fig.savefig(O/f'annotated-{page+1}.png',dpi=115);plt.close(fig)
