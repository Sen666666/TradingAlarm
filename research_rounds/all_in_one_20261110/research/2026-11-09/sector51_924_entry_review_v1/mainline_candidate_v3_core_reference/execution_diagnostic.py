from pathlib import Path
import json,hashlib
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent;P=O/'once_20241008';R=O.parent
read=lambda p:json.loads(p.read_text())
manifest={r['symbol']:r for r in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
orders=read(P/'ORDERS.json');cache={};rows=[]
for t in orders:
 if not t['side'].startswith('BUY') or t['day'] not in ['2024-09-23','2024-09-27','2024-09-30','2024-10-08']:continue
 s=t['sid']
 if s not in cache:
  p=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==manifest[s]['source_sha256'][p];cache[s]=pd.read_parquet(p)
 z=cache[s];dt=pd.Timestamp(t['day']);a=z.loc[dt];before=z[z.index<dt];prev=before.iloc[-1] if len(before) else None
 same=len(before)>0 and all(str(a[c])==str(prev[c]) for c in ['source_kind','source_path','segment_id'])
 one=all(pd.notna(a[c]) for c in ['raw_open','raw_high','raw_low','raw_close']) and len({D(str(a[c])) for c in ['raw_open','raw_high','raw_low','raw_close']})==1
 row=dict(**t,raw_OPEN=str(a.raw_open),raw_HIGH=str(a.raw_high),raw_LOW=str(a.raw_low),raw_CLOSE=str(a.raw_close),previous_observed_close=str(prev.raw_close) if prev is not None else None,previous_observed_day=str(before.index[-1].date()) if len(before) else None,same_source_previous=bool(same),all_day_one_price=bool(one),proxy_buy_above_day_high=bool(pd.notna(a.raw_high) and D(t['price'])>D(str(a.raw_high))),diagnostic_only_future_HLC_not_used_for_OPEN_decision=True,conditional_execution_not_certified=True)
 rows.append(row)
(O/'EXECUTION_DIAGNOSTICS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(rows).to_csv(O/'EXECUTION_DIAGNOSTICS.csv',index=False)
print(json.dumps([r for r in rows if r['sector51']=='半导体'],ensure_ascii=False));print('COUNTS',len(rows),sum(r['all_day_one_price'] for r in rows),sum(r['proxy_buy_above_day_high'] for r in rows))
