"""Exact original metadata/source coverage only; no indicators/FSM/account."""
from pathlib import Path
import hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent
BASE=O.parents[1]
COHORT=BASE/'dec2022_authorization_v1/followup_robustness_v1/performance/SEMICONDUCTOR_COHORT_FREEZE.json'
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
START='2025-01-01';END='2026-06-30'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
cohort=json.loads(COHORT.read_text());m={r['symbol']:r for r in json.loads(MANIFEST.read_text())};members=cohort['all_metadata_members'];sids=[r['sid'] for r in members]
assert len(sids)==len(set(sids))==126 and set(sids)<=set(m)
src={str(COHORT):sha(COHORT),str(MANIFEST):sha(MANIFEST)}
for p,h in cohort['source_sha256'].items():assert sha(p)==h;src[p]=h
save('COHORT126_FIXED.json',dict(definition='Exact frozen current industry == 半导体, no trade/winner/profit selection; intersection with canonical1709 before signal computation.',members=members,metadata_non_PIT=True,IPO_date_authoritative_source_absent=True,window=[START,END],source_sha256=src))
index=[]
for a in members:
 sid=a['sid'];r=m[sid];row=dict(sid=sid,name=a['name'],industry=a['industry'],sector=a['sector'],original_manifest_status=r['status'],cache_through=r.get('cache_through'),metadata_non_PIT=True)
 if r['status']!='complete':
  row.update(status='NO_LOCAL_OBSERVATION_BY_END_NOT_A_NEGATIVE',raw_CP_receipts=0,window_price_observations=0,source_refs=r.get('refs'),source_warm_from=r.get('warm_from'));index.append(row);continue
 paths={k:Path(r['refs'][k]) for k in ['CP1','CP1_input','facts']};sp=Path(next(p for p in r['source_sha256'] if p.endswith('/signal.parquet')));ep=Path(next(p for p in r['source_sha256'] if p.endswith('/events.parquet')));paths.update(price=sp,events=ep)
 for k,p in paths.items():
  expected=r['source_sha256'][str(p)] if k in ['price','events'] else r['output_sha256'][str(p)];actual=sha(p);assert actual==expected,(sid,k,'original hash mismatch');src[str(p)]=actual
 pfull=pd.read_parquet(sp);cfull=pd.read_parquet(paths['CP1']);qfull=pd.read_parquet(paths['CP1_input']);ev=pd.read_parquet(ep)
 assert pfull.index.is_unique and pfull.index.is_monotonic_increasing and cfull.index.is_unique
 p=pfull.loc[:END];cp=cfull.loc[:END];q=qfull.loc[:END];w=p.loc[START:END];cw=cp.loc[START:END];qw=q.loc[START:END]
 assert cp.index.as_unit('ns').equals(q.index.as_unit('ns')),(sid,'CP/input fixed cutoff observations differ')
 assert not p.empty
 required=['price_eligible','observed_bar','synthetic_event_bar','source_invalid'];unknownflags={k:int(p[k].isna().sum()) if k in p else len(p) for k in required}
 finite=p[['high','low','close']].notna().all(axis=1)&p[['high','low','close']].gt(0).all(axis=1)
 valid=finite&p['price_eligible'].eq(True)&p['observed_bar'].eq(True)&p['synthetic_event_bar'].eq(False)&p['source_invalid'].eq(False)&p.high.ge(p.low)&p.high.ge(p.close)&p.close.ge(p.low)
 vw=valid.loc[START:END]
 y25=cp.loc['2025-01-01':'2025-12-31'];h26=cp.loc['2026-01-01':'2026-06-30']
 p25=p.loc['2025-01-01':'2025-12-31'];p26=p.loc['2026-01-01':'2026-06-30']
 shared=p.index.intersection(q.index);assert (p.loc[shared,'close'].to_numpy()==q.loc[shared,'close'].to_numpy()).all()
 row.update(status='SOURCE_COMPLETE_COVERAGE_CHECKED',source_paths={k:str(v) for k,v in paths.items()},source_sha256={str(v):src[str(v)] for v in paths.values()},full_price_first_day=str(p.index[0].date()),full_price_last_by_cutoff=str(p.index[-1].date()),full_price_rows_by_cutoff=len(p),price_file_physical_last=str(pfull.index[-1].date()),CP_file_physical_last=str(cfull.index[-1].date()) if len(cfull) else None,CP_first_day=str(cp.index[0].date()) if len(cp) else None,CP_last_by_cutoff=str(cp.index[-1].date()) if len(cp) else None,CP_full_rows_by_cutoff=len(cp),window_price_observations=len(w),window_valid_HLC_observations=int(vw.sum()),window_CP_observations=len(cw),raw_CP_receipts=int(cw.receipt.sum()),CP_ready_observations=int(cw.ready.sum()),CP_receipts_2025=int(y25.receipt.sum()),CP_receipts_2026H1=int(h26.receipt.sum()),price_rows_2025=len(p25),price_rows_2026H1=len(p26),observed_start_inside_window=str(p.index[0].date())>=START,last_observed_before_window_end=str(p.index[-1].date())<END,explicit_IPO_date=None,IPO_coverage_limit='First observed source date is not certified listing date.',source_unknown_boolean_flags=unknownflags,full_source_invalid_rows=int(p.source_invalid.eq(True).sum()),full_synthetic_rows=int(p.synthetic_event_bar.eq(True).sum()),window_CP_input_rows_missing_from_price=int((~qw.index.isin(w.index)).sum()),window_price_rows_not_in_CP=int((~w.index.isin(qw.index)).sum()),price_adjustment_units='Prepared O/H/L/C same comparable adjustment coordinate; raw_* and factor retained.',explicit_halt_limit_tick_bidask_flags=False)
 index.append(row)
 print(json.dumps(dict(sid=sid,CP_window=row['raw_CP_receipts'],price_window=len(w))),flush=True)
