import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import build_signals

OUT=Path('results/strength-range-close-control')
labels=pd.read_parquet('results/trend-first-passage-audit/labels-and-exposure.parquet')
etf,_=load_extended();hk,_=load_assets();rows=[];phases=[]
for group,assets in [('etf17',etf),('hk7',hk)]:
 for weighting in ['price','volume']:
  signals={kind:build_signals(assets,f'{kind}_direction_{weighting}') for kind in ['range','close']}
  for symbol,a in assets.items():
   source=labels.loc[labels.group.eq(group)&labels.symbol.eq(symbol)].copy();dates=pd.to_datetime(source.date)
   for kind in ['range','close']:source[kind]=signals[kind][symbol].reindex(dates).to_numpy()
   source['weighting']=weighting;rows.append(source[['group','symbol','date','year','label','range','close','weighting']])
   if symbol not in ['USHJ512480','HK03033']:continue
   valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);p=a['signal'].close.reindex(valid);yy=p.loc['2026'];peak=yy.idxmax()
   for kind in ['range','close']:
    s=signals[kind][symbol].reindex(valid);change=s.diff().reindex(yy.index).fillna(0);flat=s.loc[peak:].loc[lambda x:x.eq(0)]
    phases.append(dict(symbol=symbol,kind=kind,weighting=weighting,june_held=float(s.loc['2026-06'].mean()),held_at_peak=bool(s.loc[peak]),first_flat_after_peak=str(flat.index[0].date()) if len(flat) else None,peak_to_flat=float(p.loc[flat.index[0]]/p.loc[peak]-1) if len(flat) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit') for d in change.index[change.ne(0)]]))
f=pd.concat(rows,ignore_index=True);f.to_parquet(OUT/'paired-observations.parquet',index=False)
summary=f.groupby(['group','weighting','year','close','range']).label.agg(n='size',up_first=lambda x:int(x.eq('up_first').sum()),down_first=lambda x:int(x.eq('down_first').sum()))
summary['up_rate']=summary.up_first/summary.n;summary.to_csv(OUT/'conditional-paths.csv');(OUT/'phase-review.json').write_text(json.dumps(phases,indent=2))
print(summary.to_string())
