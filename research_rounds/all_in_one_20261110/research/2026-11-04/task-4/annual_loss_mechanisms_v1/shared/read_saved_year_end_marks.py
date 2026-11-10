"""Saved facts raw prices and saved quantities, no strategy/native modules."""
from pathlib import Path
from decimal import Decimal as D
import gzip,json,hashlib,pandas as pd
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
B=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
m={r['symbol']:r for r in json.loads(bind(M).read_text())}
with gzip.open(bind(B/'daily.jsonl.gz'),'rt')as f:daily=[json.loads(x)for x in f]
a=next(x for x in daily if x['at'][:10]=='2022-12-30')
rows=[]
for sid,q in a['positions'].items():
 p=bind(m[sid]['refs']['facts']);f=pd.read_parquet(p,columns=['raw_close','factor'])
 r=f.loc['2022-12-30'];price=D(str(r['raw_close']))
 rows.append(dict(sid=sid,date='2022-12-30',saved_shares=q,saved_facts_raw_close=str(price),saved_factor=str(r['factor']),inventory=str(D(q)*price),same_day_facts_row=True,source=str(p)))
total=sum((D(r['inventory'])for r in rows),D(0));residual=total-D(a['inventory'])
assert residual==0,(str(total),a['inventory'],str(residual))
result={'status':'EXACT_SAVED_FACTS_SAME_DAY_RAW_PRICE_ANCHOR','date':'2022-12-30','stocks':len(rows),'inventory_from_saved_raw_prices':str(total),'original_inventory':a['inventory'],'residual':str(residual),'rows':rows,'no_native_or_account_import':True,'execution_claim':False}
(O/'END2022_STOCK_INVENTORY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(O/'ANCHOR_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k!='rows'},ensure_ascii=False))
