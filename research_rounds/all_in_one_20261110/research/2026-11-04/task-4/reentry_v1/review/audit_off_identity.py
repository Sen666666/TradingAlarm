from pathlib import Path
from decimal import Decimal,localcontext
from collections import Counter
import json,gzip,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1/funding_agent/private_projection');F=O.parent;R=F.parent/'review';D=Decimal
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=read(O/'INPUT_SOURCES_SHA256.json')
assert all(sha(p)==h for p,h in manifest.items())
s0={k[:10]:v['state'] for k,v in read(F/'PREOPEN_EXACT_STATE.json').items()}
pre={(x['at'][:10],x['intent']['sid'],x['intent']['role']):x for x in read(F/'PRE_CANDIDATE_EXACT_STATE.json')}
identity=read(O/'OFF_IDENTITY.json');completion=read(O/'COMPLETION.json')
root=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26/pair')
with gzip.open(root/'B.json.gz','rt') as f:book=json.load(f)
with gzip.open(root/'funding.jsonl.gz','rt') as f:funding=[json.loads(x) for x in f]
bydec={x['at'][:10]:x for x in book['decisions']};dates=sorted(s0)
assert len(dates)==13 and identity['passed'] and completion['passed'] and not completion['ON_started']
assert abs(completion['compute_seconds']+completion['remaining_OFF_ON_budget_seconds']-180)<1e-4
count=Counter();stocks=set();batch=[]
with localcontext() as ctx:
 ctx.prec=70
 for day in dates:
  previews=read(O/f'PREVIEWS_{day}.json');off=read(O/f'OFF_{day}.json');signal=previews[0]['clock']['session_date'];clock=day+' 09:30:00+08:00'
  originals=bydec[signal]['intents'];assert len(previews)==len(originals)
  assert [x['sid'] for x in previews]==[x['sid'] for x in originals]
  for p,x in zip(previews,originals):
   assert all(p[k]==v for k,v in x.items()),(day,x['sid'],'frozen intent differs')
   assert p['clock']['decision_at']==bydec[signal]['at'].replace(' ','T')
   assert p['clock']['earliest_execution_at']==clock.replace(' ','T')
   assert p['quote']['par_value']=='1'
   if p['role']=='mobile':assert p['CP1_trace']['receipt_id']==p['CP1_id'] and p['CP1_trace']['confirmed_day']==signal
   if (day,p['sid'],p['role']) in pre:assert p['preview']==pre[day,p['sid'],p['role']]['intent']['preview'];count['native_preview_targets']+=1
   stocks.add(p['sid'])
  digest=hashlib.sha256(json.dumps([s0[day],previews],sort_keys=True,ensure_ascii=False,default=str,allow_nan=False).encode()).hexdigest()
  assert digest==off['input_sha256'];assert off['inputs_unchanged'] and not off['native_Account_initializations'] and not off['real_fills'] and not off['new_financial_paths']
  expected=[{k:v for k,v in x.items() if k not in ['account','at']} for x in funding if x['at']==clock]
  actual=[x for x in off['attempts'] if not x.get('skip')]
  assert actual==expected,(day,'complete funding sequence')
  # Independently derive silent skip decisions from immutable S0 and ordered native successes.
  done=set();pending=set(s0[day]['pending_sells']);pending.update(v['stock'] for v in s0[day]['orders'].values() if v['qty']>0 and v['status'] in ['open','cancel_pending'])
  ordered=sorted(previews,key=lambda p:(p['rank'],p['role']!='core'))
  assert len(ordered)==len(off['attempts'])
  for p,a in zip(ordered,off['attempts']):
   assert (p['sid'],p['role'])==(a['sid'],a['role'])
   skip=p['sid'] in done or p['sid'] in pending;assert bool(a.get('skip'))==skip
   if a.get('result')=='reserved':done.add(p['sid'])
  assert len(done)==len(off['orders'])
  fees=D(0)
  for order in off['orders']:
   p=next(p for p in previews if p['sid']==order['sid'] and p['role']==order['role']);x=p['preview'];q=order['quantity'];price=D(order['price']);assert order['price']==x['price'] and order['floor']==x['floor']
   assert q>=x['minq'] and q<=x['maxq'] and (q-x['minq'])%x['rule']['buy_step']==0
   assert D(order['gross'])==D(q)*price and D(order['gross'])<=D(p['budget'])
   fee=D(0)
   for c in x['schedule']['components']:
    assert c['amount_basis']=='notional' and c['maximum_local'] is None and c['rounding_unit'] is None
    if c['side'] in ['both','buy']:fee+=max(D(q)*price*D(c['rate']),D(c['minimum_local']))
   assert fee==D(order['fee']);fees+=fee
   reserve=next(v for v in book['audit'] if v['kind']=='reserve' and v['at']==clock and v['sid']==order['sid'])
   assert D(reserve['gross_budget_cny'])==D(order['gross']) and D(reserve['fee_reserved_cny'])==fee
   native=next(v for v in expected if v['sid']==order['sid'] and v['role']==order['role'] and v['result']=='reserved')
   assert native['shares']==q and native['pool']==order['pool']
  assert fees==D(off['fees'])
  count.update(intents=len(previews),funding_records=len(expected),orders=len(off['orders']),skips=sum(x.get('skip',False) for x in off['attempts']))
  batch.append({'day':day,'intents':len(previews),'funding_records':len(expected),'orders':len(off['orders']),'skips':sum(x.get('skip',False) for x in off['attempts']),'full_input_digest_exact':True})
assert count['intents']==4172 and count['funding_records']==4164 and count['orders']==50 and count['skips']==8 and count['native_preview_targets']==15 and len(stocks)==1213
# Thin rebuild only uses private state and unchanged component; no native constructor or model rerun in its body.
source=(O/'rebuild_off.py').read_text();assert 'A.Runner(' not in source and 'J.Runner(' not in source and '.restore(' not in source
comp=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py').read_text()
for exact in ["NEW_MODEL=MODEL.replace(MG,'').replace(PG,PN)","NEW_ROUTE=ROUTE.replace(RG,RN)","ROUTES[remove_confirmed60](runner,a,i,x,at)"]:assert exact in comp
res={'status':'PASS_ON_PRIVATE_PROJECTION_ONLY','checked_source_files':len(manifest),'independent_counts':dict(count),'stocks':len(stocks),'OPENs':len(batch),'batches':batch,'remaining_private_OFF_ON_budget_seconds':completion['remaining_OFF_ON_budget_seconds'],'ON_scope':'One complete13-OPEN private reservation-only confirmed-min-first projection using the already frozen S0/PREVIEWS. Preserve probe full, full-target route comparison before confirmed truncation, fixed role/pool/receipt in topups, all retained guards and final fixed-plan replay. Stop at remaining131.579seconds or invalid-plan; no fallback.','excluded_scope':['No new Account or Runner','No restoration','No fills or financial path','No continuous account or return claim','No local-high or additional risk-cap overlay'],'independent_scope':'Reaggregated all original frozen intents, exact OPEN timestamp funding/skip sequence and original reserve gross/fees; independently recomputed all50 order fees and all13 complete S0+PREVIEWS input digests. All15 target previews directly matched prior exact snapshots. Did not rerun private OFF computation or original Runner.','new_accounts':0,'new_restores':0,'source_sha256':{str(O/n):sha(O/n) for n in ['COMPLETION.json','OFF_IDENTITY.json','rebuild_off.py','INPUT_SOURCES_SHA256.json']}}
(R/'PRIVATE_OFF_13OPEN_IDENTITY_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in res.items() if k not in ['source_sha256','batches']},ensure_ascii=False,indent=2))
