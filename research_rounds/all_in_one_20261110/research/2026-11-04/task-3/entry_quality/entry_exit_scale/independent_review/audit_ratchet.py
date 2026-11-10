"""Independent actual-order and old-line audit, with full raw post82 checks."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,math
import pandas as pd
getcontext().prec=70
P=Path(__file__).resolve().parents[1];M=P/'mechanism_review';O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');C=Counter();S={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
def exact(a,b,k):assert D(str(a))==D(str(b)),(k,a,b);C[k]+=1
def close(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-17'),(k,a,b);C[k]+=1
def eqnum(a,b):return abs(float(a)-float(b))<1e-12*max(1,abs(float(a)),abs(float(b)))
def money(rr):
 v=[D(x['original_net']) for x in rr];return dict(layers=len(rr),cost=sum((D(x['original_cost']) for x in rr),Z),net=sum(v,Z),positive=sum((max(Z,x) for x in v),Z),negative=sum((min(Z,x) for x in v),Z))
def checkmoney(rr,g):
 for k,v in money(rr).items():close(v,g[k],'summary_'+k)
manifest=read(M/'ACTUAL_CP_REQUEST_RATCHET_VALIDATION.json');assert sha(M/'check_actual_CP_request_ratchet.py')==manifest['script_SHA256']
for p,h in manifest['source_SHA256'].items():assert sha(p)==h,p;C['producer_source_SHA']+=1
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};cache={}
def quotes(sid):
 if sid not in cache:
  m=sm[sid];f=Path(m['refs']['facts']);cp=Path(m['refs']['CP1'])
  for p in [f,cp]:assert sha(p)==m['output_sha256'][str(p)];S[str(p)]=sha(p)
  cache[sid]=(pd.read_parquet(f,columns=['close','i_floor','i_target','factor','segment_id']),pd.read_parquet(cp,columns=['receipt','candidate','reset_reason']))
 return cache[sid]
allrows={};samples=[];post82=[];exceptions=[]
for ref,pair in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 rows=read(M/(ref+'_ACTUAL_CP_REQUEST_RATCHET_JOIN.json'));allrows[ref]=rows;book=read(pair/'B.json.gz');daily=read(pair/'daily.jsonl.gz');entry={x['layer']:x for x in read(M/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json'))};held={x['layer']:x for x in read(P/'holding_exit'/(ref+'_LAYERS.json'))};clocks={x['layer']:x for x in read(P/'holding_exit'/(ref+'_REQUEST_CLOCK_JOIN.json'))}
 fills={x['receipt']['receipt_id']:x for x in book['audit'] if x['kind']=='fill' and x['receipt']['side']=='sell'};req={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'};pilots=defaultdict(list);sales=defaultdict(list);hist=defaultdict(list)
 for x in book['audit']:
  if x['kind']=='pilot_layer_exit':
   for lid in x['layers']:pilots[lid].append(x)
 for t in book['trades']:
  if t['side']=='sell':
   for part in t['parts']:sales[part['layer']].append((t,part))
 for d in daily:
  for x in d['layers']:hist[x['id']].append((d['at'],x))
 for r in rows:
  lid=r['layer'];e=entry[lid];h=held[lid];c=clocks[lid];assert (r['sid'],r['action'],r['role'])==(e['sid'],e['action'],e['role']);exact(r['original_cost'],e['original_cost'],'original_cost');exact(r['original_net'],e['original_net'],'original_net')
  assert r['original_actual_exit_class']==h['actual_exit_class'];first=pilots[lid][0] if pilots[lid] else None
  assert r['first_pilot_layer_at']==(first['at'] if first else None) and r['first_pilot_reason']==(first['reason'] if first else None)
  if not sales[lid]:assert r['primary_CP_old_line_status']=='NO_EXECUTED_ORDER_PRIMARY_OPEN';continue
  assert len(sales[lid])==1;t,part=sales[lid][0];oid=fills[t['receipt_id']]['order_id'];request=req[oid]
  assert r['primary_actual_order_id']==oid==c['primary_actual_order_id'] and r['primary_actual_order_request_at']==request['at']==c['primary_actual_order_request_at'] and r['actual_exit_at']==t['at'];C['all_actual_order_clock']+=1
  isc=first and first['at']==request['at'] and first['reason']=='CP1_add_protection'
  assert (r['primary_CP_old_line_status']=='VERIFIED_OLD_TESTED_LINE')==bool(isc);C['all_primary_CP_classification']+=1
  if isc and part['reason']!='CP1_add_protection':exceptions.append(dict(ref=ref,layer=lid,sid=r['sid'],primary_order_id=oid,primary_request_at=request['at'],first_reason=first['reason'],actual_reason=part['reason'],actual_at=t['at'],net=r['original_net'],later_specific_requests=[dict(at=x['at'],reason=x['reason']) for x in pilots[lid] if x['at']>request['at']]))
  target=ref=='2022_2024' and ((r['actual_fill_at'][:10]>'2024-10-08' and D(r['original_net'])<0 and r['held_CLOSE_observations_to_fill_or_cutoff']<=5 and isc) or lid in [113,122])
  if not target:continue
  assert isc and r['role']=='mobile';p=request['at'];seq=[(at,x) for at,x in hist[lid] if at<=p];assert seq[-1][0]==p
  initial=D(e['original_order_floor_causal']);old=initial if len(seq)==1 else D(seq[-2][1]['floor']);saved=D(seq[-1][1]['floor']);exact(saved,old,'old_floor_unchanged_on_trigger');exact(saved,r['tested_floor_causal'],'old_tested_floor')
  f,cp=quotes(r['sid']);qt=f.loc[pd.Timestamp(p[:10])];ct=cp.loc[pd.Timestamp(p[:10])]
  assert D(str(qt['close']))<=old and bool(qt.i_target) and seq[-1][1]['reason']=='CP1_add_protection';C['trigger_branch']+=1
  exact(qt['close'],r['tested_causal_close'],'trigger_causal_close');exact(qt['factor'],r['tested_factor'],'trigger_factor');assert bool(ct.receipt)==r['primary_day_cached_new_CP1']
  # Independently inspect every earlier saved floor change, not latest receipt.
  changes=[];prev=initial
  for at,x in seq[:-1]:
   new=D(x['floor']);assert new>=prev,(lid,at,prev,new)
   if new>prev:
    q=f.loc[pd.Timestamp(at[:10])];cpx=cp.loc[pd.Timestamp(at[:10])];candidates={'OLD':prev}
    if pd.notna(q.i_floor):candidates['I_FLOOR']=D(str(q.i_floor))
    if bool(cpx.receipt) and pd.notna(cpx.candidate):candidates['CP1_RECEIPT']=D(str(cpx.candidate))
    assert D(str(q['close']))>prev and bool(q.i_target);exact(new,max(candidates.values()),'pretrigger_raise_max_inputs')
    bindings=[k for k,v in candidates.items() if k!='OLD' and v==new];assert bindings,(lid,at,new,candidates)
    assert q.segment_id==qt.segment_id,(lid,'cross source segment')
    changes.append(dict(at=at,previous=str(prev),floor=str(new),bindings=bindings,I=None if pd.isna(q.i_floor) else str(q.i_floor),CP=str(cpx.candidate) if bool(cpx.receipt) else None));C['every_prior_raise']+=1
   prev=new
  if old==initial:
   assert r['entry_to_primary_CP_ratchet']=='UNCHANGED_ENTRY_LINE' and not changes and r['latest_recorded_raise_before_trigger'] is None
  else:
   assert old>initial and r['entry_to_primary_CP_ratchet']=='RAISED_SINCE_ENTRY' and changes
   latest=changes[-1];actual=r['latest_recorded_raise_before_trigger'];assert latest['at']==actual['at'];exact(latest['floor'],actual['new_floor_causal'],'latest_raise_value');exact(latest['previous'],actual['previous_floor_causal'],'latest_raise_previous');assert latest['bindings']==actual['matching_sources'];assert latest['bindings']==['CP1_RECEIPT'];assert r['tested_line_binding_from_recorded_latest_raise_or_entry']=='CP1_RECEIPT';C['unique_CP_numeric_binding']+=1
  if lid not in [113,122]:post82.append(r)
  samples.append(dict(layer=lid,sid=r['sid'],primary=p,initial=str(initial),tested=str(old),actual_reason=part['reason'],raises=changes,trigger_has_newCP=bool(ct.receipt)))
summary=read(M/'ACTUAL_CP_REQUEST_RATCHET_SUMMARY.json')
for key,g in summary.items():
 ref,scope=key.split('|');rr=allrows[ref]
 if scope=='all_negative':rr=[r for r in rr if D(r['original_net'])<0]
 elif scope=='two_year':rr=[r for r in rr if r['actual_fill_at'][:10]<'2024-01-01']
 elif scope.startswith('post303'):
  rr=[r for r in rr if r['actual_fill_at'][:10]>'2024-10-08']
  if scope=='post303_negative_held_to_fill_at_most5':rr=[r for r in rr if D(r['original_net'])<0 and r['held_CLOSE_observations_to_fill_or_cutoff']<=5]
  elif scope=='post303_negative_primary_request_at_most5':rr=[r for r in rr if D(r['original_net'])<0 and r['entry_to_primary_request_held_CLOSE_observations'] is not None and r['entry_to_primary_request_held_CLOSE_observations']<=5]
 checkmoney(rr,g['all']);assert dict(Counter(r['primary_CP_old_line_status'] for r in rr))==g['primary_status'];known=[r for r in rr if r['primary_CP_old_line_status']=='VERIFIED_OLD_TESTED_LINE'];checkmoney(known,g['verified_primary_CP'])
 for label,d in [('entry_to_primary_CP_ratchet','by_ratchet'),('tested_line_binding_from_recorded_latest_raise_or_entry','by_current_line_binding')]:
  assert set(g[d])=={r[label] for r in known}
  for v,m in g[d].items():checkmoney([r for r in known if r[label]==v],m)
assert len(post82)==82 and Counter(r['entry_to_primary_CP_ratchet'] for r in post82)==dict(UNCHANGED_ENTRY_LINE=61,RAISED_SINCE_ENTRY=21)
assert {(x['ref'],x['layer']) for x in exceptions}=={('2022_2024',113),('2022_2024',122)}
supp=read(M/'ACTUAL_SELL_CP_SLICE_SUPPLEMENT.json')
for ref,rr in allrows.items():
 primary=[r for r in rr if r['primary_CP_old_line_status']=='VERIFIED_OLD_TESTED_LINE'];ex=[r for r in primary if r['original_actual_exit_class']!='CP1_add_protection'];checkmoney(primary,supp['refs'][ref]['primary_CP_request']);checkmoney(ex,supp['refs'][ref]['primary_CP_later_actual_reason_other']['money']);assert {r['layer'] for r in ex}=={r['layer'] for r in supp['refs'][ref]['primary_CP_later_actual_reason_other']['rows']}
 for scope,g in supp['refs'][ref]['actual_sell_reason_CP_slice'].items():
  sr=[r for r in primary if r['original_actual_exit_class']=='CP1_add_protection']
  if scope=='two_year':sr=[r for r in sr if r['actual_fill_at'][:10]<'2024-01-01']
  elif scope.startswith('post303'):
   sr=[r for r in sr if r['actual_fill_at'][:10]>'2024-10-08']
   if scope.endswith('at_most5'):sr=[r for r in sr if D(r['original_net'])<0 and r['held_CLOSE_observations_to_fill_or_cutoff']<=5]
  checkmoney(sr,g['all'])
  for field,col in [('entry_to_primary_CP_ratchet','by_ratchet'),('tested_line_binding_from_recorded_latest_raise_or_entry','by_numeric_source_label')]:
   for v,m in g[col].items():checkmoney([r for r in sr if r[field]==v],m)
native=W/'case-stage-ledger-20261031/v3/joint_v3.py';code=native.read_text();assert "if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')\n     else:" in code and "if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))" in code;S[str(native)]=sha(native)
out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(C),raw_quote_scope='All82 post303 negative <=5 held CLOSE primaryCP layers, plus000620 layers113/122. Every saved pretrigger raise checked against max(previous,I,eligible same-day CP candidate); not just last receipt.',post82=dict(all=money(post82),by_ratchet={v:money([r for r in post82 if r['entry_to_primary_CP_ratchet']==v]) for v in ['UNCHANGED_ENTRY_LINE','RAISED_SINCE_ENTRY']}),actual_reason_exceptions=exceptions,checked_layer_traces=samples,source_sha256=S,producer_source_sha256=manifest['source_SHA256'],limits=['All3436 raw book identity/actual executed order creation clocks and primary classification checked; price/line cold-check limited to84 layers; full3436 summary amounts rebuilt.','CP1_RECEIPT latest-raise attribution is a unique exact numerical source match among max inputs, not canonical receipt-ID provenance. No unknown or ties observed in requested21.','Primary CP request and actual sell.parts reason differ on000620 layers113/122: subsequent I request while fill delayed.728 two-year primaryCP cannot be called726 actualCP.','Life P&L in short holding groups is association, not delay loss or a measured benefit from a wider/slower exit.','Trigger-day saved layer floor is unchanged pre-check line. The82 requested trigger dates contain zero newCP receipts; native branch ordering independently confirms no same-bar later-update substitution.'],new_accounts=0)
(O/'CP_RATCHET_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['source_sha256','producer_source_sha256','checked_layer_traces']},ensure_ascii=False,indent=2,default=str))
