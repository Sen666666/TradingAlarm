"""Read-only V3 saved trace invariants and original-source joins; no state replay."""
from pathlib import Path
from collections import defaultdict
import ast,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent;F=O.parent;D=F/'signal_traces_v3/v3_all4';code=D.parent/'signal_trace.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
G=4*2**-53/(1-4*2**-53)
def cmp(a,b):
 a,b=float(a),float(b)
 return 0 if abs(a-b)<=G*max(a,b) else 1 if a>b else -1
def tor(a,b):return True if a is True or b is True else None if a is None or b is None else False
def body(p):
 f=next(x for x in ast.parse(Path(p).read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='compare');b=f.body
 if b and isinstance(b[0],ast.Expr) and isinstance(b[0].value,ast.Constant) and isinstance(b[0].value.value,str):b=b[1:]
 return ast.dump(ast.Module(body=b,type_ignores=[]),include_attributes=False)
receipt=json.loads((D/'RUN_RECEIPT.json').read_text());S=receipt['source_sha256'].copy()
for p,h in S.items():assert sha(p)==h,p
numeric=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py');assert body(code)==body(numeric)
rows=json.loads((D/'ALL_DAILY_TRACES.json').read_text());prefix=json.loads((D/'PREFIX_CHECKS.json').read_text())
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');m={r['symbol']:r for r in json.loads(SM.read_text())}
by=defaultdict(list)
for r in rows:by[r['sid']].append(r)
counts=defaultdict(int);unique=set();witness=[]
for sid,rr in by.items():
 sp=next(Path(x) for x in m[sid]['source_sha256'] if x.endswith('/signal.parquet'));ep=next(Path(x) for x in m[sid]['source_sha256'] if x.endswith('/events.parquet'))
 assert sha(sp)==S[str(sp)]==m[sid]['source_sha256'][str(sp)];assert sha(ep)==S[str(ep)]==m[sid]['source_sha256'][str(ep)]
 pf=pd.read_parquet(sp);ef=pd.read_parquet(ep);last=None
 for r in rr:
  d=r['day'];t=pd.Timestamp(d);p=pf.loc[t];e=ef.loc[t];b=r['before_CLOSE'];n=r['new_confirmed_pivot'];old=r['P_old'];new=r['P_new']
  assert r['C']==float(p.close) and r['raw_C']==float(p.raw_close) and r['original_E0_event']==int(e.event)
  points=[]
  def walk(x):
   if isinstance(x,dict):
    if 'source_event_id' in x and 'price_adjusted' in x:points.append(x)
    for y in x.values():walk(y)
   elif isinstance(x,list):
    for y in x:walk(y)
  walk(r)
  for q in points:
   assert q['pivot_day']<=q['confirmed_at']<=d
   z=ef.loc[pd.Timestamp(q['confirmed_at'])]
   assert q['price_adjusted']==float(z.confirmed_pivot_price) and q['pivot_day']==str(z.confirmed_pivot_date)[:10]
   assert q['event']==int(z.event) and q['source_segment']==str(int(z.segment_id))
   unique.add((sid,q['source_event_id']))
  if not r['source_segment_changed']:assert old==b['P']
  hit=bool(not r['source_segment_changed'] and b['active'] and r['price_close_valid'] and cmp(r['C'],old)<=0)
  assert hit==bool(r['support_exit_events'])
  if hit:
   counts['support_exits']+=1
   for x in r['support_exit_events']:assert x['P_old']==old and x['R_preserved']==b['R'] and x['recovery_cycle_preserved']==b['recovery_cycle']
  if r['launch_event']:
   counts['launches']+=1;assert n['event']==1 and new==n['price_adjusted'] and r['generation']==b['generation']+1
  elif r['active_generation']:
   expected=old
   if n is not None and n['event']==1 and cmp(n['price_adjusted'],old)>0:expected=n['price_adjusted']
   assert new==expected and r['generation']==b['generation']
  if r['P_update_event']:counts['P_raises']+=1;assert new>old and n['event']==1
  if r['down_event']:
   counts['downs']+=1;assert n['event']==-1 and r['R']==n and r['recovery_cycle']==b['recovery_cycle']+1 and r['up_after_R'] is False and r['B_base'] is False and r['I_expand'] is False
   assert r['revoke_event']['kind']=='down_event_retracts_maturity'
   if b['R'] and cmp(n['price_adjusted'],b['R']['price_adjusted'])<0:counts['R_replaced_by_lower_confirmed_high']+=1
  elif not r['source_segment_changed']:
   assert r['R']==b['R'] and r['recovery_cycle']==b['recovery_cycle']
  assert bool(r['trial_event'])==(n is not None and n['event']==1)
  if r['trial_event']:counts['trials']+=1;assert r['up_after_R'] is True
  if r['B_base'] is True:
   L,H,L2=r['L1'],r['H12'],r['L2'];assert L and H and L2 and cmp(L2['price_adjusted'],L['price_adjusted'])>0
   assert L['pivot_day']<H['pivot_day']<L2['pivot_day'] and H['confirmed_at']<L2['confirmed_at']<=d
   seq=ef.loc[(ef.index<=pd.Timestamp(L2['confirmed_at']))&ef.event.ne(0)&ef.segment_id.eq(int(r['source_segment']))].tail(3)
   assert list(seq.event)==[1,-1,1] and [str(x.date()) for x in seq.index]==[L['confirmed_at'],H['confirmed_at'],L2['confirmed_at']]
   assert H==r['R'];counts['HL_valid_rows']+=1
  latest=ef.loc[(ef.index<=t)&ef.event.eq(-1)&ef.segment_id.eq(int(r['source_segment']))]
  if r['R'] is not None:assert r['R']['confirmed_at']==str(latest.index[-1].date())
  valid=r['price_close_valid']
  if not valid:assert r['I_hold'] is None and r['I_expand'] is None
  elif not r['active_generation'] or not r['up_after_R']:
   known=False if r['original_event_ready'] else None
   assert r['A_active']==r['B_active']==known
   assert r['I_hold']==(True if r['active_generation'] else known)
  else:
   assert r['I_hold'] is True
   A=None if r['R'] is None or r['R']['confirmed_at']>=d else cmp(r['C'],r['R']['price_adjusted'])>0
   B=None if r['B_base'] is None else False if r['B_base'] is False else cmp(r['C'],r['H12']['price_adjusted'])>0
   assert A==r['A_active'] and B==r['B_active']
  assert r['I_expand']==tor(r['A_active'],r['B_active'])
  assert not (r['B_active'] is True and r['A_active'] is not True)
  counts['B_true_rows']+=r['B_active'] is True
  if r['confirm_event']:counts['confirms']+=1;assert r['I_expand'] is True
  if r['support_exit_events'] and r['launch_event']:counts['same_close_exit_new_START']+=1
  if last and last['source_segment']==r['source_segment']:
   assert r['effective_CLOSE_observation_index']==last['effective_CLOSE_observation_index']+int(valid)
  last=r
assert len(rows)==1026 and len(by)==4 and len(prefix)==8 and all(x['prefix_exact'] for x in prefix)
for sid in by:assert sum(x['sid']==sid for x in prefix)==2
fixed={'000620.SZ':['2022-01-17','2022-01-20','2022-01-21','2022-01-24','2022-01-26','2022-02-07'],'002583.SZ':['2024-09-27','2024-09-30','2024-10-10','2024-10-11','2024-11-04','2024-11-25','2024-11-26'],'601019.SH':['2023-02-10'],'601601.SH':['2024-09-18']}
for sid,ds in fixed.items():
 for d in ds:
  r=next(x for x in by[sid] if x['day']==d);witness.append({k:r[k] for k in ['sid','day','C','raw_C','mode','generation','recovery_cycle','P_old','P_new','R','up_after_R','A_active','B_active','I_hold','I_expand','down_event','trial_event','support_exit_events','confirm_event']})
for p in [D/'RUN_RECEIPT.json',D/'ALL_DAILY_TRACES.json',D/'PREFIX_CHECKS.json',code,F/'SIGNAL_FREEZE_V3.md',Path(__file__)]:S[str(p.resolve())]=sha(p)
result={'status':'PASS_V3_SAVED_CORE_TRACE_WITH_SCOPE_LIMITS','remaining_core_blocks':[],'display_rows':len(rows),'stocks':len(by),'original_source_price_event_rows_verified':len(rows),'unique_pivots_source_verified':len(unique),'counts':dict(counts),'B_true_A_not_true_rows':0,'producer_physical_prefix_receipts_read_not_rerun':8,'compare_body_AST_equal_to_numeric':True,'key_witnesses':witness,'source_sha256':S,'limits':['No second state engine or new price-path tests.','Prefix-exact assertions read from owner actual truncation receipts, not rerun by reviewer.','Recovery-cycle aggregation and original-entry JOIN are separate pending outputs.','Unknown/source-switch branches not broadly exercised by fixed display.','No account, CP recomputation, economic-effect or execution validation.'],'new_accounts':0,'new_backtests':0,'reviewer_trace_or_model_calls':0}
(O/'V3_SAVED_CORE_TRACE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','display_rows','unique_pivots_source_verified','counts','B_true_A_not_true_rows']},ensure_ascii=False))
