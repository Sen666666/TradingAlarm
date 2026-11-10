"""Audit mechanism and 2026 phase behavior without selecting new parameters."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from pairwise_trend_strength import pairwise_frame
from volume_clock_strength import volume_clock_frame
from volume_units import split_consistent_volume
from geometric_strength import strength_exposure
out=Path('results/strength-volume-clock'); rows=[]; checks=[]; curves=[]
etf,_=load_extended();hk,_=load_assets()
for group,assets in [('etf17',etf),('hk7',hk)]:
 for symbol,a in assets.items():
  valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index)
  c=a['signal'].close.reindex(valid);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid)
  old=pairwise_frame(c,v).strength;new=volume_clock_frame(c,v).strength
  good=old.notna()&new.notna(); flips=int(((old[good]<=5)!=(new[good]<=5)).sum())
  checks.append(dict(symbol=symbol,valid_bars=int(good.sum()),zero_threshold_disagreements=flips))
  for name,s in [('calendar',old),('volume_clock',new)]:
   exposure=strength_exposure(s)
   for phase,start,end in [('JanMay','2026-01-01','2026-05-31'),('June','2026-06-01','2026-06-30'),('JulOct','2026-07-01','2026-10-16')]:
    mask=(c.index>=start)&(c.index<=end);ix=np.flatnonzero(mask)
    if not len(ix):continue
    before=max(0,ix[0]-1)
    rows.append(dict(group=group,symbol=symbol,model=name,phase=phase,price_return=float(c.iloc[ix[-1]]/c.iloc[before]-1),mean_strength=float(s[mask].mean()),long_fraction=float(exposure[mask].mean()),entries=int((exposure.diff().gt(0)&mask).sum()),exits=int((exposure.diff().lt(0)&mask).sum())))
  if symbol=='USHJ512480':
   f=pd.DataFrame(dict(close=c,calendar=old,volume_clock=new,calendar_exposure=strength_exposure(old),volume_clock_exposure=strength_exposure(new))).loc['2026-01-01':'2026-10-16']; f.to_csv(out/'512480-2026-curve.csv'); curves.append(f)
pd.DataFrame(rows).to_csv(out/'phase-audit.csv',index=False)
assert sum(x['zero_threshold_disagreements'] for x in checks)==0
review=dict(checks=checks,conclusion='正分母变化不改变单条成对斜率的正负；在非精确中位数平分情形下，权重不变的加权中位数方向不变。因此成交量时钟主要改变强度幅度与入场，不能修复原模型方向转负过慢。精确半权重取相邻斜率平均是理论例外；本次24资产所有有效观测零阈值一致。',limits=['相同零阈值不保证两策略实际退出笔数相同，因为入场不同。','阶段是描述性分段，不宣称6月为每个资产真实拐点。','单个半导体ETF图为用户科技行情假设的示例，不代表全部科技板块。'])
(out/'phase-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
if curves:
 f=curves[0];fig,ax=plt.subplots(3,1,figsize=(12,8),sharex=True)
 ax[0].plot(f.index,f.close/f.close.iloc[0]);ax[0].set_ylabel('Normalized close');ax[0].set_title('512480 | 2026 development diagnostic')
 for name in ['calendar','volume_clock']:
  ax[1].plot(f.index,f[name],label=name);ax[2].step(f.index,f[name+'_exposure'],where='post',label=name,alpha=.7)
 ax[1].axhline(5,color='gray',ls='--');ax[1].axhline(5+5*np.tanh(1),color='gray',ls=':');ax[1].legend();ax[1].set_ylabel('Strength');ax[2].set_ylabel('Signal exposure')
 for a in ax:a.axvline(pd.Timestamp('2026-06-01'),color='gray',alpha=.4);a.grid(alpha=.15)
 fig.tight_layout();fig.savefig(out/'phase-2026.png',dpi=140);plt.close(fig)
print(json.dumps(dict(assets=len(checks),bars=sum(x['valid_bars'] for x in checks),zero_disagreements=sum(x['zero_threshold_disagreements'] for x in checks))))
print(pd.DataFrame(rows).query("symbol=='USHJ512480'").to_string(index=False))
