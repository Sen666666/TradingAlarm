import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from strategy_signals import build_signals
from pairwise_trend_strength import pairwise_frame
from volume_units import split_consistent_volume
OUT=Path('results/strength-uniform-pairwise')
a,_=load_extended();a={s:a[s] for s in ['USHJ512480','HK03033']};rows=[]
fig,axes=plt.subplots(2,1,figsize=(12,7))
for axis,(s,asset) in zip(axes,a.items()):
 p=asset['signal'].close;year=p.loc['2026'];peak=year.idxmax();axis.plot(year.index,year/year.iloc[0]*100,color='black',label='Price (start=100)')
 twin=axis.twinx()
 for model in ['pairwise_price','pairwise_volume','uniform_pairwise_price','uniform_pairwise_volume']:
  signal=build_signals({s:asset},model)[s];change=signal.diff().loc['2026'];flat=signal.loc[peak:].loc[lambda x:x.eq(0)]
  rows.append(dict(symbol=s,model=model,june_held=float(signal.loc['2026-06'].mean()),held_at_peak=bool(signal.loc[peak]),first_flat_after_peak=str(flat.index[0].date()) if len(flat) else None,peak_to_flat=float(p.loc[flat.index[0]]/p.loc[peak]-1) if len(flat) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit') for d in change.index[change.ne(0)]]))
  if 'pairwise' in model:
   v=split_consistent_volume(asset['raw'].volume,asset.get('splits',[]));score=pairwise_frame(p,v,joint=model.endswith('volume'),recency=not model.startswith('uniform_')).strength.loc['2026'];twin.plot(score.index,score,label=model,alpha=.8)
 twin.axhline(5,color='gray',ls=':');twin.set_ylim(0,10);twin.set_ylabel('Trend strength');twin.legend(loc='upper right');axis.set_title(s+' / 2026 development review');axis.set_ylabel('Adjusted price index')
fig.tight_layout();fig.savefig(OUT/'2026-review.png',dpi=150);plt.close(fig)
(OUT/'phase-review.json').write_text(json.dumps(rows,indent=2));print(json.dumps([{k:v for k,v in r.items() if k!='signals'} for r in rows],indent=2))
