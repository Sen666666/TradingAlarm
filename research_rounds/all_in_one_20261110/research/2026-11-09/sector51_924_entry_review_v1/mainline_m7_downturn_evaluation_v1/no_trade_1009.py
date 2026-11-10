"""Descriptive one-day buy-and-hold comparator. Not a strategy input or retuning exercise."""
import json,hashlib
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
R=Path(__file__).resolve().parent.parent;P=R/'mainline_m7_downturn_q0_split_v3/once_20241031';O=Path(__file__).resolve().parent/'mainline_m7_downturn_q0_split_v3__2024-10-09'
hs=json.loads((P/'HOLDINGS.json').read_text());old={}
for h in hs:
 if h['day']=='2024-10-08':old[h['sid']]=old.get(h['sid'],0)+h['qty']
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');m={x['symbol']:x for x in json.loads(mp.read_text())};rows=[];hashes={}
for s,q in sorted(old.items()):
 p=Path(next(p for p in m[s]['source_sha256'] if p.endswith('/signal.parquet')));h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m[s]['source_sha256'][str(p)];hashes[str(p)]=h
 z=pd.read_parquet(p);r=z.loc[pd.Timestamp('2024-10-09')];prev=z.loc[pd.Timestamp('2024-10-08')]
 assert r.observed_bar and r.price_eligible and not r.source_invalid and not r.synthetic_event_bar
 assert tuple(str(r[c]) for c in ['source_kind','source_path','segment_id'])==tuple(str(prev[c]) for c in ['source_kind','source_path','segment_id'])
 assert D(str(r.adjustment_factor))==D(str(prev.adjustment_factor)), 'Held corporate actions would require explicit comparator entitlement handling'
 rows.append(dict(sid=s,held_1008=q,mark_1009=str(r.raw_close),value=str(q*D(str(r.raw_close)))))
ll=json.loads((P/'DAY_LEDGER.json').read_text());a=next(x for x in ll if x['day']=='2024-10-08');b=ll[-1];bench=D(a['cash'])+D(a['receivable'])+sum(D(r['value']) for r in rows)
result=dict(anchor='2024-10-08',valuation='2024-10-09',cash_unchanged=a['cash'],receivable_unchanged=a['receivable'],no_trade_NAV=str(bench),no_trade_return_pct=str(100*(bench/D(a['NAV'])-1)),actual_NAV=b['NAV'],actual_minus_no_trade_NAV=str(D(b['NAV'])-bench),rows=rows,source_hashes=hashes,caveat='One-day passive continuation of the actual10/8 portfolio, not a tuned strategy or multi-day counterfactual. Actual NAV includes transaction fees and conditional OPEN5bp proxy; comparator makes no trades. No held source/factor change or entitlement on10/9.')
(O/'NO_TRADE_1009_COMPARATOR.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result['actual_minus_no_trade_NAV'])
