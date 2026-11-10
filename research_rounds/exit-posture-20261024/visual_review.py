from pathlib import Path
import json,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;O=R/'results/v0';m=json.loads((R/'inputs.json').read_text())['series']
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['font.size']=9;plt.rcParams['axes.unicode_minus']=False
for w,interval in [('primary',('2025-01-02','2026-10-13')),('history2024',('2024-01-02','2024-12-31'))]:
 fig,axes=plt.subplots(4,4,figsize=(20,14),layout='constrained')
 for ax,mm in zip(axes.flat,m):
  sym=mm['symbol'];d=pd.read_parquet(R/'inputs'/f'{sym}.parquet').loc[interval[0]:interval[1]];price=d.close/d.open.iloc[0];ax.plot(price.index,price,c='#999',lw=.8,label='价格/初始开盘')
  for p,col in [('E0','#176b78'),('E2','#d57235')]:
   ac=O/'accounts'/f'{sym}__{w}__base__P__{p}';l=pd.read_parquet(ac/'ledger.parquet');f=pd.read_csv(ac/'fills.csv');ax.plot(l.index,l.nav,c=col,label=p+'净值',lw=1.2)
   sells=f.loc[f.side=='sell'];days=pd.to_datetime(sells.date);ax.scatter(days,price.reindex(days),s=9,c=col,marker='x')
  ax.set_title(mm['name']);ax.grid(alpha=.12);ax.tick_params(axis='x',labelrotation=25,labelsize=8)
 for ax in list(axes.flat)[13:]:ax.axis('off')
 axes.flat[0].legend(fontsize=7);fig.suptitle(w+' 全13样本固定复盘：价格、净值、实际卖出；失败不删除',fontsize=16);fig.savefig(R/'charts'/f'review-{w}.png',dpi=100);plt.close(fig)
