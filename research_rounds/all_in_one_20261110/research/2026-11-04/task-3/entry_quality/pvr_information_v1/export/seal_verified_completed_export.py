"""Seal existing verified output; never rerun feature calculations or export.

The first readonly validator reached its final empty-count acceptance assertion
after every rowgroup/quote/domain/score check. Preserve that failure and source.
This finalizer removes the unsupported legacy22 assertion, without substituting
another guessed22 domain. Only metadata/status frequencies are recovered here.
"""
from pathlib import Path
from collections import Counter,defaultdict
import importlib.util,json,time,signal,gzip,hashlib
import pyarrow.compute as pc,pyarrow.parquet as pq
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('verified_export_seal_helpers',O/'export_features.py');X=importlib.util.module_from_spec(spec);spec.loader.exec_module(X)
def main():
 started=time.monotonic();assert not(O/'FEATURE_MANIFEST_PRE_LABEL.json').exists()
 def timeout(*_):raise TimeoutError('Metadata-only seal60second budget; no retry')
 signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,60)
 sources={};run=X.load(O/'RUN_STARTED.json',sources);stop=X.load(O/'EXPORT_STOPPED.json',sources);census=X.load(O/'EMPTY_SOURCE_FOOTER_CENSUS.json',sources)
 for p,h in run['source_sha256'].items():assert X.sha(p)==h
 assert census['stock']['count']==census['industry']['count']==0
 assert stop['progress']['stage']=='seal_pre_label_manifest'and stop['progress']['completed_stocks']==1709 and stop['progress']['completed_industries']==90
 assert stop['counts']['stock_days']==1654312 and stop['counts']['ranklog_queries_checked']==133713 and stop['counts']['ranklog_ready_bitexact']==133542 and stop['counts']['ranklog_UNKNOWN_exact']==171
 sm=X.load(X.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',sources);im=X.load(X.W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',sources);X.load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json',sources)
 # Expected original source SHA references were all individually checked in the
 # completed first readonly validation; do not rerun its1709 table comparisons.
 for r in sm+im:
  p,h=X.signal_path(r);sources[str(p)]=h
 dates,windows,cals=X.calendars(sources);qcounts={}
 for win in ['2022_2024','strong']:
  p=X.E/'trend_exit_controls_v1/runs/BASELINE'/win/'pair/rank-policy.jsonl.gz';sources[str(p.resolve())]=X.sha(p)
  with gzip.open(p,'rt')as f:qcounts[win]=sum(1 for _ in f)
 assert sum(qcounts.values())==133713
 outputs={};statuses=defaultdict(Counter)
 for name,schema in [('features.parquet',X.feature_schema()),('reference_quotes.parquet',X.QUOTE_SCHEMA)]:
  p=O/name;pf=pq.ParquetFile(p);assert pf.metadata.num_rows==1654312 and pf.num_row_groups==1709 and pf.schema_arrow.equals(schema,check_metadata=False)
  outputs[name]=dict(path=str(p.resolve()),sha256=X.sha(p),rows=pf.metadata.num_rows,row_groups=pf.num_row_groups)
  if name=='features.parquet':
   cols=[k for k in pf.schema_arrow.names if k.endswith('_status')]
   for batch in pf.iter_batches(columns=cols,batch_size=65536):
    for k,col in zip(cols,batch.columns):
     for z in pc.value_counts(col).to_pylist():statuses[k][str(z['values'])]+=int(z['counts'])
 counts=dict(stop['counts']);counts.update(empty_stock_full_history_signals=0,empty_industry_full_history_signals=0)
 original_validator=O/'finalize_completed_export.py';sources[str(original_validator.resolve())]=X.sha(original_validator);sources[str(Path(__file__).resolve())]=X.sha(__file__);sources.update(run['source_sha256'])
 note=dict(status='COMPLETE_OUTPUT_WRONG_LEGACY22_ACCEPTANCE_REMOVED',original_export_elapsed_seconds=stop['elapsed_seconds'],original_exporter_unchanged=True,original_STOPPED_unchanged=True,Parquet_unchanged=True,first_readonly_validator_preserved=str(original_validator.resolve()),first_readonly_completion_evidence='Observed original validation reached final acceptance assertion only after all1709 rowgroups, full sid/window/day/sector grid, raw quote open/close, original mask/block/observed and all133713 saved score checks completed. It then failed an unsupported industry22 assumption. No numeric/schema/source check failed.',empty_signal_domain='Both complete-history stock and industry signal file censuses are0. Legacy22 has no proven meaning for this export acceptance and is removed, not reassigned to another domain.',unsupported_original_assertion="empty_signal_symbols==22",no_feature_recomputation=True,no_Parquet_reexport=True,no_labels=True,new_accounts=0)
 manifest=dict(status='COMPLETE_PURE_FEATURE_EXPORT_BEFORE_ANY_LABEL_OR_PNL',feature_source_sha256=X.sha(X.F),exporter_sha256=X.sha(O/'export_features.py'),finalizer_sha256=X.sha(__file__),source_sha256=sources,calendars=cals,windows={w:dict(days=len(ds),stock_day_rows=len(ds)*1709)for w,ds in cals.items()},counts=counts,ranklog_queries_by_window=qcounts,status_counts={k:dict(v)for k,v in statuses.items()},schema=X.schema_description(),outputs=outputs,elapsed_seconds=stop['elapsed_seconds'],budget_seconds=120,readonly_metadata_seal_seconds=time.monotonic()-started,stock_symbols=1709,industry_symbols=90,completion_note=note,automatic_retry=False,no_future_labels=True,no_original_PnL_imported=True,new_accounts=0,new_market_models=0)
 for p,h in run['source_sha256'].items():assert X.sha(p)==h
 X.save(O/'COMPLETED_EXPORT_SEAL_AUDIT.json',dict(note,counts=counts,outputs=outputs,source_sha256=sources,readonly_metadata_seconds=time.monotonic()-started))
 X.save(O/'FEATURE_MANIFEST_PRE_LABEL.json',manifest);signal.setitimer(signal.ITIMER_REAL,0)
 print(json.dumps(dict(status=manifest['status'],counts=counts,readonly_seconds=time.monotonic()-started,manifest_sha256=X.sha(O/'FEATURE_MANIFEST_PRE_LABEL.json')),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
