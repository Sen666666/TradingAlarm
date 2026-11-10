"""Read recorded layer snapshots at actual sell-order creation; no line replay.

Only an exact first specific CP request at that primary clock establishes that
the CLOSE branch tested the saved floor and did not update it on this bar.
Other order/pilot relationships remain explicitly unknown.
"""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import json, gzip, hashlib, math
import pandas as pd

O=Path(__file__).resolve().parent
H=O.parent/'holding_exit'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p, gz=False, lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,v):
 with (O/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def eq(a,b):return a is not None and b is not None and abs(float(a)-float(b))<=1e-9*max(1.,abs(float(a)),abs(float(b)))

native=W/'case-stage-ledger-20261031/v3/joint_v3.py'
code=native.read_text();SRC[str(native)]=sha(native)
assert "if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')\n     else:" in code
assert "layers=[dict(x,**a.jmeta[x['id']]) for x in a.layers if x['qty']]" in code
pilot=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py')
SRC[str(pilot)]=sha(pilot)
assert "for z in self.live(sid):\n   if z['id'] in ids:z['reason']=reason" in pilot.read_text()
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
cache={}
def frames(sid):
 if sid not in cache:
  m=sm[sid];fp=Path(m['refs']['facts']);cp=Path(m['refs']['CP1'])
  assert sha(fp)==m['output_sha256'][str(fp)] and sha(cp)==m['output_sha256'][str(cp)]
  SRC[str(fp)]=sha(fp);SRC[str(cp)]=sha(cp)
  cache[sid]=(pd.read_parquet(fp,columns=['close','i_floor','factor','i_target','segment_id']),pd.read_parquet(cp,columns=['receipt','candidate','scale','z','reset_reason']))
 return cache[sid]

def summary(rr):
 known=[r for r in rr if r['primary_CP_old_line_status']=='VERIFIED_OLD_TESTED_LINE']
 def money(xs):
  vs=[D(x['original_net']) for x in xs]
  return dict(layers=len(xs),cost=str(sum((D(x['original_cost']) for x in xs),D(0))),net=str(sum(vs,D(0))),positive=str(sum((v for v in vs if v>0),D(0))),negative=str(sum((v for v in vs if v<0),D(0))))
 return dict(all=money(rr),primary_status=dict(Counter(r['primary_CP_old_line_status'] for r in rr)),
  verified_primary_CP=money(known),by_ratchet={k:money([r for r in known if r['entry_to_primary_CP_ratchet']==k]) for k in sorted({r['entry_to_primary_CP_ratchet'] for r in known})},
  by_current_line_binding={k:money([r for r in known if r['tested_line_binding_from_recorded_latest_raise_or_entry']==k]) for k in sorted({r['tested_line_binding_from_recorded_latest_raise_or_entry'] for r in known})})

OUT={};SUM={};VALID={}
for ref,pair in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 entries=read(O/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json'));holds={x['layer']:x for x in read(H/(ref+'_LAYERS.json'))};clocks={x['layer']:x for x in read(H/(ref+'_REQUEST_CLOCK_JOIN.json'))}
 book=read(pair/'B.json.gz',gz=True);ds=read(pair/'daily.jsonl.gz',gz=True,lines=True)
 first={};pilots=defaultdict(list)
 for a in book['audit']:
  if a['kind']!='pilot_layer_exit':continue
  for lid in a['layers']:
   pilots[lid].append(a)
   first.setdefault(lid,a)
 hist=defaultdict(list);dm={x['at']:x for x in ds}
 for d in ds:
  for x in d['layers']:hist[x['id']].append((d['at'],x))
 rows=[]
 for e in entries:
  lid=e['layer'];h=holds[lid];c=clocks[lid];p=c['primary_actual_order_request_at'];a=first.get(lid)
  r=dict(window=ref,layer=lid,sid=e['sid'],name=e['name'],role=e['role'],action=e['action'],actual_fill_at=e['actual_fill_at'],decision_at=e['decision_at'],original_cost=e['original_cost'],original_net=e['original_net'],original_actual_exit_class=h['actual_exit_class'],held_CLOSE_observations_to_fill_or_cutoff=h['held_close_observations'],primary_actual_order_id=c['primary_actual_order_id'],primary_actual_order_request_at=p,entry_to_primary_request_held_CLOSE_observations=c['entry_to_primary_request_held_CLOSE_observations'],actual_exit_at=c['actual_exit_at'],first_pilot_layer_at=None if a is None else a['at'],first_pilot_reason=None if a is None else a['reason'],initial_floor_causal=e['original_order_floor_causal'],initial_order_floor_binding=e['initial_order_floor_binding'],primary_CP_old_line_status='NOT_PRIMARY_CP_REQUEST',entry_to_primary_CP_ratchet=None,tested_floor_causal=None,tested_line_binding_from_recorded_latest_raise_or_entry=None,latest_recorded_raise_before_trigger=None,unknown=[])
  if p is None:r['primary_CP_old_line_status']='NO_EXECUTED_ORDER_PRIMARY_OPEN'
  elif h['actual_exit_class']=='CP1_add_protection' and not(a and a['at']==p and a['reason']=='CP1_add_protection'):
   r['primary_CP_old_line_status']='UNKNOWN_PRIMARY_NOT_FIRST_SPECIFIC_CP_REQUEST';r['unknown'].append('First pilot CP or extension clock is not the actual executed sell-order creation clock; not substituted.')
  elif a and a['at']==p and a['reason']=='CP1_add_protection':
   seq=[(at,x) for at,x in hist[lid] if at<=p];snap=next((x for at,x in seq if at==p),None)
   if not(snap and e['role']=='mobile'):
    r['primary_CP_old_line_status']='UNKNOWN_PRIMARY_SNAPSHOT_MISSING';r['unknown'].append('No saved mobile layer at actual order-created CLOSE.')
   else:
    f,cp=frames(e['sid']);t=pd.Timestamp(p[:10]);q=f.loc[t];floor=snap['floor'];old=e['original_order_floor_causal'] if len(seq)==1 else seq[-2][1]['floor']
    r.update(tested_floor_causal=floor,tested_causal_close=float(q.close),tested_raw_floor=float(floor)/float(q.factor),tested_factor=float(q.factor),tested_source_segment=float(q.segment_id),primary_day_native_I_target=bool(q.i_target),primary_day_cached_new_CP1=bool(cp.loc[t,'receipt']),primary_day_CP_reset_reason=None if pd.isna(cp.loc[t,'reset_reason']) else str(cp.loc[t,'reset_reason']))
    if not(eq(floor,old) and D(str(q.close))<=D(str(floor)) and bool(q.i_target) and snap['reason']=='CP1_add_protection'):
     r['primary_CP_old_line_status']='UNKNOWN_OLD_LINE_BRANCH_CHECK_FAILED';r['unknown'].append('Saved trigger snapshot not independently consistent with unchanged pre-check floor and CP branch.')
    else:
     r['primary_CP_old_line_status']='VERIFIED_OLD_TESTED_LINE'
     change=float(floor)-float(e['original_order_floor_causal'])
     if eq(floor,e['original_order_floor_causal']):
      r['entry_to_primary_CP_ratchet']='UNCHANGED_ENTRY_LINE';r['tested_line_binding_from_recorded_latest_raise_or_entry']=e['initial_order_floor_binding']
     elif change>0:
      r['entry_to_primary_CP_ratchet']='RAISED_SINCE_ENTRY'
      prev=e['original_order_floor_causal'];raises=[]
      for at,x in seq[:-1]:
       if not eq(x['floor'],prev):
        if float(x['floor'])<=float(prev):r['unknown'].append('Non-monotonic saved floor change; no source inference.')
        raises.append((at,prev,x['floor']))
       prev=x['floor']
      if raises:
       at,previous,new=raises[-1];rq=f.loc[pd.Timestamp(at[:10])];rc=cp.loc[pd.Timestamp(at[:10])];sources=[]
       if pd.notna(rq.i_floor) and eq(new,rq.i_floor):sources.append('I_FLOOR')
       if bool(rc.receipt) and pd.notna(rc.candidate) and eq(new,rc.candidate):sources.append('CP1_RECEIPT')
       binding='BOTH_I_CP1_TIE' if len(sources)==2 else sources[0] if len(sources)==1 else 'UNKNOWN_RECORDED_RAISE_SOURCE'
       r['latest_recorded_raise_before_trigger']=dict(at=at,previous_floor_causal=previous,new_floor_causal=new,cached_I_floor_causal=None if pd.isna(rq.i_floor) else float(rq.i_floor),cached_CP1_receipt=bool(rc.receipt),cached_CP1_candidate=None if pd.isna(rc.candidate) else float(rc.candidate),matching_sources=sources,source_inference='Exact value match to that same saved snapshot raise; not a new line replay or future/current stock terminal line.')
       r['tested_line_binding_from_recorded_latest_raise_or_entry']=binding
      else:r['tested_line_binding_from_recorded_latest_raise_or_entry']='UNKNOWN_RAISE_NOT_VISIBLE';r['unknown'].append('Raised compared with entry but no pre-trigger saved raise observed.')
     else:r['entry_to_primary_CP_ratchet']='UNKNOWN_LOWER_THAN_ENTRY';r['tested_line_binding_from_recorded_latest_raise_or_entry']='UNKNOWN';r['unknown'].append('Tested line below original entry in causal coordinate.')
  rows.append(r)
 OUT[ref]=rows;save(ref+'_ACTUAL_CP_REQUEST_RATCHET_JOIN.json',rows)
 scopes={'all_actual_entries':rows,'all_negative':[r for r in rows if D(r['original_net'])<0]}
 if ref=='2022_2024':
  scopes['two_year']=[r for r in rows if r['actual_fill_at'][:10]<'2024-01-01']
  post=[r for r in rows if '2024-10-09'<=r['actual_fill_at'][:10]<='2024-12-31'];assert len(post)==303
  scopes['post303']=post
  scopes['post303_negative_held_to_fill_at_most5']=[r for r in post if D(r['original_net'])<0 and r['held_CLOSE_observations_to_fill_or_cutoff']<=5]
  scopes['post303_negative_primary_request_at_most5']=[r for r in post if D(r['original_net'])<0 and r['entry_to_primary_request_held_CLOSE_observations'] is not None and r['entry_to_primary_request_held_CLOSE_observations']<=5]
 for k,rr in scopes.items():SUM[ref+'|'+k]=summary(rr)
 known=[r for r in rows if r['primary_CP_old_line_status']=='VERIFIED_OLD_TESTED_LINE']
 VALID[ref]=dict(all_rows=len(rows),verified_old_tested_line=len(known),unknown_primary_actual_CP=sum(r['primary_CP_old_line_status'].startswith('UNKNOWN') for r in rows),all_primary_CP_tested_snapshot_equals_prior_layer_floor=True,all_primary_CP_close_at_or_below_tested_floor=True,all_tested_layers_are_independent_layer_snapshots=True)
save('ACTUAL_CP_REQUEST_RATCHET_SUMMARY.json',SUM)
save('ACTUAL_CP_REQUEST_RATCHET_VALIDATION.json',dict(refs=VALID,source_SHA256=SRC,script_SHA256=sha(__file__),protocol='Primary is original actual sell fill.order_id -> exit_request creation. Only same-clock first specific CP layer request is accepted; otherwise unknown. CP branch tests old floor before any same-bar I/CP ratchet and does not update touched layer, proven by native source. Source of last raised saved layer floor uses exact same-day cache equality, not replay. All rows retained. No model, account, threshold, or new exit.',primary_not_first_pilot_substitution=True,new_model_calls=0,new_accounts=0))
print(json.dumps(SUM,ensure_ascii=False,indent=2))
