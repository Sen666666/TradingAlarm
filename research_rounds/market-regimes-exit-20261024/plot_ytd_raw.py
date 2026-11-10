from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;d=pd.read_parquet(R/'inputs/USHJ512480.parquet').loc['2026-01-01':]
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(2,1,figsize=(15,7),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[3,1]});axes[0].plot(d.index,d.close,c='#426575');axes[0].set_yscale('log');axes[0].set_title('512480 2026完整区间原始量价；末尾五个交易日同源补齐，至10月23日');axes[1].bar(d.index,d.volume,width=1.2,color='#a4b4aa')
for ax in axes:ax.grid(alpha=.15)
fig.savefig(R/'review/raw-ytd.png',dpi=120);plt.close(fig);print('YTD raw only',len(d),'observations',d.index[-1])
