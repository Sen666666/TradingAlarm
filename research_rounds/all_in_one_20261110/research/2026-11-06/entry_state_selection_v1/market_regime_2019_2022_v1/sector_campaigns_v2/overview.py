from pathlib import Path
import pandas as pd,json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
O=Path(__file__).parent;P=O.parent;S=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/sector-data-v2');m=json.loads((S/'manifest.json').read_text())['series'];major=pd.read_csv(P/'MAJOR_24_INDUSTRY_ALIGNMENT.csv').industry.unique().tolist();F=FontProperties(fname='/System/Library/Fonts/STHeiti Light.ttc');fig,axs=plt.subplots(6,4,figsize=(19,19))
for ax,name in zip(axs.ravel(),major):
 x=next(x for x in m if x['name']==name and x['market']=='A');d=pd.read_parquet(x['bars']['path']).loc['2018-12-28':'2023-12-29'];s=d.close/d.close.iloc[0];ax.plot(s.index,s,lw=1);ax.set_title(name,fontproperties=F);ax.axvline(pd.Timestamp('2022-12-30'),color='gray',ls='--');ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(O/'OVERVIEW24.png',dpi=100)
