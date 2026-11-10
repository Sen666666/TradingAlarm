import pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
p=Path(__file__).resolve().parents[1];plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False;fig,axes=plt.subplots(3,1,figsize=(14,9),sharex=True)
for ax,sid in zip(axes,['688498.SH','300308.SZ','603115.SH']):
 f=pd.read_parquet(p/'CONTROL/prepared/facts'/f'{sid}.parquet').loc['2025':];ax.plot(f.index,f.close/f.close.iloc[0],label=sid+' 收盘倍数');a=ax.twinx()
 for v,k in [('CONTROL',0),('MARKET_ALL',1),('JOINT',2),('G1_JOINT',3)]:
  z=pd.read_parquet(p/v/'prepared/facts'/f'{sid}.parquet').loc[f.index];a.plot(z.index,z.i_target.astype(float)*.7+k,label=v,alpha=.7,lw=.8)
 ax.grid(alpha=.2);ax.legend(loc='upper left');a.legend(loc='upper right',ncol=2);a.set_ylabel('状态轨道（非实际仓位）')
fig.tight_layout();fig.savefig(p/'round2-state-review.png',dpi=110)
