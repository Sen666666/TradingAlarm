from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
fig,axs=plt.subplots(7,2,figsize=(18,18))
for row,sym in enumerate(['USHJ512480','USHJ510300','USHJ518880','HK00002','HK00101','HK09618','HK03033']):
 d=pd.read_parquet(R.parent/'market-regimes-exit-20261024/inputs'/f'{sym}.parquet').loc['2021-01-01':'2026-10-16'];axs[row,0].plot(d.index,d.close/d.close.iloc[0],lw=.7,color='black');axs[row,0].set_title(sym+' continuous raw price normalized')
 for j,p in enumerate(['F','C2','R','G']):
  s=pd.read_parquet(R/'prepared'/('continuous_'+sym)/f'{p}.parquet');axs[row,1].step(s.index,s.target*.7+j,where='post',lw=.7)
 axs[row,1].set_yticks(range(4),['F','C2','R','G']);axs[row,1].set_title(sym+' sequential states; no accounts')
 for ax in axs[row]:ax.grid(alpha=.15)
fig.tight_layout();fig.savefig(R/'review/continuous-all.png',dpi=100)
