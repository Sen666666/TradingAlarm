from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,sys,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;F=Path(sys.argv[1]);read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();block=read(F/'UNCERTIFIED_DAY.json')
if block is None:print('NO_BLOCKED_DAY');sys.exit(0)
day=block['day'];last=read(F/'DAY_LEDGER.json')[-1]['day'];hs=[x for x in read(F/'HOLDINGS.json') if x['day']==last];held=defaultdict(int)
for h in hs:held[h['sid']]+=h['qty']
attempts={x['sid']:x for x in read(F/'ATTEMPTS.json') if x['final_qty']};pending={x['sid']:x for x in read(F/'PENDING_AT_END.json')};targets=sorted(set(held)|set(pending));U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');m={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};admitted={(x['sid'],x['ex_date']) for x in read(F/'EVENT_ADMISSION.json')};rows=[]
for s in targets:
 p=next(p for p in m[s]['source_sha256'] if p.endswith('/signal.parquet'));z=pd.read_parquet(p);t=pd.Timestamp(day);issues=[];old=attempts.get(s,pending.get(s));f0=D(old['factor']);origin=tuple(old['origin']);act=[x for x in read(AS/'inputs-v1/actions'/(s+'.json'))['events'] if x['effective_date']==day]
 if t not in z.index:issues.append('OPEN_MISSING');cur=None
 else:
  cur=z.loc[t];op=D(str(cur.raw_open));fn=D(str(cur.adjustment_factor));lin=tuple(str(cur[x]) for x in ['source_kind','source_path','segment_id'])
  if not op.is_finite() or op<=0:issues.append('OPEN_MISSING')
  if lin!=origin:issues.append('SOURCE_CHANGE')
  if not fn.is_finite() or fn<=0:issues.append('FACTOR_INVALID')
  elif abs(fn/f0-1)>D('1e-11') and (s,day) not in admitted:issues.append('UNADMITTED_FACTOR_CHANGE')
 if act and (s,day) not in admitted:issues.append('UNADMITTED_EQUITY_EVENT')
 rows.append(dict(day=day,sid=s,held_qty=held.get(s,0),pending_seed=s in pending,issues=issues))
bad=[x for x in rows if x['issues']];author=read(F.parent/'BLOCKED_DAY_ALL_ISSUES.json');normalize=lambda xs:{x['sid']:(x['held_qty'],x['pending_seed'],set(x['issues'])) for x in xs};equal=normalize(bad)==normalize(author);assert equal
rep=dict(status='PASS_INDEPENDENT_BLOCKED_TARGET_SCAN',certified_through=last,blocked_day=day,targets=len(targets),held_symbols=len(held),pending_seeds=len(pending),issues=bad,matches_implementation_full_scan=equal,scope='Read-only check of every held or pending next-OPEN target against raw quotes/source lineage/local actions and admitted-event keys. No allocation/fill strategy run.',meaning='A zero-entitlement pending seed still requires a verified factor/equity bridge before any allocation. A likely later cash rejection does not authorize bypassing preflight.',source_sha256={str(p):sha(p) for p in [Path(__file__),F/'ATTEMPTS.json',F/'PENDING_AT_END.json',F/'EVENT_ADMISSION.json',F.parent/'BLOCKED_DAY_ALL_ISSUES.json']});out=O/(F.parent.name+'_BLOCKED_TARGET_AUDIT.json');out.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rep,ensure_ascii=False,indent=2))
