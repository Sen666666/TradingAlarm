"""Fixed original-layer peak/CP-scale annotation and k2/3/4 scan. No account imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,csv,hashlib,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def frame(p,h=None):
 p=Path(p);a=sha(p);assert h is None or a==h;SRC[str(p.resolve())]=a;return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
p=read(O/'PROTOCOL.json');selection=p['target_mobile_layers'];ks=[2,3,4]
base=Q/'mobile_ema20_exit_audit_v1/candidate_timeline'
original=read(base/'DAILY_TIMELINE.json')
b=read(Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz',True)
buys={x['layer']:x for x in b['trades'] if x['side']=='buy'}
layers={x['id']:x for x in b['layers']}
bj={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'}
ms={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
annual={x['sid']:x for x in read(F/'inputs/MANIFEST.json')}
facts={};cp={};receipt={};ok={};source_refs={}
for sid in selection:
 m=ms[sid];facts[sid]=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])
 cp[sid]=frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])
 sp=next(x for x in m['source_sha256'] if x.endswith('/signal.parquet'))
 r=frame(sp,m['source_sha256'][sp]).reindex(facts[sid].index);f=facts[sid]
 ok[sid]=(r.price_eligible.eq(True)&r.observed_bar.eq(True)&r.source_invalid.eq(False)
  &r.synthetic_event_bar.eq(False)&np.isfinite(f.close)&f.close.gt(0)
  &r.segment_id.eq(f.segment_id)&np.isclose(r.close,f.close,rtol=1e-10,atol=1e-10))
 ap=Path(annual[sid]['output_path']);assert sha(ap)==annual[sid]['output_sha256']
 receipt[sid]={r['confirmed_day']:r for r in read(ap)}
 source_refs[sid]=dict(facts=m['refs']['facts'],CP1=m['refs']['CP1'],canonical_2024_receipts=str(ap),original_signal=sp)

def cp_source(sid,day):
 r=receipt[sid].get(day);d=pd.Timestamp(day);z=cp[sid]
 if r is None or d not in z.index:return dict(kind='UNKNOWN',reason='canonical_receipt_or_cache_day_missing')
 q=z.loc[d]
 if not bool(q.receipt) or float(q.candidate)!=float(r['original_candidate']) or float(q.scale)!=float(r['original_scale']):
  return dict(kind='UNKNOWN',reason='canonical_original_scale_or_candidate_mismatch')
 if r.get('trace_unknown'):return dict(kind='UNKNOWN',reason='canonical_trace_unknown',receipt=r)
 return dict(kind='CP',receipt_id=r['receipt_id'],confirmed_day=day,
  candidate=r['original_candidate'],original_scale=r['original_scale'],cache_q_scale=float(q.scale),
  cache_q_next_scale_not_used=float(q.next_scale),cache_current_s63_not_used=float(q.s),
  scale_frozen_at=r.get('scale_frozen_at'),source_segment=r['source_segment'],receipt=r)

state={};rows=[];annotations=[]
for t in original:
 sid=t['sid']
 if sid not in selection:continue
 day=t['day'];dt=pd.Timestamp(day);f=facts[sid];q=cp[sid].loc[dt] if dt in cp[sid].index else None
 for h in t['original_layer_state']:
  lid=h['layer']
  if lid not in selection[sid] or h['kind']!='add':continue
  entry=buys[lid];sd=entry['signal_at'][:10];old=D(h['old_floor_used_at_original_CLOSE_adj']);after=D(h['floor_after_original_CLOSE_adj'])
  if lid not in state:
   sdt=pd.Timestamp(sd);fi=f.loc[sdt];cq=cp[sid].loc[sdt]
   floorI=D(str(fi.i_floor));floorCP=D(str(cq.candidate))
   # Exact native source priority: max(I, CP) keeps I on an exact tie.
   initial=max(floorI,floorCP)
   src=dict(kind='I',known_at=sd,floor=str(floorI),reason='initial_I_first_max')
   if floorCP>floorI:src=cp_source(sid,sd)
   assert D(entry['floor'])==initial==old,(sid,lid,'entry_floor_not_equal')
   if src['kind']=='CP':assert bj[lid]['CP1_id']==src['receipt_id']
   state[lid]=dict(floor=initial,source=src)
  st=state[lid];assert st['floor']==old,(sid,lid,day,'old_snapshot_provenance_disagrees')
  before_src=st['source'].copy();reasons=[]
  opened=pd.Timestamp(layers[lid]['opened'][:10]);entry_segment=f.loc[opened,'segment_id']
  history=f.loc[(f.index>=opened)&(f.index<dt)&ok[sid]]
  if not bool(t['valid_current_quote']):reasons.append('INVALID_CURRENT_QUOTE')
  if f.loc[dt,'segment_id']!=entry_segment or (len(history) and not history.segment_id.eq(entry_segment).all()):
   reasons.append('PRICE_SOURCE_DOMAIN_CHANGED')
  if history.empty:
   peak=peakday=None;reasons.append('NO_PRIOR_OWNED_VALID_CLOSE')
  else:
   peak=float(history.close.max());peakday=str(history.close.idxmax().date())
  if before_src['kind']!='CP':reasons.append('I_DOMINATED_NO_ACTIVE_CP_SCALE' if before_src['kind']=='I' else 'UNKNOWN_OLD_FLOOR_PROVENANCE')
  scale=float(before_src['original_scale']) if before_src['kind']=='CP' else None
  if scale is not None and (not math.isfinite(scale) or scale<=0):reasons.append('INVALID_ACTIVE_CP_SCALE')
  C=float(f.loc[dt,'close']);dd=math.log(peak/C) if peak is not None else None
  factor=float(f.loc[dt,'factor']);factorok=bool(math.isfinite(factor) and factor>0 and np.isclose(C,factor*float(f.loc[dt,'raw_close']),rtol=1e-10,atol=1e-10))
  hits={str(k):bool(dd>k*scale) if not reasons else None for k in ks}
  req=h['original_first_request'];relation='before' if not req or day<req[:10] else 'same_CLOSE' if day==req[:10] else 'after_request_pending'
  row=dict(sid=sid,name=t['name'],layer=lid,day=day,signal_at=t['signal_at'],original_qty=h['qty'],
   actual_entry_at=layers[lid]['opened'],original_first_request=req,original_fill_closed=layers[lid].get('closed'),
   pending_before_original_CLOSE=h['pending_before_original_CLOSE'],pending_after_original_CLOSE=h['pending_after_original_CLOSE'],
   relation_to_original_request=relation,eligible=not reasons,status='ELIGIBLE' if not reasons else reasons[0],unknown_reasons=reasons,
   adjusted_C=C,raw_C=float(f.loc[dt,'raw_close']),H_prior_adjusted=peak,H_prior_day=peakday,
   H_prior_raw_current_units=peak/factor if factorok and peak is not None else None,
   log_H_prior_over_C=dd,s_activeCP=scale,drawdown_in_active_CP_scales=dd/scale if dd is not None and scale else None,
   old_floor_adj=str(old),old_floor_raw=float(old)/factor if factorok else None,
   old_floor_source=before_src,after_CLOSE_floor_adj=str(after),
   I_target=t['I_target'],I_floor_adj=t['I_floor_adj'],same_day_CP_receipt=t['CP_receipt'],
   same_day_CP_candidate_adj=t['CP_candidate_adj'],same_day_CP_not_used_for_this_test=True,
   k_hits=hits,strictly_earlier_hits={str(k):hits[str(k)] is True and relation=='before' for k in ks},
   earliest_next_market_OPEN=t['earliest_next_market_OPEN'],no_fill_or_return_assumed=True,
   raw_display_status='READY' if factorok else 'UNKNOWN')
  rows.append(row)
  # Attribute only actual recorded floor increases. Equal max keeps the old source.
  new_src=before_src.copy();reconstructed=old
  if after>old:
   iv=t['I_floor_adj']
   if iv is not None and D(str(iv))>reconstructed:
    reconstructed=D(str(iv));new_src=dict(kind='I',known_at=day,floor=str(reconstructed),reason='I_strictly_raised_original_floor')
   if q is not None and bool(q.receipt) and D(str(q.candidate))>reconstructed:
    reconstructed=D(str(q.candidate));new_src=cp_source(sid,day)
   assert reconstructed==after,(sid,lid,day,'actual_increase_source_unresolved',str(reconstructed),str(after))
  else:assert after==old,(sid,lid,day,'unexpected_floor_decrease')
  st['floor']=after;st['source']=new_src
  annotations.append(dict(sid=sid,layer=lid,day=day,old_floor=str(old),after_floor=str(after),old_source=before_src,
   after_source=new_src,unchanged_floor_preserves_old_source=bool(after==old),source_of_actual_increase_only=True))

firsts=[]
for sid,ids in selection.items():
 for lid in ids:
  rr=[x for x in rows if x['sid']==sid and x['layer']==lid]
  for k in ks:
   hh=[x for x in rr if x['k_hits'][str(k)] is True]
   first=hh[0] if hh else None
   firsts.append(dict(sid=sid,layer=lid,k=k,original_first_request=rr[0]['original_first_request'],
    first_trigger=first['day'] if first else None,first_trigger_relation=first['relation_to_original_request'] if first else None,
    first_trigger_record=first,eligible_holding_days=sum(x['eligible'] for x in rr),total_original_holding_days=len(rr),
    unknown_reason_counts=dict(Counter(v for x in rr for v in x['unknown_reasons']))))
stock=[]
for sid in selection:
 for k in ks:
  ff=[x for x in firsts if x['sid']==sid and x['k']==k];dates=[x['first_trigger'] for x in ff if x['first_trigger']]
  stock.append(dict(sid=sid,k=k,first_trigger=min(dates) if dates else None,
   first_strictly_earlier_trigger=min((x['first_trigger'] for x in ff if x['first_trigger_relation']=='before'),default=None),
   layers=[dict(layer=x['layer'],first_trigger=x['first_trigger'],relation=x['first_trigger_relation']) for x in ff]))
save('DAILY_LAYER_SCAN.json',rows);save('FLOOR_PROVENANCE.json',annotations)
save('FIRST_HITS_BY_LAYER_K.json',firsts);save('SIX_STOCK_FIRST_HITS.json',stock)
save('HAINENGDA_ALL_TRIGGER_DAYS.json',[x for x in rows if x['sid']=='002583.SZ' and any(v is True for v in x['k_hits'].values())])
with (O/'DAILY_LAYER_SCAN.csv').open('w',newline='') as f:
 flat=[{k:(json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(dict,list)) else clean(v)) for k,v in r.items()} for r in rows]
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
save('SOURCE_AND_VALIDATION.json',dict(status='FIXED_ORIGINAL_PATH_CONDITION_SCAN_NOT_ACCOUNT_OR_ECONOMIC_VALIDATION',
 source_sha256=SRC,source_refs=source_refs,script_sha256=sha(__file__),rows=len(rows),layers=len(state),
 eligible_layer_days=sum(x['eligible'] for x in rows),status_counts=dict(Counter(x['status'] for x in rows)),
 unknown_reason_counts=dict(Counter(r for x in rows for r in x['unknown_reasons'])),
 old_and_after_floor_exact_source_annotation=True,canonical_original_scale_equals_cache_q_scale=True,
 current_s63_or_next_scale_never_substituted=True,equal_max_preserves_prior_source=True,
 new_accounts=0,new_backtests=0,new_strategy_paths=0,strategy_changes=0))
print(json.dumps(clean(stock),ensure_ascii=False))
print('HAI',json.dumps(clean([dict(day=x['day'],layer=x['layer'],C=x['raw_C'],H=x['H_prior_raw_current_units'],s=x['s_activeCP'],dd=x['log_H_prior_over_C'],oldfloor=x['old_floor_raw'],hits=x['k_hits'],relation=x['relation_to_original_request']) for x in rows if x['sid']=='002583.SZ' and any(v is True for v in x['k_hits'].values())]),ensure_ascii=False))
