"""Raw observations only; no portfolio replay or parameter search."""
from pathlib import Path
import json, hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
SNAP=ROOT/'TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared'
CP=ROOT/'research_rounds/continuous-protection-lines-20261028/signals'
CASES=['601869.SH','300502.SZ','300308.SZ','688498.SH','688048.SH','688256.SH','002987.SZ','002439.SZ','688041.SH']
plt.rcParams['font.family']=['Arial Unicode MS','PingFang SC','DejaVu Sans']
def main():
 names=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').name
 (O/'charts').mkdir(parents=True,exist_ok=True);records=[]
 for j in range(3):
  fig,axs=plt.subplots(6,1,figsize=(18,14),gridspec_kw={'height_ratios':[3,1]*3},layout='constrained')
  for k,sid in enumerate(CASES[j*3:j*3+3]):
   f=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet').loc['2024-01-01':'2026-10-27'];z=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet').reindex(f.index);c=pd.read_parquet(CP/f'{sid}.parquet').reindex(f.index)
   f=f.loc[f.observed_bar & f.price_eligible & ~f.synthetic_event_bar];z=z.reindex(f.index);c=c.reindex(f.index);x=np.arange(len(f));ax=axs[2*k];av=axs[2*k+1]
   # Signals carry causal OHLC; divide by the same-day causal unit factor to show raw exchange prices.
   factor=z.factor.to_numpy();op=f.open.to_numpy()/factor;cl=f.close.to_numpy()/factor;hi=f.high.to_numpy()/factor;lo=f.low.to_numpy()/factor
   # Prefer explicit raw columns when present, and assert raw close consistency.
   assert np.allclose(cl,z.raw_close,rtol=1e-10)
   colors=np.where(cl>=op,'#c83d48','#248268');ax.add_collection(LineCollection([[(t,a),(t,b)] for t,a,b in zip(x,lo,hi)],colors=colors,linewidths=.45))
   ax.vlines(x,op,cl,colors=colors,linewidth=1.25)
   mask=c.receipt.fillna(False).to_numpy(bool)
   ax.autoscale_view();ax.set_title(f'{names[sid]} {sid}｜先看原始日K与成交金额；未叠策略/未运行新账户',loc='left');ax.set_ylabel('未复权价格 / 元');ax.grid(alpha=.15)
   av.bar(x,f.amount/1e8,color=colors,width=.8);av.set_ylabel('成交额/亿元');ticks=np.linspace(0,len(f)-1,8,dtype=int);av.set_xticks(ticks,[str(f.index[t].date()) for t in ticks],fontsize=8);ax.set_xticks([])
   records.append({'symbol':sid,'name':names[sid],'rows':len(f),'cp_receipts':int(mask.sum()),'i_buy_days':int(z.i_buy.sum()),'raw_close_check':True})
  fig.savefig(O/'charts'/f'raw-{j+1}.png',dpi=135);plt.close(fig)
 (O/'RAW_FACTS.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
 print(json.dumps(records,ensure_ascii=False))
if __name__=='__main__':main()