save('COVERAGE126_INPUT_INDEX.json',index)
complete=[r for r in index if r['status']=='SOURCE_COMPLETE_COVERAGE_CHECKED'];na=[r for r in index if r['status']!='SOURCE_COMPLETE_COVERAGE_CHECKED']
summary=dict(status='FULL_METADATA_COHORT_SOURCE_PREPARATION_ONLY',window=[START,END],fixed_metadata_members=126,in_canonical1709=126,complete_sources=len(complete),no_local_observation=len(na),no_local_members=[dict(sid=r['sid'],name=r['name'],status=r['status']) for r in na],source_late_start_members=[dict(sid=r['sid'],name=r['name'],first_observed=r['full_price_first_day'],window_CP=row['raw_CP_receipts']) for r in complete for row in [r] if r['observed_start_inside_window']],window_CP_receipts=sum(r['raw_CP_receipts'] for r in complete),CP_receipts_2025=sum(r['CP_receipts_2025'] for r in complete),CP_receipts_2026H1=sum(r['CP_receipts_2026H1'] for r in complete),window_CP_observations=sum(r['window_CP_observations'] for r in complete),window_price_observations=sum(r['window_price_observations'] for r in complete),window_valid_HLC_observations=sum(r['window_valid_HLC_observations'] for r in complete),actual_CP_physical_end_counts={d:sum(r['CP_file_physical_last']==d for r in complete) for d in sorted({r['CP_file_physical_last'] for r in complete})},canonical_manifest_cache_through_counts={d:sum(r['cache_through']==d for r in complete) for d in sorted({r['cache_through'] for r in complete})},full_unknown_boolean_rows=sum(sum(r['source_unknown_boolean_flags'].values()) for r in complete),limitations=['Current metadata classification is not historical PIT constituents.','No local observation is not a negative or failed signal.','First observed date is not authoritative IPO/listing date.','No certified trading-session/halt/limit/ST/tick/bidask or received-at feed.','Physical source may extend beyond chosen cutoff; all computation will cut to2026Jun30; no 2026H2 claims.'],source_sha256=src,script_sha256=sha(__file__),new_FSM_runs=0,new_indicators=0,new_accounts=0,new_quantities=0,new_returns=0)
save('COVERAGE126_SUMMARY.json',summary)
print(json.dumps({k:summary[k] for k in ['fixed_metadata_members','complete_sources','no_local_observation','window_CP_receipts','CP_receipts_2025','CP_receipts_2026H1','window_price_observations','window_valid_HLC_observations','actual_CP_physical_end_counts','canonical_manifest_cache_through_counts']}),flush=True)
