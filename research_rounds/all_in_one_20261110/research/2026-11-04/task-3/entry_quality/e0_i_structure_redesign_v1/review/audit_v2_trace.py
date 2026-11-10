"""Read existing V2 trace/source only. No trace/model/account import or replay."""
from pathlib import Path
from collections import defaultdict
import argparse,ast,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent;F=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
G=(4*(2**-53))/(1-4*(2**-53))
def cmp(a,b):
 a,b=float(a),float(b)
 return 0 if abs(a-b)<=G*max(a,b) else 1 if a>b else -1
def maximum(points):
 p=None
 for q in points:
  if p is None or cmp(q['price_adjusted'],p['price_adjusted'])>0:p=q
 return p
def tor(a,b):return True if a is True or b is True else None if a is None or b is None else False
def body(fn,name):
 f=next(x for x in ast.parse(Path(fn).read_text()).body if isinstance(x,ast.FunctionDef) and x.name==name)
 b=f.body
 if b and isinstance(b[0],ast.Expr) and isinstance(b[0].value,ast.Constant) and isinstance(b[0].value.value,str):b=b[1:]
 return ast.dump(ast.Module(body=b,type_ignores=[]),include_attributes=False)
p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args();D=a.directory
R=json.loads((D/'RUN_RECEIPT.json').read_text());code=F/'signal_traces/signal_trace.py';numeric=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py')
assert body(code,'compare')==body(numeric,'compare')
S={}
for path,h in R['source_sha256'].items():assert sha(path)==h,path;S[path]=h
assert str(code.resolve()) in S or str(code) in S
rows=json.loads((D/'ALL_DAILY_TRACES.json').read_text());checks=json.loads((D/'PREFIX_CHECKS.json').read_text())
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in json.loads(SM.read_text())}
by=defaultdict(list)
for r in rows:by[r['sid']].append(r)
prices={};events={};seen_points=set();all_points=[];adjacent_checks=0;exits=0;launches=0;lh=0;updates=0;same_day_exit_start=0
for sid,rr in by.items():
 m=manifest[sid];sp=next(Path(x) for x in m['source_sha256'] if x.endswith('/signal.parquet'));ep=next(Path(x) for x in m['source_sha256'] if x.endswith('/events.parquet'))
 assert sha(sp)==m['source_sha256'][str(sp)]==S[str(sp)];assert sha(ep)==m['source_sha256'][str(ep)]==S[str(ep)]
 pf=pd.read_parquet(sp);ef=pd.read_parquet(ep);prices[sid]=pf;events[sid]=ef
 assert [r['day'] for r in rr]==sorted(r['day'] for r in rr)
 for r in rr:
  day=r['day'];t=pd.Timestamp(day);orig=pf.loc[t];ev=ef.loc[t] if t in ef.index else None
  assert float(orig.close)==r['C']
  assert ev is not None and int(ev.event)==r['original_E0_event']
  points=[]
  def walk(x):
   if isinstance(x,dict):
    if 'price_adjusted' in x and 'confirmed_at' in x and 'source_event_id' in x:points.append(x)
    for y in x.values():walk(y)
   elif isinstance(x,list):
    for y in x:walk(y)
  walk(r)
  for q in points:
   assert q['pivot_day']<=q['confirmed_at']<=day
   e=ef.loc[pd.Timestamp(q['confirmed_at'])]
   assert float(e.confirmed_pivot_price)==q['price_adjusted'] and int(e.event)==q['event']
   assert str(e.confirmed_pivot_date)[:10]==q['pivot_day'] and str(int(e.segment_id))==q['source_segment']
   if (sid,q['source_event_id']) not in seen_points:seen_points.add((sid,q['source_event_id']));all_points.append(dict(sid=sid,**q))
  b=r['before_CLOSE'];old=r['P_old'];new=r['P_new'];n=r['new_confirmed_pivot'];valid=r['price_close_valid']
  if not r['source_segment_changed']:assert old==b['P']
  expected_exit=bool(b['active'] and not r['source_segment_changed'] and valid and cmp(r['C'],old)<=0)
  assert bool(r['support_exit_events'])==expected_exit
  if expected_exit:
   exits+=1
   for e in r['support_exit_events']:assert e['P_old']==old and e['generation']==b['generation'] and e['at']==day
  if r['launch_event']:
   launches+=1;assert n is not None and n['event']==1 and r['start_at']==day and r['active_generation']
   assert r['generation']==b['generation']+1 and new==n['price_adjusted']
   ini=r['initial_KA'];hs=ef.loc[(ef.index<t)&ef.event.eq(-1)&ef.segment_id.eq(int(r['source_segment']))].tail(2)
   assert len(hs)==len(ini['components'])
   assert [str(x.date()) for x in hs.index]==[x['confirmed_at'] for x in ini['components']]
   assert maximum(ini['components'])==ini['selected']
  elif r['active_generation']:
   assert not expected_exit and r['generation']==b['generation']
   expected=old
   if n is not None and n['event']==1 and cmp(n['price_adjusted'],old)>0:expected=n['price_adjusted']
   assert new==expected
  if r['support_exit_events'] and r['launch_event']:same_day_exit_start+=1
  if r['P_update_event']:updates+=1;assert new>old and n['event']==1 and r['P_source']==n
  if r['B_base'] is True:
   L1,H,L2=r['L1'],r['H12'],r['L2'];assert L1 and H and L2
   assert L1['pivot_day']<H['pivot_day']<L2['pivot_day'] and H['confirmed_at']<L2['confirmed_at']<=day and cmp(L2['price_adjusted'],L1['price_adjusted'])>0
   seq=ef.loc[(ef.index<=pd.Timestamp(L2['confirmed_at']))&ef.event.ne(0)&ef.segment_id.eq(int(r['source_segment']))].tail(3)
   assert list(seq.event)==[1,-1,1] and [str(x.date()) for x in seq.index]==[L1['confirmed_at'],H['confirmed_at'],L2['confirmed_at']]
   adjacent_checks+=1
  for rev in r['KA_revision_history']:
   assert rev['at']<=day and rev['H_previous']['confirmed_at']<rev['at'] and rev['H_new']['confirmed_at']==rev['at']
   assert cmp(rev['H_new']['price_adjusted'],rev['H_previous']['price_adjusted'])<0
   assert maximum([q for q in [rev['old_KA'],rev['H_previous']] if q is not None])==rev['new_KA']
  de=r['lower_high_or_equal_event']
  if de and de['kind']=='lower_high_repair':lh+=1;assert r['B_base'] is False and r['current_KA']==de['new_KA']
  if not valid:assert r['I_hold'] is None and r['I_expand'] is None
  elif r['active_generation']:
   assert r['I_hold'] is True
   KA=r['current_KA'];AA=None if KA is None else cmp(r['C'],KA['price_adjusted'])>0
   if KA:assert KA['confirmed_at']<day
   BB=None if r['B_base'] is None else False if r['B_base'] is False else cmp(r['C'],r['H12']['price_adjusted'])>0
   assert AA==r['A_active'] and BB==r['B_active'] and tor(AA,BB)==r['I_expand']
  else:assert r['I_expand'] is None if not r['original_event_ready'] else r['I_expand'] is False
  assert r['I_expand']==tor(r['A_active'],r['B_active'])
  if r['confirm_event']:
   assert r['active_generation'] and r['I_expand'] is True and (r['launch_event'] or b['mode_memory']=='START')
  if r['downgrade_events']:assert b['mode_memory']=='CONFIRMED' and r['I_expand'] is False
