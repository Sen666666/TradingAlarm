"""Frozen original CP flags -> fixed 20-effective-observation price labels.

Only local immutable parquet/csv reading and arithmetic. No model/account/strategy imports.
"""
from pathlib import Path
import collections,hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
P=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
CUTOFF=pd.Timestamp('2026-10-22')
started=time.monotonic();hashes={};errors=[];sources=[];rows=[];paths=[]
def bind(p,expected=None):
 p=Path(p)
 if str(p) not in hashes:hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert hashes[str(p)]==expected,('source SHA mismatch',str(p))
 return p
def js(p):return json.loads(bind(p).read_text())
def ds(d):return pd.Timestamp(d).strftime('%Y-%m-%d')
def number(a):
 try:v=float(a)
 except (TypeError,ValueError):return None
 return v if math.isfinite(v) else None
def boolean(v):
 return bool(v) if isinstance(v,(bool,np.bool_)) else None
def eqflag(f,k,want):
 if k not in f:return np.zeros(len(f),dtype=bool)
 return f[k].eq(want).fillna(False).to_numpy(dtype=bool)
def val(f,k,i):
 return number(f[k].iloc[i]) if k in f else None

bind(P/'FROZEN_DESIGN.txt')
E=pd.read_csv(bind(P/'universe_audit/CP_EVENT_INDEX_2022_2026H1.csv'),dtype={'sid':str,'date':str,'canonical_receipt_id':str}).fillna({'canonical_receipt_id':''})
assert len(E)==99031 and not E.duplicated(['sid','date']).any()
S={r['symbol']:r for r in js(U/'STOCK_MANIFEST.json')}
cal=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(bind(M),usecols=['date']).date))
assert cal.is_unique and cal.is_monotonic_increasing
required=['close','segment_id','volume','price_eligible','observed_bar','synthetic_event_bar','source_invalid']
for ns,(sid,evs) in enumerate(E.groupby('sid',sort=True),1):
 sm=S[sid];sp=[p for p in sm['source_sha256'] if '/prepared' in p and p.endswith('/signal.parquet')]
 assert len(sp)==1,(sid,sp)
 sp=sp[0];f=pd.read_parquet(bind(sp,sm['source_sha256'][sp])).loc[:CUTOFF]
 assert f.index.is_unique and f.index.is_monotonic_increasing,(sid,'index')
 missing=[k for k in required if k not in f]
 assert not missing,(sid,'required original flags missing',missing)
 fp=sm['refs']['facts'];qp=sm['refs']['CP1_input']
 facts=pd.read_parquet(bind(fp,sm['output_sha256'][fp]),columns=['close','segment_id'])
 qin=pd.read_parquet(bind(qp,sm['output_sha256'][qp]),columns=['close','segment_id'])
 close=pd.to_numeric(f['close'],errors='coerce').to_numpy(dtype=float)
 volume=pd.to_numeric(f['volume'],errors='coerce').to_numpy(dtype=float)
 seg=pd.to_numeric(f['segment_id'],errors='coerce').to_numpy(dtype=float)
 finiteprice=np.isfinite(close)&(close>0);finitevolume=np.isfinite(volume)&(volume>0)
 observed=eqflag(f,'observed_bar',True);priceeligible=eqflag(f,'price_eligible',True)
 nonsynthetic=eqflag(f,'synthetic_event_bar',False);noninvalid=eqflag(f,'source_invalid',False)
 alias_conflict=np.zeros(len(f),dtype=bool)
 if 'is_observed_bar' in f:
  alias_known=f['is_observed_bar'].notna().to_numpy(dtype=bool)&f['observed_bar'].notna().to_numpy(dtype=bool)
  alias_conflict=alias_known&f['is_observed_bar'].ne(f['observed_bar']).fillna(False).to_numpy(dtype=bool)
 eligible=observed&priceeligible&finiteprice&finitevolume&nonsynthetic&noninvalid&~alias_conflict&np.isfinite(seg)
 # Source IDs are respected as contiguous blocks; never select a later repeated ID across a boundary.
 change=np.r_[True,(seg[1:]!=seg[:-1])|~np.isfinite(seg[1:])|~np.isfinite(seg[:-1])]
 block=np.cumsum(change)-1
 block_end=np.r_[np.flatnonzero(change)[1:]-1,len(f)-1]
 valid_byblock={b:np.flatnonzero(eligible&(block==b)) for b in np.unique(block)}
 failure_masks={'unobserved_or_unknown':~observed,'price_ineligible_or_unknown':~priceeligible,'nonpositive_or_unknown_close':~finiteprice,
  'nonpositive_or_unknown_volume':~finitevolume,'synthetic_or_unknown':~nonsynthetic,'source_invalid_or_unknown':~noninvalid,
  'observed_alias_conflict':alias_conflict}
 pref={k:np.r_[0,np.cumsum(v)] for k,v in failure_masks.items()}
 stockaudit={'sid':sid,'prepared_signal_ref':sp,'prepared_signal_sha256':hashes[sp],'source_rows_through_cutoff':len(f),
  'source_first':ds(f.index.min()) if len(f) else None,'source_last':ds(f.index.max()) if len(f) else None,
  'source_segment_blocks':len(block_end),'source_observed_alias_conflict_rows':int(alias_conflict.sum()),'events':len(evs),
  'facts_ref':fp,'CP1_input_ref':qp}
 sources.append(stockaudit)
 for e in evs.to_dict('records'):
  d=pd.Timestamp(e['date']);loc=f.index.get_indexer([d])[0]
  r={'sid':sid,'date':e['date'],'canonical_receipt_id':e['canonical_receipt_id'] or None,
   'canonical_receipt_status':e['canonical_receipt_status'],'audit_event_key':sid+'|'+e['date']+'|'+hashes[sp][:16],
   'source_ref_id':sid,'source_segment':None,'signal_close':None,'signal_eligible':False,
   'signal_close_matches_facts':False,'signal_close_matches_CP_input':False,'signal_segment_matches_facts':False,'signal_segment_matches_CP_input':False,
   'label_valid':False,'label_status':None,'label_end':None,'future_eligible_available_same_segment':0,'actual_days':0,
   'calendar_span_days':None,'common_session_span':None,'common_calendar_complete_through_label_end':None,
   'skipped_source_rows':None,'missing_common_session_rows':None,'source_rows_in_followup_span':None,
   'mfe20_log':None,'mae20_log':None,'final20_log':None,'future_max20_log_unclipped':None,'future_min20_log_unclipped':None,
   'mfe20_arithmetic':None,'mae20_arithmetic':None,'final20_arithmetic':None,
   'mfe20_date':None,'mae20_date':None,'mfe20_observation_number':None,'mae20_observation_number':None,
   'future_max20_unclipped_date':None,'future_min20_unclipped_date':None,
   'last_followup_effective_day':None,'next_common_session':None,'next_session_source_row_present':False,
   'next_session_raw_open':None,'next_session_raw_high':None,'next_session_raw_low':None,'next_session_raw_close':None,'next_session_raw_volume':None,
   'next_session_observed':None,'next_session_price_eligible':None,'next_session_positive_volume':None,
   'next_session_one_price_exact':None,'next_session_synthetic_event_bar':None,'next_session_source_invalid':None,
   'next_session_limit_up_status':None,'next_session_limit_down_status':None,'next_session_suspension_status':None,
   'execution_proven':False,'nonoverlap20':False,'phase':('DEV' if d.year in [2022,2023] else 'V2024' if d.year==2024 else 'V2025' if d.year==2025 else 'V2026H1'),
   'dev_fit_eligible':False,'label_cross_calendar_year':None,'label_within_phase':None}
  for k in failure_masks:r['skipped_'+k]=None
  if loc<0:
   r['label_status']='SIGNAL_SOURCE_ROW_MISSING';errors.append({'sid':sid,'date':e['date'],'error':r['label_status']});rows.append(r);continue
  r['source_segment']=int(seg[loc]) if np.isfinite(seg[loc]) else None
  r['signal_close']=number(close[loc]);r['signal_eligible']=bool(eligible[loc])
  for table,fr in [('facts',facts),('CP_input',qin)]:
   if d in fr.index:
    r['signal_close_matches_'+table]=bool(fr.at[d,'close']==close[loc])
    r['signal_segment_matches_'+table]=bool(fr.at[d,'segment_id']==seg[loc])
  coordinate_ok=all(r[k] for k in ['signal_close_matches_facts','signal_close_matches_CP_input','signal_segment_matches_facts','signal_segment_matches_CP_input'])
  if not coordinate_ok:errors.append({'sid':sid,'date':e['date'],'error':'SIGNAL_COORDINATE_MISMATCH','signal_close':number(close[loc]),'facts_close':number(facts.at[d,'close']) if d in facts.index else None,'CP_input_close':number(qin.at[d,'close']) if d in qin.index else None})
  # Raw next common-session description is not the first effective observation and never guarantees a fill.
  nc=cal.searchsorted(d,side='right')
  if nc<len(cal):
   nd=cal[nc];r['next_common_session']=ds(nd);nl=f.index.get_indexer([nd])[0]
   if nl>=0:
    r['next_session_source_row_present']=True
    for field in ['open','high','low','close','volume']:r['next_session_raw_'+field]=val(f,'raw_'+field,nl)
    for field,out in [('observed_bar','observed'),('price_eligible','price_eligible'),('synthetic_event_bar','synthetic_event_bar'),('source_invalid','source_invalid')]:
     r['next_session_'+out]=boolean(f[field].iloc[nl]) if field in f else None
    rv=r['next_session_raw_volume'];r['next_session_positive_volume']=rv>0 if rv is not None else None
    ohlc=[r['next_session_raw_'+k] for k in ['open','high','low','close']]
    r['next_session_one_price_exact']=(min(ohlc)>0 and len(set(ohlc))==1) if all(v is not None for v in ohlc) else None
    for field,out in [('limit_up','limit_up_status'),('limit_down','limit_down_status'),('suspend_status','suspension_status')]:
     if field in f:r['next_session_'+out]=None if pd.isna(f[field].iloc[nl]) else str(f[field].iloc[nl])
  b=int(block[loc]);vend=int(block_end[b]);vi=valid_byblock[b];future=vi[np.searchsorted(vi,loc,side='right'):]
  chosen=future[:20];r['future_eligible_available_same_segment']=len(future);r['actual_days']=len(chosen)
  if len(chosen):r['last_followup_effective_day']=ds(f.index[chosen[-1]])
  follow_end=int(chosen[-1]) if len(chosen)==20 else vend
  r['source_rows_in_followup_span']=follow_end-loc
  r['skipped_source_rows']=(follow_end-loc)-int(eligible[loc+1:follow_end+1].sum())
  for k,prefv in pref.items():r['skipped_'+k]=int(prefv[follow_end+1]-prefv[loc+1])
  end_date=f.index[follow_end]
  cd=cal[(cal>d)&(cal<=end_date)]
  r['missing_common_session_rows']=int((~cd.isin(f.index[loc+1:follow_end+1])).sum())
  if not coordinate_ok:r['label_status']='SIGNAL_COORDINATE_MISMATCH'
  elif not eligible[loc]:r['label_status']='SIGNAL_BASE_INELIGIBLE'
  elif len(chosen)<20:r['label_status']='SOURCE_SEGMENT_BOUNDARY_BEFORE20' if vend<len(f)-1 else 'SOURCE_END_BEFORE20'
  else:
   ds20=f.index[chosen];qs=np.log(close[chosen]/close[loc]);mmax=int(np.argmax(qs));mmin=int(np.argmin(qs));qmax=float(qs[mmax]);qmin=float(qs[mmin])
   mfe=max(0.,qmax);mae=min(0.,qmin);final=float(qs[-1]);le=ds20[-1]
   r.update(label_valid=True,label_status='COMPLETE20',label_end=ds(le),calendar_span_days=int((le-d).days),
    common_calendar_complete_through_label_end=bool(le<=cal.max()),common_session_span=int(((cal>d)&(cal<=le)).sum()) if le<=cal.max() else None,
    mfe20_log=mfe,mae20_log=mae,final20_log=final,future_max20_log_unclipped=qmax,future_min20_log_unclipped=qmin,
    mfe20_arithmetic=float(np.expm1(mfe)),mae20_arithmetic=float(np.expm1(mae)),final20_arithmetic=float(np.expm1(final)),
    mfe20_date=ds(d if qmax<0 else ds20[mmax]),mae20_date=ds(d if qmin>0 else ds20[mmin]),
    mfe20_observation_number=0 if qmax<0 else mmax+1,mae20_observation_number=0 if qmin>0 else mmin+1,
    future_max20_unclipped_date=ds(ds20[mmax]),future_min20_unclipped_date=ds(ds20[mmin]),
    label_cross_calendar_year=bool(d.year!=le.year),label_within_phase=bool(le<=pd.Timestamp('2023-12-31' if r['phase']=='DEV' else '2024-12-31' if r['phase']=='V2024' else '2025-12-31' if r['phase']=='V2025' else '2026-06-30')),
    dev_fit_eligible=bool(r['phase']=='DEV' and le<=pd.Timestamp('2023-12-31')))
   paths.append({'sid':sid,'date':e['date'],'future_dates':[ds(t) for t in ds20],'future_close':close[chosen].tolist(),'future_logchanges':qs.tolist()})
  rows.append(r)
 if ns%200==0:print('PROGRESS',ns,'stocks',len(rows),'labels','seconds',round(time.monotonic()-started,2),flush=True)

