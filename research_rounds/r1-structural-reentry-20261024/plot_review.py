from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';S=R.parent/'market-regimes-exit-20261024/inputs';(R/'review').mkdir(exist_ok=True)
cases=json.loads((R/'cases.json').read_text());colors={'E0':'#235e91','R':'#df7d2b','R1':'#16866b'}
for k in range(0,len(cases),3):
 fig,axes=plt.subplots(3,3,figsize=(17,10),gridspec_kw={'width_ratios':[2.7,1,1.8]})
 for i,c in enumerate(cases[k:k+3]):
  d=pd.read_parquet(S/f'{c["symbol"]}.parquet').loc[c['start']:c['end']];r1=pd.read_parquet(R/'prepared'/c['id']/'R1.parquet');states={p:pd.read_parquet(P/'prepared'/c['id']/f'{p}.parquet') for p in ['E0','R']};states['R1']=r1
  ax=axes[i,0];ax.plot(d.index,d.close,color='#ad891b',lw=.85);ax.step(d.index,states['E0'].floor.where(states['E0'].target.astype(bool)),where='post',color=colors['E0'],lw=.6,alpha=.7)
  rr=r1[r1.recovery_entry.astype(bool)];ax.scatter(rr.index,d.close.loc[rr.index],marker='^',s=20,color=colors['R1'],label='R1恢复确认日（未撮合）');ax.set_title(c['id']+' '+c['name']+' '+c['type'],fontsize=10);ax.legend(fontsize=7,loc='upper left')
  axes[i,1].bar(d.index,d.volume/d.volume.median(),width=1,color='#a5afb9');axes[i,1].set_title('原始量 / 窗内中位量',fontsize=9)
  for j,p in enumerate(['E0','R','R1']):axes[i,2].step(d.index,states[p].target*.65+j,where='post',color=colors[p],lw=.85)
  axes[i,2].set_yticks([.3,1.3,2.3],['E0','R','R1']);axes[i,2].set_ylim(-.1,2.9);axes[i,2].set_title(f'资格轨迹：R1恢复{int(r1.recovery_entry.sum())}次',fontsize=9)
  for ax in axes[i]:ax.grid(alpha=.15);ax.tick_params(labelsize=7)
 fig.suptitle('R1账户前图检：原始价格/成交量、结构支持和因果信号；没有新账户结果',fontsize=14);fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(R/'review'/f'sheet-{k//3+1}.png',dpi=115);plt.close(fig)
# Focused prior diagnosis and known failure windows, still signal-only.
for sym,start,end,name in [('USHJ518880','2024-08-01','2025-11-20','gold-2024-25'),('USHJ518880','2026-03-01','2026-06-30','gold-decline-2026'),('USHJ512480','2025-04-01','2025-11-30','semi-bull-2025'),('USHJ512480','2026-06-01','2026-10-23','semi-decline-2026')]:
 case='continuous_'+sym if not (sym=='USHJ512480' and end=='2026-10-23') else 'semi_ytd26';full_d=pd.read_parquet(S/f'{sym}.parquet');full_q=full_d.volume/full_d.volume.shift().rolling(21).median();d=full_d.loc[start:end];r1=pd.read_parquet(R/'prepared'/case/'R1.parquet').loc[start:end];st={p:pd.read_parquet(P/'prepared'/case/f'{p}.parquet').loc[start:end] for p in ['E0','R']};st['R1']=r1
 fig,axs=plt.subplots(3,1,figsize=(13,7.3),sharex=True,gridspec_kw={'height_ratios':[3,1,1]});axs[0].plot(d.index,d.close,color='#aa871a',lw=1.1);axs[0].step(d.index,st['E0'].floor.where(st['E0'].target.astype(bool)),where='post',lw=.8,color=colors['E0'],label='E0结构支持');rr=r1[r1.recovery_entry.astype(bool)];axs[0].scatter(rr.index,d.close.loc[rr.index],color=colors['R1'],marker='^',s=35,label='R1恢复确认');axs[0].legend(fontsize=8);axs[0].set_title(name+'：信号轨迹，未运行账户')
 axs[1].bar(d.index,full_q.reindex(d.index),width=1,color='#a5afb9');axs[1].set_ylabel('相对量')
 for j,p in enumerate(['E0','R','R1']):axs[2].step(d.index,st[p].target*.65+j,where='post',lw=1,color=colors[p])
 axs[2].set_yticks([.3,1.3,2.3],['E0','R','R1']);axs[2].set_ylim(-.1,2.9)
 for ax in axs:ax.grid(alpha=.15)
 fig.tight_layout();fig.savefig(R/'review'/f'{name}.png',dpi=120);plt.close(fig)
print('source review figures prepared, accounts0')
