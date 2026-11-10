import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from strategy_signals import build_signals
OUT=Path('results/strength-symmetric-exit');assets,_=load_extended();models=json.loads((OUT/'protocol.json').read_text())['strategies'];rows=[]
for symbol in ['USHJ512480','HK03033']:
 a=assets[symbol];p=a['signal'].close;yy=p.loc['2026'];peak=yy.idxmax()
 for model in models:
  s=build_signals({symbol:a},model)[symbol];change=s.diff().loc['2026'];flat=s.loc[peak:].loc[lambda x:x.eq(0)]
  rows.append(dict(symbol=symbol,model=model,june_held=float(s.loc['2026-06'].mean()),held_at_peak=bool(s.loc[peak]),first_flat_after_peak=str(flat.index[0].date()) if len(flat) else None,peak_to_flat=float(p.loc[flat.index[0]]/p.loc[peak]-1) if len(flat) else None,signals=[dict(date=str(d.date()),side='enter' if change.loc[d]>0 else 'exit') for d in change.index[change.ne(0)]]))
(OUT/'phase-review.json').write_text(json.dumps(rows,indent=2));print(json.dumps([{k:v for k,v in r.items() if k!='signals'} for r in rows],indent=2))
