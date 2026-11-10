"""Thin join of3436 saved actual orders to original CP1/I caches and receipts.
No model/account, no live protection-origin reconstruction.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
from datetime import datetime
import json,hashlib,math,csv
import pandas as pd

getcontext().prec=60
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,z):
 with (O/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,allow_nan=False,default=str)
def number(x):return None if pd.isna(x) else x.item() if hasattr(x,'item') else x
def eq(a,b):return abs(float(a)-float(b))<=max(1e-10,1e-10*max(abs(float(a)),abs(float(b))))
def aggregate(z):
 return dict(rows=len(z),stocks=len({x['sid'] for x in z}),original_cost=sum((D(x['original_cost']) for x in z),D(0)),original_net=sum((D(x['original_net']) for x in z),D(0)),positive_net=sum((D(x['original_net']) for x in z if D(x['original_net'])>0),D(0)),negative_net=sum((D(x['original_net']) for x in z if D(x['original_net'])<0),D(0)))

def main():
 O.mkdir(parents=True,exist_ok=True)
 save('THIN_JOIN_PROTOCOL.json',dict(created_at=datetime.now().astimezone().isoformat(),scope='all2265+1171 actual initial orders, original cached CP1 scale/current z/I floor and canonical source identities',origin='CP1 candidate origin is current confirmed receipt day; scale origin exact canonical scale_frozen_at. I-floor numeric plateau start is not claimed underlying E0 pivot provenance; semantic origin unknown.',exclusions=['no CP1 cold calculation','no live ratchet tracker','no current_z substitution for old scale','no exit policy','no new account','no new5day proxy']))
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 mps={'2022':W/'2022-normal-reference-20261031/inputs/MANIFEST.json','2023':W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json','2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json'}
 manifests={y:{x['sid']:x for x in read(p) if not x['industry']} for y,p in mps.items()}
 mothers={ref:read(B/'loss_correction/entry_risk_commitment_review'/(ref+'_ENTRIES.json')) for ref in ['2022_2024','strong']}
 requests=defaultdict(list)
 for ref,es in mothers.items():
  for x in es:requests[x['sid']].append((ref,x))
 out={r:[] for r in mothers};unknown=[];receipt_checks=0
 for sid,entries in sorted(requests.items()):
  m=sm[sid];fp=Path(m['refs']['facts']);cp=Path(m['refs']['CP1']);assert sha(fp)==m['output_sha256'][str(fp)] and sha(cp)==m['output_sha256'][str(cp)];SRC[str(fp)]=sha(fp);SRC[str(cp)]=sha(cp)
  f=pd.read_parquet(fp,columns=['close','segment_id','i_target','i_floor','factor','raw_close']);z=pd.read_parquet(cp,columns=['receipt','candidate','scale','next_scale','z','s','r','u','v','m','phase','reset_reason','anchor','frontier','credit','displacement','delta_frontier']);assert f.index.equals(z.index)
  on=f.i_target.eq(1);change=f.i_floor.ne(f.i_floor.shift())|f.segment_id.ne(f.segment_id.shift())|on.ne(on.shift())
  plateau=pd.Series(pd.NaT,index=f.index,dtype='datetime64[ns]');plateau.loc[change]=f.index[change];f['I_floor_current_numeric_run_first_visible_day']=plateau.ffill().where(on)
  traces={}
  for year in {e['decision_at'][:4] for _,e in entries if e['receipt']}:
   if year in manifests:rec=manifests[year][sid];p=Path(rec['output_path']);expected=rec['output_sha256']
   else:p=Path(m['refs']['receipts']);expected=m['output_sha256'][str(p)]
   assert sha(p)==expected
   for rr in read(p):traces[rr['receipt_id']]=rr
  for ref,e in entries:
   d=e['decision_at'][:10];dt=pd.Timestamp(d);why=[]
   if dt not in f.index or dt not in z.index:why.append('no_exact_original_cache_row')
   if why:
    row=dict(window=ref,layer=e['layer'],sid=sid,decision_at=e['decision_at'],unknown=why);unknown.append(row);out[ref].append(row);continue
   q=f.loc[dt];c=z.loc[dt];floor=D(e['frozen_initial_adjusted_floor']);intentfloor=D(str(e['frozen_intent']['floor']));Ifloor=D(str(q.i_floor));trace=traces.get(e['receipt']) if e['receipt'] else None
   assert floor==intentfloor
   if e['role']=='mobile':
    assert bool(c.receipt) and trace is not None and not trace['trace_unknown']
    assert trace['canonical_series']==sid and trace['confirmed_day']==d and trace['receipt_id']==e['receipt']
    assert eq(trace['original_scale'],c.scale) and eq(trace['original_candidate'],c.candidate)
    assert eq(floor,max(Ifloor,D(str(c.candidate))))
    assert eq(float(q.close)*math.exp(-math.sqrt(21)*float(c.scale)),c.candidate)
    receipt_checks+=1
    cpval=D(str(c.candidate));binding='I_AND_CP1_TIE' if eq(Ifloor,cpval) else 'CP1_CANDIDATE' if cpval>Ifloor else 'I_FLOOR'
   else:
    assert eq(floor,Ifloor);binding='I_FLOOR_CORE'
   currentz=float(c.z) if pd.notna(c.z) else None;used=float(c.scale) if pd.notna(c.scale) else None
   cp_fields={k:number(c[k]) for k in z.columns}
   visible=q.I_floor_current_numeric_run_first_visible_day
   origin=d if binding=='CP1_CANDIDATE' else None
   initialwidth=math.log(float(q.close)/float(floor)) if floor>0 else None
   row=dict(window=ref,layer=e['layer'],sid=sid,name=e['name'],decision_at=e['decision_at'],actual_fill_at=e['opened'],budget_order=e['budget_order'],role=e['role'],action=e['action'],receipt=e['receipt'],watch_epoch=e['watch_epoch'],original_cost=e['cost'],original_net=e['net'],
    original_order_floor_causal=str(floor),original_frozen_intent_floor_causal=str(intentfloor),original_I_floor_causal=str(Ifloor),initial_order_floor_binding=binding,
    order_floor_unique_semantic_origin_day=origin,order_floor_origin_status='current_receipt_candidate_confirmed' if origin else 'I_origin_unknown_or_tied_do_not_infer_from_current_z',
    I_floor_current_numeric_run_first_visible_day=None if pd.isna(visible) else str(visible.date()),I_floor_semantic_pivot_or_event_origin='unknown_not_traced',
    signal_causal_close=number(q.close),signal_raw_close=number(q.raw_close),signal_factor=number(q.factor),fill_factor=e['fill_factor'],initial_raw_floor_at_actual_fill=e['initial_raw_floor'],actual_execution_raw_price=e['actual_execution_price'],source_segment=int(q.segment_id),
    CP1_cached=cp_fields,CP1_scale_role='actual_mobile_receipt_candidate_scale' if e['role']=='mobile' else 'diagnostic_not_core_exit_scale',
    CP1_used_scale=used,CP1_current_z=currentz,CP1_next_scale=number(c.next_scale),CP1_used_scale_over_current_z=None if used is None or currentz is None or currentz<=0 else used/currentz,
    CP1_scale_frozen_at=None if trace is None else trace.get('scale_frozen_at'),CP1_freeze_to_decision_original_valid_observations=None if trace is None else int(z.index.get_loc(dt)-z.index.get_loc(pd.Timestamp(trace['scale_frozen_at']))),CP1_freeze_age_clock='original CP1 valid observation index, excludes freeze observation and includes decision; never calendar days',CP1_formation_start_exclusive=None if trace is None else trace['formation_start_exclusive'],CP1_scale_id=None if trace is None else trace['scale_id'],
    CP1_canonical_trace=trace,initial_log_distance_close_to_order_floor=initialwidth,
    initial_width_over_used_scale=None if used is None or initialwidth is None else initialwidth/used,
    initial_width_over_current_z=None if currentz is None or initialwidth is None else initialwidth/currentz,
    floor_units='causal_adjusted_signal_price; raw floor at fill divides by that actual fill factor',
    later_ratchet_origin='not_inferred_this_initial_order_join',original_quote_and_scale_caches_unchanged=True,unknown=[])
   assert eq(D(row['initial_raw_floor_at_actual_fill'])*D(row['fill_factor']),floor)
   out[ref].append(row)
 for ref,rows in out.items():
  rows.sort(key=lambda x:x['layer']);assert len(rows)==(2265 if ref=='2022_2024' else 1171);save(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json',rows)
  flat=[]
  for x in rows:
   flat.append({k:x.get(k) for k in ['window','layer','sid','name','decision_at','actual_fill_at','budget_order','role','action','receipt','original_cost','original_net','original_order_floor_causal','original_I_floor_causal','initial_order_floor_binding','order_floor_unique_semantic_origin_day','I_floor_current_numeric_run_first_visible_day','CP1_used_scale','CP1_current_z','CP1_next_scale','CP1_used_scale_over_current_z','CP1_scale_frozen_at','CP1_freeze_to_decision_original_valid_observations','CP1_formation_start_exclusive','initial_log_distance_close_to_order_floor','initial_width_over_used_scale','initial_width_over_current_z','later_ratchet_origin']})
  with (O/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.csv')).open('x') as h:w=csv.DictWriter(h,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 summary={}
 for ref,rows in out.items():
  good=[x for x in rows if not x['unknown']];groups=defaultdict(list)
  for x in good:groups[(x['role'],x['action'],x['initial_order_floor_binding'])].append(x)
  summary[ref]=dict(all=aggregate(good),unknown_rows=len(rows)-len(good),by_role_action_binding=[dict(role=k[0],action=k[1],binding=k[2],**aggregate(v)) for k,v in sorted(groups.items())],CP1_binding_counts=dict(Counter(x['initial_order_floor_binding'] for x in good)))
 save('THIN_JOIN_SUMMARY.json',summary);save('THIN_JOIN_VALIDATION.json',dict(rows=sum(map(len,out.values())),canonical_mobile_receipts_checked=receipt_checks,unknown=unknown,actual_order_floor_equals_frozen_intent=True,mobile_floor_max_I_CP1=True,CP1_candidate_equals_close_exp_minus_sqrt21_usedscale=True,all_canonical_receipt_scale_candidate_and_day_exact=True,raw_causal_floor_mapping=True,no_later_ratchet_source_inferred=True,no_model_calls=True,no_accounts=True))
 save('THIN_JOIN_SOURCES.json',dict(sources=SRC,script_sha256=sha(__file__),actual_entry_rows=3436,new_CP1_calculations=0,new_accounts=0))
 print('ENTRY_SCALE_JOIN_COMPLETE',sum(map(len,out.values())),'mobile',receipt_checks,'unknown',len(unknown),flush=True)
 print(json.dumps({r:s['CP1_binding_counts'] for r,s in summary.items()}),flush=True)
if __name__=='__main__':main()
