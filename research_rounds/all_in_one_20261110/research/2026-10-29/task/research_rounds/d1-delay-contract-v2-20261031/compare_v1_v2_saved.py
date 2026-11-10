"""Compare saved economic/event outputs only; never initialize/replay a runner."""
from pathlib import Path
import json,gzip,sys,hashlib
O=Path(__file__).resolve().parent;OLD=O.parent/'d1-delay-contract-20261031'
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'));from initialization_guard import IO
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
result=[]
for ref in ('B3','B_diag'):
 a=OLD/'runs'/ref;b=O/'runs'/ref
 if not (b/'DONE.json').exists():continue
 left=obj(a/'pair/B.json.gz');right=obj(b/'pair/B.json.gz');books={k:left[k]==right[k] for k in left.keys()|right.keys()}
 events={};examples={}
 for n in ('daily','funding','opportunities','balances','industry'):
  aa=rows(a/'pair'/(n+'.jsonl.gz'));bb=rows(b/'pair'/(n+'.jsonl.gz'));events[n]=aa==bb
  if aa!=bb:
   first=next((i for i in range(min(len(aa),len(bb))) if aa[i]!=bb[i]),min(len(aa),len(bb)))
   examples[n]=dict(old_length=len(aa),new_length=len(bb),first_array_index=first,old=aa[first] if first<len(aa) else None,new=bb[first] if first<len(bb) else None)
 result.append(dict(reference=ref,old_source_sha256='2ea0c86607bde44c613e0439850a497d8c0dc8e67144d136d7b1d0150fe361ce',new_source_sha256=hashlib.sha256((O/'d1_runner.py').read_bytes()).hexdigest(),economic_book_field_equality=books,all_economic_book_fields_equal=all(books.values()),event_stream_equality=events,first_event_differences=examples,trades_fingerprint_v1=digest(left['trades']),trades_fingerprint_v2=digest(right['trades']),old_ending_NAV=left['ending_NAV'],new_ending_NAV=right['ending_NAV'],new_execution_repair_not_parameter_selection=True))
IO.write_json(O/'V1_V2_ECONOMIC_COMPARISON.json',result)
for x in result:print(x['reference'],'book_equal',x['all_economic_book_fields_equal'],'events',x['event_stream_equality'],'NAV',x['new_ending_NAV'])
