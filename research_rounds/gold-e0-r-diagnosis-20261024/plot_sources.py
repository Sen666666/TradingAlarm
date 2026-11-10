from pathlib import Path
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt,matplotlib.dates as mdates
from matplotlib import font_manager
from matplotlib.patches import Rectangle
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';A=P/'results/v0/accounts';(R/'charts').mkdir(exist_ok=True)
d=pd.read_parquet(R.parent/'market-regimes-exit-20261024/inputs/USHJ518880.parquet').loc['2021-01-01':'2026-10-16']
s={p:pd.read_parquet(P/'prepared/continuous_USHJ518880'/f'{p}.parquet') for p in ['E0','R']};l={p:pd.read_parquet(A/f'continuous_USHJ518880__{p}__base/ledger.parquet') for p in s};t={p:pd.read_csv(A/f'continuous_USHJ518880__{p}__base/trades.csv') for p in s};colors={'E0':'#225c91','R':'#e27a23'}
e=pd.read_parquet(R/'evidence/events.parquet');f=pd.read_parquet(R/'evidence/features.parquet')
fig,axs=plt.subplots(4,1,figsize=(15,11),sharex=True,gridspec_kw={'height_ratios':[3.9,.9,.65,1.8]})
ax=axs[0];ax.plot(d.index,d.close,color='#b38b17',lw=1.3,label='黄金ETF 518880 收盘价');ax.step(d.index,s['E0'].floor.where(s['E0'].target.astype(bool)),where='post',color=colors['E0'],lw=.8,alpha=.65,label='E0 已知结构保护点')
for p in s:
 tt=t[p];tt=tt.loc[~tt.terminal.astype(bool)];ex=pd.to_datetime(tt.exit_date);px=d.close.reindex(ex).to_numpy();ax.scatter(ex,px,s=35 if p=='R' else 24,marker='x' if p=='R' else 'o',color=colors[p],label=p+' 算法卖出日',zorder=4)
terminal=pd.to_datetime(t['E0'].loc[t['E0'].terminal.astype(bool),'exit_date']);ax.scatter(terminal,d.close.reindex(terminal),marker='s',s=45,facecolors='none',edgecolors=colors['E0'],label='E0 预设末日清算',zorder=5)
en=pd.to_datetime(t['E0'].entry_date);ax.scatter(en,d.close.reindex(en),marker='^',color='#28343f',s=34,label='两者相同的14次买入日',zorder=5)
ax.set_title('黄金ETF 518880：同样买入，截然不同的退出与等待\n2021-01-04—2026-10-16｜同一价格数据，全部14次买入同日同价；点标在成交日收盘价，成交价按次日开盘计',fontsize=14,pad=14)
ax.set_ylabel('元 / 份');ax.legend(ncol=2,loc='upper left',fontsize=9)
ax.annotate('2024-09-05 R早退\n之后432个自然日未再入场',xy=(pd.Timestamp('2024-09-05'),d.loc['2024-09-05','close']),xytext=(pd.Timestamp('2023-07-01'),7.5),arrowprops={'arrowstyle':'->','color':colors['R']},bbox={'boxstyle':'round,pad=.4','fc':'#fff4e7','ec':'#edc699'},fontsize=10,color='#a55313')
ax.annotate('2025-10-23 E0结束该段\n该笔净收益 +62.59%',xy=(pd.Timestamp('2025-10-23'),d.loc['2025-10-23','close']),xytext=(pd.Timestamp('2024-08-01'),10.1),arrowprops={'arrowstyle':'->','color':colors['E0']},bbox={'boxstyle':'round,pad=.4','fc':'#eef6fc','ec':'#bad2e4'},fontsize=10,color=colors['E0'])
axs[1].bar(d.index,d.volume/1e6,width=1.1,color='#a8afb7');axs[1].set_ylabel('成交量\n百万原单位')
for j,p in enumerate(['E0','R']):axs[2].fill_between(d.index,j,j+.7*l[p].held,step='post',color=colors[p],alpha=.75)
axs[2].set_yticks([.35,1.35],['E0 暴露90.9%','R 暴露14.1%']);axs[2].set_ylim(-.05,1.9);axs[2].text(.995,.96,'含开盘卖出日的当日暴露',transform=axs[2].transAxes,ha='right',va='top',fontsize=8,color='#63717c')
for p in s:axs[3].plot(l[p].index,l[p].nav,color=colors[p],lw=1.4,label=p+f' 净收益{l[p].nav.iloc[-1]-1:+.2%} / 最大回撤{-l[p].drawdown.min():.2%}')
axs[3].axhline(1,color='gray',ls=':',lw=.7);axs[3].set_ylabel('账户净值\n起始=1');axs[3].legend(fontsize=9,ncol=2,loc='upper left')
for ax in axs:ax.grid(alpha=.15)
axs[-1].xaxis.set_major_locator(mdates.YearLocator());axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'));fig.tight_layout();fig.savefig(R/'charts/gold-overview.png',dpi=150);plt.close(fig)

