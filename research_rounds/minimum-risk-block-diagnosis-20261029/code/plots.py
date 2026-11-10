"""Historical prices stop at the rejected decision; no hypothetical executions."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];SNAP=ROOT/'TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared';CP=ROOT/'research_rounds/continuous-protection-lines-20261028/signals'
plt.rcParams['font.family']=['Arial Unicode MS','PingFang SC','DejaVu Sans']
def main():
 (O/'charts').mkdir(exist_ok=False);cases=pd.read_csv(O/'data/cases.csv')
 for sid,day,start in [('300308.SZ','2025-06-27','2025-03-20'),('688498.SH','2025-10-20','2025-08-01')]:
  case=cases[cases.symbol.eq(sid)&cases.date.eq(day)].iloc[0];f=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet').loc[start:day];signal=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet').reindex(f.index);cp=pd.read_parquet(CP/f'{sid}.parquet').reindex(f.index);factor=f.factor.iloc[-1];x=np.arange(len(f));cl=f.close/factor;floor=f.i_floor/factor
  fig,(ax,av)=plt.subplots(2,1,figsize=(15,8),gridspec_kw={'height_ratios':[4,1]},sharex=True,layout='constrained');ax.plot(x,cl,color='#273a48',lw=1.5,label='历史收盘');ax.plot(x,floor,color='#5071bb',lw=1.3,label='原 I/E0 结构保护');mask=cp.receipt.fillna(False);ax.scatter(x[mask],cp.loc[mask,'candidate']/factor,c='#c58c28',s=23,label='已有CP1候选（未改用）');ax.axhline(case.required_protection,c='#b44949',ls='--',lw=1.1,label=f'本次0.25%预算所需最低保护 {case.required_protection:.2f}（算术边界）');ax.scatter(x[-1],case.price,c='#111',s=38,zorder=6);ax.annotate(f'买点日收盘 {case.price:.2f}',(x[-1],case.price),(-160,18),textcoords='offset points',arrowprops={'arrowstyle':'->'});ax.fill_between(x,np.asarray(floor,float),np.asarray(cl,float),where=floor.notna(),color='#5071bb',alpha=.06);ax.set_title(f'{case["name"]} {sid}｜仅展示截至 {day} 的已知轨迹',loc='left');ax.set_ylabel('元，统一折算到买点日价格单位');ax.grid(alpha=.18);ax.legend(loc='upper left',fontsize=9)
  av.bar(x,signal.amount/1e8,color='#829298');av.set_ylabel('成交额/亿元');ticks=np.linspace(0,len(f)-1,8,dtype=int);av.set_xticks(ticks,[str(f.index[t].date()) for t in ticks]);av.grid(alpha=.12);fig.savefig(O/'charts'/f'{sid}-{day}.png',dpi=140);plt.close(fig)
 print('2 diagnostic figures; no account replay or future prices')
if __name__=='__main__':main()
