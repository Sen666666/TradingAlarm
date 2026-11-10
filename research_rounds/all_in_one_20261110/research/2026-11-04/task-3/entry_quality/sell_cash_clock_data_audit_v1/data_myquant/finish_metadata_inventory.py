"""Read-only bounded metadata/small key-column audit. No provider imports/API calls."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,sqlite3
import pyarrow.parquet as pq

R=Path('/Users/bytedance/repos/my-quant'); O=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[]
rels=[
 'README.md','pyproject.toml','docs/data-foundation.md','docs/a-share-factor-data-foundation.md','docs/external-factor-data-catalog.md',
 'src/my_quant/data/sources/__init__.py','src/my_quant/data/builders/a_share_history/consolidate.py','src/my_quant/data/builders/a_share_history/planner.py','src/my_quant/data/adjustments.py',
 'data/meta/runs/daily_bars_20260516T022631Z.json',
 'data/meta/runs/limit_prices/limit_prices_20260515.json',
 'data/meta/runs/suspend_status/suspend_status_20200312_sample.json',
 'data/meta/runs/adjustment_factors/adjustment_factors_20260517_backfilled.json',
 'data/meta/runs/adjusted_daily_bars_adjusted_daily_bars_qfq_20260517.json',
 'data/meta/runs/security_memberships_20260516T073635Z_security_memberships.json',
 'data/meta/schemas/daily_bars_20260516T022631Z.json',
 'data/meta/schemas/security_memberships_20260516T073635Z_security_memberships.json',
]
metadata=[]
safe={'source','domain','dataset','interface','manifest_type','created_at','pulled_at','row_count','run_id','schema_version','transform_version','complete','blocking_jobs','first_trade_date','last_trade_date','symbol_count','trade_date_count','requested_range','retention_days','kind','output_path'}
for family in ['daily_bars','limit_prices','suspend_status','adjustment_factors']:
 p=next(iter(sorted((R/'data/meta/pulls/tushare/a_share'/family).glob('*.json'))),None)
 if p: rels.append(str(p.relative_to(R)))
for rel in rels:
 p=R/rel;st=p.stat();inputs.append({'path':str(p),'bytes':st.st_size,'sha256':sha(p),'mtime_ns':st.st_mtime_ns})
 if p.suffix=='.json':
  d=json.loads(p.read_text()); out={k:v for k,v in d.items()if k in safe}
  if isinstance(d.get('input_paths'),list):out['input_path_count']=len(d['input_paths'])
  metadata.append({'path':str(p),'top_level_key_names':list(d),'selected_safe_fields':out})

small=[]
for rel,cols,keys in [
 ('data/processed/factors/limit_prices/limit_prices.parquet',['symbol','trade_date','pre_close','up_limit','down_limit'],['symbol','trade_date']),
 ('data/processed/factors/suspend_status/suspend_status.parquet',['symbol','trade_date','is_suspended','is_resumed','suspend_event_count','suspend_timing','suspend_types'],['symbol','trade_date']),
 ('data/processed/security_memberships/security_memberships.parquet',['symbol','effective_start_date','snapshot_date','observed_at','known_from','as_of','pit_status','lookahead_risk'],None),
 ('data/processed/industry_taxonomy/industry_taxonomy.parquet',['observed_at','known_from','snapshot_date'],None),
]:
 p=R/rel;pf=pq.ParquetFile(p);assert pf.metadata.num_rows<20000
 frame=pf.read(columns=cols).to_pandas();out={'path':str(p),'rows':len(frame),'columns_read':cols,'null_counts':{c:int(frame[c].isna().sum())for c in cols}}
 if keys:out.update(unique_keys=int(len(frame[keys].drop_duplicates())),duplicate_key_rows=int(frame.duplicated(keys,keep=False).sum()))
 for c in ['is_suspended','is_resumed','suspend_types','pit_status','lookahead_risk']:
  if c in frame:out[c+'_counts']={str(k):int(v)for k,v in frame[c].value_counts(dropna=False).items()}
 for c in ['observed_at','known_from','as_of','snapshot_date']:
  if c in frame:out[c+'_minmax']=[str(frame[c].min()),str(frame[c].max())]
 if 'known_from'in frame and 'observed_at'in frame:
  out['known_from_before_observed_count']=int((frame.known_from<frame.observed_at).sum())
 if 'up_limit'in frame:
  out['non_strict_or_nonpositive_limit_rows_count']=int(((frame.up_limit<=frame.down_limit)|(frame.down_limit<=0)).sum())
  out['nonpositive_bound_semantics']='Predicate only, not a vendor-error verdict: a 0/99999.99 pair may be an unlimited-day sentinel. Meaning not verified from local rights/source metadata.'
  out['non_strict_or_nonpositive_limit_rows']=json.loads(frame.loc[(frame.up_limit<=frame.down_limit)|(frame.down_limit<=0)].to_json(orient='records',date_format='iso'))
  securities=pq.ParquetFile(R/'data/processed/securities/securities.parquet').read(columns=['symbol']).to_pandas()
  known=set(securities.symbol)
  out['key_symbol_in_current_securities_count']=int(frame.symbol.isin(known).sum())
  out['key_symbol_outside_current_securities_count']=int((~frame.symbol.isin(known)).sum())
 small.append(out)

p=R/'data/meta/checkpoints/a_share_history.sqlite';conn=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);conn.execute('PRAGMA query_only=ON')
history={'path':str(p),'read_mode':'ro&immutable=1; query_only','artifact_row_count_distribution':[{ 'row_count':int(c),'artifacts':n}for c,n in conn.execute('SELECT row_count,COUNT(*) FROM artifacts GROUP BY row_count ORDER BY row_count DESC LIMIT 5')], 'artifacts_at_6000':conn.execute('SELECT COUNT(*) FROM artifacts WHERE row_count=6000').fetchone()[0]}
conn.close()

license_names=[str(p.relative_to(R))for p in R.iterdir()if re.search(r'^(licen[sc]e|copying|notice)(\.|$)',p.name,re.I)]
evidence={
 'repo':str(R),'scope':'data/raw,processed,meta,external; bounded canonical footer reads; selected small tables only',
 'no_network_or_api':True,'no_refresh_backtest_or_strategy_execution':True,'no_credentials_values_read':True,
 'source_manifest':inputs,'selected_metadata':metadata,'small_table_quality_checks':small,'history_control_check':history,
 'timestamps':{'trade_date':'session/date label, not exact event/publication or executable quote time','pulled_at':'local collection time, not historical source publication time','created_at':'local processing/manifest write time','observed_at_known_from_as_of':'membership provenance fields; quality flags and chronology are retained, not promoted to historical market-data publication proof'},
 'rights':{'status':'UNKNOWN','root_license_copying_notice_files':license_names,'local_statement':'README describes meta as authorized metadata but contains no market-data grant/terms/redistribution scope; selected manifests contain source/interface/collection/retention, no license terms','code_license_is_not_market_data_license':True,'not_checked':'No API account entitlements, website terms, external license confirmation or credential files read'},
 'absence_scope':'No minute/tick/quote/trade/orderbook, daily-ST, CA-event/announcement/pay-date filenames identified in the four inventory roots or execution-clock columns in audited canonical schemas. This is not a scan of the whole computer and not proof those data never existed.',
 'quality_limits':['Daily whole-table duplicate keys/missing sessions and historical delisted-universe completeness not independently rescanned. Current source validates keys but that is code evidence, not a new row-level audit of old files.','Daily dates in footer are global extents, not every-stock or every-date complete coverage.','5517 succeeded daily jobs mean planned tasks completed, not complete exchange history. At-6000 artifact saturation and old requested starts require separate completeness proof. No repair attempted.','Suspension event absence must not be filled as vendor-confirmed tradable. ST/limits/suspensions cannot be reconstructed solely from current names or daily OHLC.','Adjustment factors are not entitlement quantities, availability dates or announcements; qfq reference dates may encode later anchors.','No intraday executable depth, bid queue, quote/trade sequence or actual cash settlement/broker timestamp source was found.'],
}
(O/'METADATA_AND_RIGHTS_EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'small':small,'history':history,'rights':evidence['rights'],'source_count':len(inputs)},ensure_ascii=False,indent=2))
