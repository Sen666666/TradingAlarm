"""Compare targets around observed 2026 peaks; signal dates are not fill dates."""
import json
from pathlib import Path
from hk_extension import load_extended
from strategy_signals import build_signals
OUT=Path('results/strength-pair-order')
a,_=load_extended();rows=[]
for symbol in ['USHJ512480','HK03033']:
    asset=a[symbol];close=asset['signal'].close;peak=close.loc['2026'].idxmax()
    for model in ['pairwise_price','pairwise_volume','pair_order_price','pair_order_volume']:
        signal=build_signals({symbol:asset},model)[symbol]
        flat=signal.loc[peak:].loc[lambda s:s.eq(0)]
        changes=signal.diff().loc['2026']
        rows.append(dict(symbol=symbol,model=model,peak=str(peak.date()),june_held=float(signal.loc['2026-06'].mean()),held_at_peak=bool(signal.loc[peak]),first_flat_after_peak=str(flat.index[0].date()) if len(flat) else None,peak_to_signal_close=float(close.loc[flat.index[0]]/close.loc[peak]-1) if len(flat) else None,changes=[dict(date=str(d.date()),side='enter' if changes.loc[d]>0 else 'exit') for d in changes.index[changes.ne(0)]]))
(OUT/'phase-review.json').write_text(json.dumps(rows,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='changes'} for r in rows],indent=2))