# Prefix receipts are producer's physical-truncation assertions, not a second replay by this reviewer.
assert len(checks)==14 and all(x['prefix_exact'] for x in checks) and {x['sid'] for x in checks}==set(by)
for sid in by:assert sum(x['sid']==sid for x in checks)==2
fixed=[('000620.SZ','2022-01-07'),('000620.SZ','2022-01-20'),('000620.SZ','2022-02-07'),('601601.SH','2024-08-30'),('002583.SZ','2024-09-20'),('601019.SH','2022-12-12'),('601019.SH','2023-02-10')]
witness=[]
for sid,day in fixed:
 r=next(x for x in by[sid] if x['day']==day)
 witness.append({k:r[k] for k in ['sid','day','C','original_E0_event','generation','mode','I_hold','I_expand','A_active','B_active','B_base','P_old','P_new','L1','H12','L2','initial_KA','current_KA','support_exit_events','confirm_event','lower_high_or_equal_event']})
assert witness[0]['A_active'] is True and witness[0]['B_active'] is False
assert witness[1]['A_active'] is True and witness[1]['B_active'] is False and witness[1]['P_new']>witness[1]['P_old']
assert witness[2]['mode']=='OFF' and witness[2]['support_exit_events']
assert witness[3]['A_active'] is False and witness[3]['B_active'] is True
assert witness[4]['A_active'] is True and witness[4]['B_active'] is False
assert witness[5]['I_expand'] is False and witness[5]['lower_high_or_equal_event']['effective_raise']
assert witness[6]['A_active'] is False and witness[6]['B_active'] is True
for p in [code,F/'SIGNAL_FREEZE_V2.md',D/'ALL_DAILY_TRACES.json',D/'RUN_RECEIPT.json',D/'PREFIX_CHECKS.json'] :S[str(p.resolve())]=sha(p)
result=dict(status='PASS_V2_STATIC_IMPLEMENTATION_AND_EXISTING_SIGNAL_ROWS_WITH_LIMITS',remaining_blocks=[],stocks=len(by),display_rows=len(rows),all_display_price_event_rows_source_exact=len(rows),unique_pivot_source_points_checked=len(all_points),valid_HL_adjacent_pair_row_checks=adjacent_checks,support_exit_rows=exits,launch_rows=launches,P_raise_rows=updates,lower_high_rows=lh,same_close_exit_new_start_rows=same_day_exit_start,producer_physical_prefix_checks_read=14,compare_body_AST_exact_to_original_numeric=True,key_witnesses=witness,source_sha256=S,limits=['No independent second trace/state-engine replay or new hypothetical price tests.','14 prefix assertions are verified producer receipts plus static causal loop review, not independently rerun by reviewer.','No cold account, cash, fill, CP recomputation or economic-effect audit.','Source UNKNOWN and missing-volume branch observations limited to saved actual source coverage; synthetic edge tests not run.'],new_accounts=0,new_backtests=0,new_E0_or_CP_recalculations=0,models_imported_or_called=0)
(O/'V2_IMPLEMENTATION_AND_TRACE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','stocks','display_rows','unique_pivot_source_points_checked','valid_HL_adjacent_pair_row_checks','support_exit_rows','launch_rows','P_raise_rows','lower_high_rows','same_close_exit_new_start_rows']},ensure_ascii=False))