L=pd.DataFrame(rows).sort_values(['date','sid']).reset_index(drop=True)
assert len(L)==len(E)==99031 and not L.duplicated(['sid','date']).any()
assert set(zip(L.sid,L.date))==set(zip(E.sid,E.date))
for sid,g in L.groupby('sid',sort=False):
 previous_end=None
 for idx in g.sort_values('date').index:
  if bool(L.at[idx,'label_valid']) and (previous_end is None or L.at[idx,'date']>previous_end):
   L.at[idx,'nonoverlap20']=True;previous_end=L.at[idx,'label_end']
assert L.loc[~L.label_valid,['mfe20_log','mae20_log','final20_log']].isna().all().all()
assert (L.loc[L.label_valid,'actual_days']==20).all()
assert (L.loc[L.label_valid,'mfe20_log']>=0).all() and (L.loc[L.label_valid,'mae20_log']<=0).all()
assert (L.loc[L.label_valid,'final20_log']<=L.loc[L.label_valid,'mfe20_log']+1e-15).all()
assert (L.loc[L.label_valid,'final20_log']>=L.loc[L.label_valid,'mae20_log']-1e-15).all()
L.to_parquet(O/'LABELS.parquet',index=False)
L.to_csv(O/'LABELS.csv',index=False)
pd.DataFrame(paths).to_parquet(O/'LABEL_PATHS.parquet',index=False)
pd.DataFrame(sources).to_csv(O/'SOURCE_BINDINGS.csv',index=False)
L[['sid','date','label_end','label_valid','nonoverlap20']].to_csv(O/'NONOVERLAP20.csv',index=False)
summary={'events':len(L),'distinct_stocks':int(L.sid.nunique()),'label_valid':int(L.label_valid.sum()),'label_status':dict(collections.Counter(L.label_status)),
 'canonical_ID_missing':int(L.canonical_receipt_id.isna().sum()),'nonoverlap20_count':int(L.nonoverlap20.sum()),'dev_fit_eligible':int(L.dev_fit_eligible.sum()),
 'coordinate_mismatch_events':len(errors),'source_cutoff':ds(CUTOFF),'source_reference_files':len(sources),'source_SHA_files_checked':len(hashes),
 'next_session_source_missing_events':int((~L.next_session_source_row_present).sum()),'next_session_one_price_exact_events':int(L.next_session_one_price_exact.eq(True).sum()),
 'actual_limit_or_suspension_status_saved_events':int(L[['next_session_limit_up_status','next_session_limit_down_status','next_session_suspension_status']].notna().any(axis=1).sum()),
 'label_crossyear':int(L.label_cross_calendar_year.eq(True).sum()),'label_extending_after2026H1':int((L.label_end.fillna('')>'2026-06-30').sum()),
 'valid_labels_with_skipped_source_rows':int((L.label_valid&L.skipped_source_rows.gt(0)).sum()),
 'valid_labels_with_missing_common_session_rows':int((L.label_valid&L.missing_common_session_rows.gt(0)).sum()),
 'max_valid_calendar_span_days':int(L.loc[L.label_valid,'calendar_span_days'].max()),'reference_calendar_complete_label_count':int(L.common_calendar_complete_through_label_end.eq(True).sum()),
 'features_computed':0,'CP_models_recomputed':0,'account_runs':0,'seconds':time.monotonic()-started}
phase=L.groupby('phase').agg(events=('sid','size'),stocks=('sid','nunique'),label_valid=('label_valid','sum'),nonoverlap20=('nonoverlap20','sum'),dev_fit_eligible=('dev_fit_eligible','sum'))
phase.to_csv(O/'COUNTS_BY_PHASE.csv')
L.assign(month=L.date.str[:7]).groupby('month').agg(events=('sid','size'),stocks=('sid','nunique'),label_valid=('label_valid','sum'),nonoverlap20=('nonoverlap20','sum')).to_csv(O/'COUNTS_BY_MONTH.csv')
(O/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(O/'COORDINATE_ERRORS.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n')
bind(__file__);(O/'SOURCE_SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
print('SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True);print(phase.to_string(),flush=True)
