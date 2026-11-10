"""Read-only sealing of already completed files after a wrong empty-count gate.

Never calls compute_features, writes Parquet, reads PnL, or creates labels/accounts.
The failed exporter and original data files remain byte-for-byte unchanged.
"""
from pathlib import Path
from collections import Counter,defaultdict
import importlib.util,json,hashlib,time,signal,math
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.compute as pc,pyarrow.parquet as pq
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('completed_feature_export_reader',O/'export_features.py');X=importlib.util.module_from_spec(spec);spec.loader.exec_module(X)
def sum_bool(col):return int(pc.sum(col).as_py()or 0)
def same_float(a,b):return np.array_equal(np.asarray(a,float),np.asarray(b,float),equal_nan=True)
def main():
 started=time.monotonic();out=O/'FEATURE_MANIFEST_PRE_LABEL.json';assert not out.exists()
 def alarm(*_):raise TimeoutError('Readonly export finalization exceeded60seconds; no automatic retry')
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,60)
 src={};start=X.load(O/'RUN_STARTED.json',src);stopped=X.load(O/'EXPORT_STOPPED.json',src);small=X.load(O/'SMALL_SAMPLE_EXPORT_CHECKS.json',src)
 assert stopped['progress']['stage']=='seal_pre_label_manifest'and stopped['progress']['completed_stocks']==1709 and stopped['progress']['completed_industries']==90
 assert stopped['error']=='AssertionError()'and stopped['elapsed_seconds']<=120
 for p,h in start['source_sha256'].items():assert X.sha(p)==h,('changed frozen source',p)
 assert small['exporter_sha256']==start['source_sha256'][str((O/'export_features.py').resolve())]
 # Pin the exact original assertion. Its first two clauses are rechecked below;
 # only the false full-history-empty-stock count prevented the original seal.
 original=(O/'export_features.py').read_text();needle="assert count['stock_days']==1709*968 and count['ranklog_queries_checked']==sum(qcounts.values())and count['empty_signal_symbols']==22";assert original.count(needle)==1
 sm=X.load(X.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',src);im=X.load(X.W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',src);meta=X.load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json',src)
 dates,windows,cals=X.calendars(src);daystrings=list(dates.strftime('%Y-%m-%d'));offset={(win,d):i for i,(win,d)in enumerate(zip(windows,daystrings))};queries,qcounts=X.ranklog_queries(src)
 fpath=O/'features.parquet';qpath=O/'reference_quotes.parquet';fsha=X.sha(fpath);qsha=X.sha(qpath);f=pq.ParquetFile(fpath);q=pq.ParquetFile(qpath)
 assert f.metadata.num_rows==q.metadata.num_rows==1654312 and f.num_row_groups==q.num_row_groups==1709
 assert f.schema_arrow.equals(X.feature_schema(),check_metadata=False)and q.schema_arrow.equals(X.QUOTE_SCHEMA,check_metadata=False)
 counts=Counter();statuses=defaultdict(Counter);empty_stocks=[];empty_industries=[];window_empty_stocks=[];window_empty_industries=[];source_rows={}
 for r in im:
  path,h=X.signal_path(r);assert X.sha(path)==h;src[str(path)]=h;n=pq.read_metadata(path).num_rows;source_rows[r['series']]=n
  if n==0:empty_industries.append(r['series'])
  ix=pd.read_parquet(path,columns=[]).index
  if not dates.isin(ix).any():window_empty_industries.append(r['series'])
 for j,r in enumerate(sm):
  sid=r['symbol'];ft=f.read_row_group(j);qt=q.read_row_group(j)
  assert ft.num_rows==qt.num_rows==968
  for tab in [ft,qt]:
   assert pc.all(pc.equal(tab['sid'],sid)).as_py()and tab['day'].to_pylist()==daystrings and tab['window'].to_pylist()==windows
  assert pc.all(pc.equal(ft['sector'],meta[sid]['sector_id'])).as_py()
  assert ft['pvr_valid_observation'].combine_chunks().equals(qt['valid'].combine_chunks())and ft['pvr_clock_block'].combine_chunks().equals(qt['block'].combine_chunks())
  path,h=X.signal_path(r);assert X.sha(path)==h;src[str(path)]=h;raw=pd.read_parquet(path);source_rows[sid]=len(raw)
  if raw.empty:empty_stocks.append(sid)
  if not sum_bool(ft['stock_source_row_present']):window_empty_stocks.append(sid)
  rawgrid=raw.reindex(dates);assert same_float(qt['open'].to_numpy(),rawgrid.open.to_numpy())and same_float(qt['close'].to_numpy(),rawgrid.close.to_numpy())
  # Only the original mask/block predicate is checked; no rolling feature or
  # future-return recomputation occurs during this finalization.
  valid,block=X.API.original_observation_clock(raw);expected_valid=valid.reindex(dates).fillna(False).to_numpy(bool)
  assert np.array_equal(qt['valid'].to_numpy(),expected_valid)
  expected_block=block.reindex(dates).to_numpy(float,na_value=np.nan);assert same_float(qt['block'].to_numpy(),expected_block)
  observed=pd.Series(True,index=raw.index,dtype=bool)
  for k in ['observed_bar','is_observed_bar']:
   if k in raw:observed &=raw[k].fillna(False).astype(bool)
  if 'synthetic_event_bar'in raw:observed &=~raw.synthetic_event_bar.fillna(True).astype(bool)
  assert np.array_equal(qt['observed'].to_numpy(),observed.reindex(dates).fillna(False).to_numpy(bool))
  values=ft['score'].to_numpy()
  for win,d,ready,value in queries.get(sid,[]):
   got=float(values[offset[win,d]]);assert math.isfinite(got)==ready
   if ready:assert np.float64(got).view(np.uint64)==np.float64(value).view(np.uint64)
   else:assert value is None or not math.isfinite(float(value))
   counts['ranklog_queries_checked']+=1;counts['ranklog_ready_bitexact'if ready else'ranklog_UNKNOWN_exact']+=1
  counts['stock_days']+=968;counts['stock_source_rows_present']+=sum_bool(ft['stock_source_row_present']);counts['reference_observed']+=sum_bool(qt['observed']);counts['reference_valid_PVR_domain']+=sum_bool(qt['valid']);counts['PVR_known_stockdays']+=int(np.isfinite(values).sum())
  for k in [k for k in ft.column_names if k.endswith('_status')]:
   for z in pc.value_counts(ft[k]).to_pylist():statuses[k][str(z['values'])]+=int(z['counts'])
 assert counts['stock_days']==1709*968 and counts['ranklog_queries_checked']==sum(qcounts.values())==133713
 assert counts['ranklog_ready_bitexact']==133542 and counts['ranklog_UNKNOWN_exact']==171 and len(empty_stocks)==0 and len(empty_industries)==22
 for k,v in counts.items():assert stopped['counts'][k]==v,('original completed counters mismatch',k,v)
 assert stopped['counts']['empty_signal_symbols']==0
 for p,h in start['source_sha256'].items():assert X.sha(p)==h
 assert X.sha(fpath)==fsha and X.sha(qpath)==qsha
 counts['empty_signal_symbols']=len(empty_stocks);counts['empty_stock_full_history_signals']=len(empty_stocks);counts['empty_industry_full_history_signals']=len(empty_industries);counts['stock_no_source_row_on_export_calendar']=len(window_empty_stocks);counts['industry_no_source_row_on_export_calendar']=len(window_empty_industries)
 src.update(start['source_sha256']);src[str(Path(__file__).resolve())]=X.sha(__file__)
 outputs={name:dict(path=str(path.resolve()),sha256=h,rows=pf.metadata.num_rows,row_groups=pf.num_row_groups)for name,path,h,pf in [('features.parquet',fpath,fsha,f),('reference_quotes.parquet',qpath,qsha,q)]}
 note=dict(status='COMPLETED_EXPORT_ONLY_FINAL_EMPTY_STOCK_ASSERTION_WAS_WRONG',exact_failed_assertion=needle,confirmed_true_clauses=['stock_days==1709*968','ranklog_queries_checked==sum(qcounts.values())'],false_clause="empty_signal_symbols==22; that counter counts full-history stock source emptiness and is0",correct_counts=dict(empty_full_history_stock_signals=0,empty_full_history_industry_signals=22),original_STOPPED_preserved=True,exporter_and_Parquet_unchanged=True,no_feature_recomputation=True,no_Parquet_reexport=True,no_labels=True,new_accounts=0)
 manifest=dict(status='COMPLETE_PURE_FEATURE_EXPORT_BEFORE_ANY_LABEL_OR_PNL',feature_source_sha256=X.sha(X.F),exporter_sha256=X.sha(O/'export_features.py'),finalizer_sha256=X.sha(__file__),source_sha256=src,calendars=cals,windows={w:dict(days=len(ds),stock_day_rows=len(ds)*1709)for w,ds in cals.items()},counts=dict(counts),ranklog_queries_by_window=qcounts,status_counts={k:dict(v)for k,v in statuses.items()},schema=X.schema_description(),outputs=outputs,elapsed_seconds=stopped['elapsed_seconds'],budget_seconds=120,readonly_finalization_seconds=time.monotonic()-started,readonly_finalization_budget_seconds=60,stock_symbols=1709,industry_symbols=90,empty_source_ids=dict(full_history_stocks=empty_stocks,full_history_industries=empty_industries,no_export_calendar_row_stocks=window_empty_stocks,no_export_calendar_row_industries=window_empty_industries),completion_note=note,automatic_retry=False,no_future_labels=True,no_original_PnL_imported=True,new_accounts=0,new_market_models=0)
 X.save(O/'COMPLETED_EXPORT_SEAL_AUDIT.json',dict(note,counts=dict(counts),outputs=outputs,source_sha256=src,readonly_seconds=time.monotonic()-started))
 X.save(out,manifest);signal.setitimer(signal.ITIMER_REAL,0)
 print(json.dumps(dict(status=manifest['status'],counts=dict(counts),empty_industries=empty_industries,readonly_seconds=manifest['readonly_finalization_seconds'],manifest_sha256=X.sha(out)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
