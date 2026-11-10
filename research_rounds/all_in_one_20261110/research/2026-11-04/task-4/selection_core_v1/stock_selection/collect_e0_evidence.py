"""Read three frozen dates' original E0 events and native facts, no model calls."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
DATES=['2024-09-24','2026-01-15','2022-01-24'];sha={};rows=[];begun=time.monotonic()
def bind(p,expected=None):
 p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert sha[str(p)]==expected,('source changed',str(p))
 return p
def n(v):
 try:x=float(v)
 except (TypeError,ValueError):return None
 return x if np.isfinite(x) else None
sm=json.loads(bind(U/'STOCK_MANIFEST.json').read_text());bind(P/'FROZEN_STATIC_DIAGNOSTIC.txt')
for k,s in enumerate(sm,1):
 sid=s['symbol'];refs=[p for p in s['source_sha256'] if '/prepared' in p and p.endswith('/events.parquet')];assert len(refs)==1
 ep=refs[0];f=pd.read_parquet(bind(ep,s['source_sha256'][ep]));fp=s['refs']['facts'];g=pd.read_parquet(bind(fp,s['output_sha256'][fp]),columns=['e0_target','e0_ready','segment_id'])
 for date in DATES:
  t=pd.Timestamp(date);er=f.loc[t] if t in f.index else None;nr=g.loc[t] if t in g.index else None;pr=g.loc[g.index<t].tail(1)
  pv=pr.iloc[0] if len(pr) else None
  r={'sid':sid,'date':date,'E0_original_events_ref':ep,'E0_original_events_exact_date':er is not None,'native_facts_exact_date':nr is not None,
   'source_E0_event':n(er['event']) if er is not None else None,'source_E0_entered':n(er['entered']) if er is not None else None,
   'source_E0_target':n(er['target']) if er is not None else None,'source_E0_segment':n(er['segment_id']) if er is not None else None,
   'source_E0_confirmed_pivot_price':n(er['confirmed_pivot_price']) if er is not None else None,'source_E0_confirmed_pivot_date':None if er is None or pd.isna(er['confirmed_pivot_date']) else str(er['confirmed_pivot_date']),
   'native_E0_target':n(nr['e0_target']) if nr is not None else None,'native_E0_ready':n(nr['e0_ready']) if nr is not None else None,
   'native_E0_segment':n(nr['segment_id']) if nr is not None else None,'native_E0_previous_date':pr.index[0].strftime('%Y-%m-%d') if len(pr) else None,
   'native_E0_previous_target':n(pv['e0_target']) if pv is not None else None,'native_E0_previous_ready':n(pv['e0_ready']) if pv is not None else None,
   'native_E0_previous_segment':n(pv['segment_id']) if pv is not None else None,
   'source_E0_target_segment_matches_native_fact':None,'native_E0_0_to_1':None,'native_E0_1_to_1':None,
   'START_saved_original_evidence':None,'START_event_type':None,
   'scope':'Original prepared E0 price-event fields, independently compared with native facts; not legacy companion pending/I entered and not a newly recomputed event.'}
  if er is not None and nr is not None:
   r['source_E0_target_segment_matches_native_fact']=bool(r['source_E0_target']==r['native_E0_target'] and r['source_E0_segment']==r['native_E0_segment'])
   if r['source_E0_target_segment_matches_native_fact']:
    r['START_saved_original_evidence']=bool(r['source_E0_event'] is not None and r['source_E0_event']>0 or r['source_E0_entered']==1)
  if pv is not None and nr is not None and r['native_E0_ready']==1 and r['native_E0_previous_ready']==1 and r['native_E0_segment']==r['native_E0_previous_segment']:
   r['native_E0_0_to_1']=r['native_E0_previous_target']==0 and r['native_E0_target']==1
   r['native_E0_1_to_1']=r['native_E0_previous_target']==1 and r['native_E0_target']==1
  if r['START_saved_original_evidence'] is True:
   if r['native_E0_0_to_1'] is True:r['START_event_type']='FIRST_DOMAIN_START_NATIVE_TARGET_0_TO_1'
   elif r['native_E0_1_to_1'] is True and r['source_E0_event'] is not None and r['source_E0_event']>0:r['START_event_type']='IN_VALID_DOMAIN_POSITIVE_STRUCTURE_EVENT'
   else:r['START_event_type']='SAVED_START_EVIDENCE_DOMAIN_IDENTITY_UNKNOWN'
  elif r['START_saved_original_evidence'] is False:r['START_event_type']='NO_START_EVIDENCE_TODAY'
  else:r['START_event_type']='UNKNOWN_SOURCE_OR_NATIVE_EQUIVALENCE'
  rows.append(r)
 if k%400==0:print('PROGRESS',k,round(time.monotonic()-begun,2),flush=True)
d=pd.DataFrame(rows);assert len(d)==5127 and not d.duplicated(['sid','date']).any();d.to_parquet(O/'E0_THREE_DATE_EVIDENCE.parquet',index=False);d.to_csv(O/'E0_THREE_DATE_EVIDENCE.csv',index=False)
summary={'rows':len(d),'source_native_comparable':int(d.source_E0_target_segment_matches_native_fact.notna().sum()),'source_native_target_segment_mismatch':int(d.source_E0_target_segment_matches_native_fact.eq(False).sum()),'START_saved_evidence':int(d.START_saved_original_evidence.eq(True).sum()),'event_types':d.START_event_type.value_counts().to_dict(),'seconds':time.monotonic()-begun,'model_account_runs':0}
bind(__file__);(O/'E0_SOURCE_SHA256.json').write_text(json.dumps(sha,indent=2)+'\n');(O/'E0_EVIDENCE_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False),flush=True)