def candle(ax,z):
 for dt,b in z.iterrows():
  x=mdates.date2num(dt);color='#bd4d49' if b.close>=b.open else '#25816f';ax.vlines(x,b.low,b.high,color=color,lw=.8);height=max(abs(b.close-b.open),.0008);ax.add_patch(Rectangle((x-.32,min(b.open,b.close)),.64,height,facecolor=color,edgecolor=color,lw=.4))

def zoom(start,end,name,title,annotations):
 z=d.loc[start:end];fig,axs=plt.subplots(3,1,figsize=(14,8.5),sharex=True,gridspec_kw={'height_ratios':[3.4,1,1]});ax=axs[0];candle(ax,z)
 for p in ['E0','R']:
  line=s[p].floor if p=='E0' else s[p].exit_line;mask=s[p].target.astype(bool)|s[p].exited.astype(bool);ax.step(z.index,line.where(mask).reindex(z.index),where='post',color=colors[p],lw=1.4,label=p+('结构保护点' if p=='E0' else '2波幅保护线'))
  sel=t[p][pd.to_datetime(t[p].exit_date).between(z.index[0],z.index[-1])];xx=pd.to_datetime(sel.exit_date);ax.scatter(xx,d.close.reindex(xx),marker='x' if p=='R' else 'o',color=colors[p],s=65,label=p+'卖出',zorder=5)
 for text,day,xtext,ytext,color in annotations:
  ax.annotate(text,xy=(pd.Timestamp(day),d.loc[day,'close']),xytext=(pd.Timestamp(xtext),ytext),arrowprops={'arrowstyle':'->','color':color},bbox={'boxstyle':'round,pad=.35','fc':'white','ec':color,'alpha':.96},fontsize=10,color=color)
 ax.set_title(title,fontsize=14,pad=12);ax.set_ylabel('元 / 份');ax.legend(loc='upper left',ncol=2,fontsize=9)
 axs[1].bar(z.index,(f.q.reindex(z.index)).to_numpy(),width=.8,color='#adb5bd');axs[1].axhline(1,color='gray',ls=':',lw=.8);axs[1].set_ylabel('成交量 /\n前21日中位量')
 for j,p in enumerate(['E0','R']):axs[2].step(z.index,s[p].target.reindex(z.index)*.7+j,where='post',color=colors[p],lw=1.6)
 axs[2].set_yticks([.35,1.35],['E0 状态','R 状态']);axs[2].set_ylim(-.1,1.9);axs[2].set_ylabel('有 / 无资格')
 for ax in axs:ax.grid(alpha=.16)
 axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'));fig.autofmt_xdate();fig.tight_layout();fig.savefig(R/'charts'/name,dpi=145);plt.close(fig)
zoom('2024-08-12','2024-10-25','early-exit-2024.png','分歧起点：小幅回落触发R退出，原量价结构仍然存续',[
 ('9/4收盘：5.463\nR线5.473，E0支持5.327\n当日量仅为常态的0.68倍','2024-09-04','2024-08-15',5.70,colors['R']),
 ('10/11新向上事件\n确认低点5.640，支持上移\nE0没有“重新入场”，R仍不买','2024-10-11','2024-09-10',5.91,colors['E0'])])
zoom('2026-03-10','2026-06-30','decline-2026.png','反面复查：R在2026年这一笔退出更好，E0承受结构退出前的下跌',[
 ('同为3/25买入\nR于4/27退出：+1.44%','2026-04-27','2026-03-13',10.5,colors['R']),
 ('6/10收盘破结构支持\nE0于6/11卖出：−11.92%','2026-06-11','2026-05-05',9.45,colors['E0'])])
print('source charts ready; no fusion or new signal accounts')
