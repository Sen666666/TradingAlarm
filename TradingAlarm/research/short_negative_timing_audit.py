"""Compare fast reversal timing to original sell decision, not its later execution."""
import json
from pathlib import Path
import pandas as pd
OUT=Path('results/shared-entry-path-audit')
e=pd.read_parquet(OUT/'episodes.parquet');z=pd.read_parquet('results/broad-exit-disagreement/all-observed-signals.parquet');orders=json.loads(Path('results/broad-shared-first-cross/group_gate_cap-base-orders.json').read_text());rows=[]
for x in e[e.model.eq('first_cross')].itertuples():
 sells=[o for o in orders if o['symbol']==x.symbol and o['units']<0 and x.entry<=o['date']<=x.exit];original=sells[0]['signal_date']
 p=z[z.symbol.eq(x.symbol)&z.date.ge(pd.Timestamp(x.entry))&z.date.lt(pd.Timestamp(original))];early=p[p.fast5.le(0)]
 rows.append(dict(kind=x.kind,strictly_earlier_short_negative=len(early)>0,pnl=x.pnl,first_negative=str(early.date.iloc[0].date()) if len(early) else None,original_sell_signal=original,symbol=x.symbol,entry=x.entry,exit=x.exit))
r=pd.DataFrame(rows);r.to_json(OUT/'short-negative-timing.json',orient='records',indent=2);summary=r.groupby('kind').agg(count=('pnl','size'),strictly_earlier_short_negative=('strictly_earlier_short_negative','sum'));summary.to_json(OUT/'short-negative-summary.json',orient='index',indent=2);print(summary.to_string())
