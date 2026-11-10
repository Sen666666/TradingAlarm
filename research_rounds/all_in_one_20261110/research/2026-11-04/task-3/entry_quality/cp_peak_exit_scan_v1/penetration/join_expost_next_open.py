"""Append ex-post raw next-market-OPEN observations to saved rows. No signals/run."""
from pathlib import Path
from decimal import Decimal as D
import csv,gzip,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,D):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def writecsv(n,rows):
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
inputfile=O/'MOBILE_DAILY_PENETRATION.json';before=sha(inputfile);data=json.loads(inputfile.read_text())
oldkeys={id(x):dict(x['summary']) for x in data}
dp=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/daily.jsonl.gz'
with gzip.open(dp,'rt') as f:daily=[json.loads(s) for s in f]
mp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';manifest={r['symbol']:r for r in json.loads(mp.read_text())}
src={str(dp.resolve()):sha(dp),str(mp.resolve()):sha(mp)};bars={}
for sid in {x['summary']['sid'] for x in data}:
 m=manifest[sid];p=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(p)==m['source_sha256'][str(p)];src[str(p)]=sha(p);bars[sid]=pd.read_parquet(p)
known=0;unknown=0
for x in data:
 r=x['summary'];assert not any(k.startswith('expost_') for k in r)
 at=r['daily_index'];nd=None if at+1>=len(daily) else daily[at+1]['at'][:10];df=bars[r['sid']]
 z=dict(expost_evaluation_only_not_input=True,expost_next_market_day=nd,expost_next_raw_OPEN=None,expost_next_sell_5bp_price_reference=None,expost_next_raw_CLOSE=None,expost_next_factor=None,expost_next_segment_id=None,expost_next_OPEN_over_current_CLOSE_minus1=None,expost_next_quote_status='UNKNOWN_MISSING_EXACT_NEXT_BAR')
 if nd is not None and pd.Timestamp(nd) in df.index:
  b=df.loc[pd.Timestamp(nd)];cur=df.loc[pd.Timestamp(r['day'])];op=b.get('raw_open');cl=b.get('raw_close');factor=b.get('adjustment_factor');seg=b.get('segment_id')
  z.update(expost_next_raw_OPEN=op,expost_next_raw_CLOSE=cl,expost_next_factor=factor,expost_next_segment_id=seg)
  valid=op is not None and math.isfinite(float(op)) and float(op)>0 and bool(b.get('price_eligible',False)) and bool(b.get('observed_bar',False)) and not bool(b.get('source_invalid',True)) and not bool(b.get('synthetic_event_bar',True))
  same=valid and D(str(factor))==D(str(r['current_factor'])) and seg==cur.get('segment_id') and r['domain_status']=='KNOWN_SAME_RAW_UNIT_AND_EXACT_OBSERVATIONS'
  if valid:z['expost_next_sell_5bp_price_reference']=D(str(op))*D('.9995')
  z['expost_next_quote_status']='KNOWN_EXACT_BAR_SAME_PRICE_UNIT' if same else 'UNKNOWN_PRICE_VALIDITY_OR_CA_UNIT_OR_SOURCE_SEGMENT'
  if same:z['expost_next_OPEN_over_current_CLOSE_minus1']=D(str(op))/D(str(r['C_raw']))-1
 if z['expost_next_quote_status']=='KNOWN_EXACT_BAR_SAME_PRICE_UNIT':known+=1
 else:unknown+=1
 r.update(clean(z));assert all(r[k]==v for k,v in oldkeys[id(x)].items())
 x['expost_evaluation_scope']='These next-session source observations are labels known afterward only. O*.9995 is an arithmetic reference, not a feasible quantity/fill/ACK/capacity/cash assessment. No original trigger/provenance calculation reads them.'
rows=[x['summary'] for x in data];cross=[r for r in rows if r['actual_first_CP_request_today']]
save('MOBILE_DAILY_PENETRATION.json',data);writecsv('MOBILE_DAILY_PENETRATION.csv',rows)
save('ACTUAL_FIRST_CP_TRIGGER_POINTS.json',cross);writecsv('ACTUAL_FIRST_CP_TRIGGER_POINTS.csv',cross)
save('EXPOST_NEXT_OPEN_JOIN_RECEIPT.json',dict(status='PASS_SOURCE_JOIN_ONLY_EXISTING_FIELDS_UNCHANGED',before_main_sha256=before,after_main_sha256=sha(inputfile),script_sha256=sha(Path(__file__)),source_sha256=src,rows=len(rows),known_next_bars=known,unknown_next_bars=unknown,scope='Evaluation labels only; no Account/window/fee/capacity calls, no signal inputs, no new exit rule or PnL.',new_accounts=0,new_models=0,new_backtests=0,new_indicators=0))
print(json.dumps(dict(rows=len(rows),known=known,unknown=unknown),ensure_ascii=False))
