"""Saved financial-field equality before first scheduled D; no engine import."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import gzip,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def numeric(x):
 if isinstance(x,list):return [numeric(v) for v in x]
 if isinstance(x,dict):return {k:numeric(v) for k,v in x.items()}
 if isinstance(x,str):return D(x)
 return x
win='strong';run=T/'market_gross_admission_native_v1/full-strong-v1';binding_path=T/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json';control=read(binding_path)[win]
for p,h in control['source_sha256'].items():assert sha(p)==h
assert read(run/'DONE.json')['completed'] and read(run/'WINDOW_RESULT.json')['source_post_exact']
dp=run/'pair/daily.jsonl.gz';db=run/'pair/D_GROSS10.json.gz';bp=next(Path(p) for p in control['source_sha256'] if p.endswith('/pair/daily.jsonl.gz'));bb=next(Path(p) for p in control['source_sha256'] if p.endswith('/pair/B.json.gz'));clock=T/'market_gross_admission_native_v1/prepared/strong/MARKET_INFO_FULL_CLOCKS.json'
info=read(clock)['all_scheduled_OPEN_CLOSE'];first=min(r['at'] for r in info if r['state']=='DOWN');cutday=first[:10];Drows={r['at'][:10]:r for r in rows(dp)};Brows={r['at'][:10]:r for r in rows(bp)};assert list(Drows)==list(Brows)
prefix=[d for d in Drows if Drows[d]['at']<first];assert all(r['state']=='NOT_DOWN' for r in info if r['at']<first)
fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','on','positions','pool_probe','pool_confirmed','shared_loss'];mismatch=[];representation_only=[]
for d in prefix:
 for key in fields:
  x,y=Drows[d][key],Brows[d][key]
  if numeric(x)!=numeric(y):mismatch.append(dict(day=d,field=key,D=x,B=y))
  elif x!=y:representation_only.append(dict(day=d,field=key))
def trade_day(b):
 out=defaultdict(lambda:defaultdict(lambda:dict(fills=0,shares=0,gross=Z,fees=Z)))
 for tr in b['trades']:
  if tr['at']>=first:continue
  d=tr['at'][:10];k=(tr['security_id'],tr['side']);v=out[d][k];v['fills']+=1;v['shares']+=int(tr['shares']);v['gross']+=D(tr['gross_cny']);v['fees']+=D(tr['fees_cny'])
 return out
Dtrade=trade_day(book(db));Btrade=trade_day(book(bb))
for d in sorted(set(Dtrade)|set(Btrade)):
 if dict(Dtrade[d])!=dict(Btrade[d]):mismatch.append(dict(day=d,field='actual_sid_side_fillcount_qty_gross_fees',D={str(k):v for k,v in Dtrade[d].items()},B={str(k):v for k,v in Btrade[d].items()}))
res=dict(status='PASS_ND_PREFIX_ACTUAL_D_VS_ARCHIVED_B_FINANCIAL_EXACT' if not mismatch else 'FAIL_FIRST_FINANCIAL_DIFFERENCE',first_scheduled_D=first,completed_CLOSE_prefix_days=len(prefix),first_prefix_CLOSE=prefix[0],last_prefix_CLOSE=prefix[-1],all_preD_scheduled_events_NOT_DOWN=True,daily_fields_compared=fields,financial_numeric_equality='EXACT_DECIMAL_NO_EPS',representation_only_differences=representation_only,actual_fill_comparison='Each date×security×side fill count/shares/gross/fees before first scheduled D; labels, RID, order metadata deliberately excluded',actual_prefix_fill_count=sum(v['fills'] for d in Dtrade.values() for v in d.values()),mismatches=mismatch,first_mismatch=mismatch[0] if mismatch else None,source_sha256={str(p):sha(p) for p in [dp,db,bp,bb,clock,binding_path]},checker_sha256=sha(Path(__file__)),new_accounts=0,new_financial_models=0,scope='Financial-field archived-control no-op test only; not full-book metadata equality or candidate efficacy. First D is CLOSE Feb2, first D OPEN Feb3; prefix excludes first D CLOSE.')
(O/'STRONG_ND_PREFIX_FINANCIAL_EXACT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2,default=str)+'\n');print(res['status'],len(prefix),'fills',res['actual_prefix_fill_count'],'firstD',first,'sha',sha(O/'STRONG_ND_PREFIX_FINANCIAL_EXACT.json'),flush=True)
