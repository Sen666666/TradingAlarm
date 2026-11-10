from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path('results/first-pullback-audit');f=pd.read_json(OUT/'date-balanced-summary.json');f=f[f.group.eq('a485')]
fig,axes=plt.subplots(1,2,figsize=(11,4))
features=['drawdown21','down_volume_share5','volume_ratio5_21'];names=['Shallower drawdown','More down-day volume','Higher volume ratio']
for ax,h in zip(axes,[5,21]):
 p=f[f.horizon.eq(h)].pivot(index='feature',columns='year',values='mean_difference').reindex(features)*100
 im=ax.imshow(p.to_numpy(),cmap='RdYlGn',vmin=-3,vmax=3,aspect='auto');ax.set_xticks(range(len(p.columns)),p.columns);ax.set_yticks(range(3),names);ax.set_title(f'Next {h} observed-bar return difference')
 for i in range(3):
  for j in range(len(p.columns)):ax.text(j,i,f'{p.iloc[i,j]:+.2f} pp',ha='center',va='center')
fig.suptitle('First short-negative event: same-date high-minus-low feature groups\nA485 development sample; descriptive future returns, not strategy PNL')
fig.tight_layout();fig.savefig(OUT/'contrasts.png',dpi=150)
