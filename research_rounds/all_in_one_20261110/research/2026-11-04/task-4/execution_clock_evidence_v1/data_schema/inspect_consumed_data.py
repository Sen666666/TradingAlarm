"""Read actual bound manifests, schemas and two tiny historical samples only.

Never import or call any Market, model, indicator, Runner, Account or backtest.
"""
from pathlib import Path
import hashlib,json,math,re
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
SOURCE={};EXCERPTS=[]
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SOURCE[str(p)]=h.hexdigest();return p
def readj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,(pd.Timestamp,)):return x.isoformat()
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return[clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(name,x):(OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def excerpt(name,p,first,last):
 p=bind(p);target=OUT/'snippets'/(name+'.py.txt');target.parent.mkdir(exist_ok=True,parents=True);s=''.join(p.read_text().splitlines(keepends=True)[first-1:last]);target.write_text(s)
 EXCERPTS.append(dict(name=name,path=str(p),first_line=first,last_line=last,source_sha256=SOURCE[str(p)],snippet_path=str(target),snippet_sha256=hashlib.sha256(s.encode()).hexdigest(),verbatim=True))

market_manifest=readj(P/'manifest.json');records={r['series_id']:r for r in market_manifest['series']}
stock_manifest_path=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';stock_manifest=readj(stock_manifest_path);stocks={r['symbol']:r for r in stock_manifest}
input_path=R/'a-share-selection-e0-20261024/inputs-v2/input-manifest.json';input_manifest=readj(input_path);selection=readj(input_manifest['selection']['path'])
if 'sha256'in input_manifest['selection']:assert SOURCE[input_manifest['selection']['path']]==input_manifest['selection']['sha256']
freeze=readj(ROOT/'new_price_trend_v1/funding/SOURCE_FREEZE.json')
out=[];chosen=[]
for window,sid,day in [('long','300085.SZ','2024-10-10'),('strong','300666.SZ','2026-01-16')]:
 rec=records[sid];sr=stocks[sid];signal=next(p for p in sr['source_sha256']if p.endswith('/signal.parquet'))
 chosen.append(dict(window=window,sid=sid,execution_record=rec,stock_ref_record=sr))
 for kind,path,expected in [('execution_raw',rec['raw']['path'],rec['raw']['sha256']),('original_numeric_signal',signal,sr['source_sha256'][signal]),('full_I_E0_facts',sr['refs']['facts'],sr['output_sha256'][sr['refs']['facts']])]:
  path=bind(path);assert SOURCE[str(path)]==expected;schema=pq.read_schema(path);frame=pd.read_parquet(path)
  if 'trade_date'in frame:date_values=pd.DatetimeIndex(pd.to_datetime(frame['trade_date']))
  elif 'date'in frame:date_values=pd.DatetimeIndex(pd.to_datetime(frame['date']))
  else:date_values=pd.DatetimeIndex(frame.index)
  selected=frame.loc[date_values==pd.Timestamp(day)]
  observed=frame['observed_at']if'observed_at'in frame else None
  nonempty=observed.astype('string').fillna('').str.strip().ne('')if observed is not None else None
  intraday_columns=[c for c in schema.names if re.search(r'bid|ask|quote|tick|trade_time|datetime|minute|orderbook|last_trade|exchange_time',c,re.I)]
  out.append(dict(window=window,sid=sid,kind=kind,path=str(path),sha256=SOURCE[str(path)],schema=[dict(name=f.name,type=str(f.type),nullable=f.nullable)for f in schema],pandas_index_metadata=json.loads(schema.metadata[b'pandas'])['index_columns']if schema.metadata and b'pandas'in schema.metadata else None,
   rows=len(frame),date_column='trade_date'if'trade_date'in frame else'date',dates_all_midnight=bool((date_values==date_values.normalize()).all()),date_count_unique=len(date_values.unique()),has_duplicate_date=bool(date_values.has_duplicates),date_timezone=str(date_values.tz),sample_day=day,sample=selected.reset_index().to_dict('records'),
   observed_at_field_present=observed is not None,observed_at_nonempty_rows=None if observed is None else int(nonempty.sum()),observed_at_nonempty_examples=[]if observed is None else observed.loc[nonempty].astype(str).drop_duplicates().head(3).tolist(),explicit_bid_ask_trade_time_minute_columns=intraday_columns,
   scope='Schema+source sample only; daily dates and observed_at strings do not by themselves certify quote availability time.'))
save('ACTUAL_INPUT_SCHEMA_AND_SAMPLES.json',out)
save('ACTUAL_MANIFEST_BINDINGS.json',dict(actual_context_source=str(W/'mainline-I-quarter-2025Q3-20261031/adapter.py'),context_record_override='context57-59 replaces inherited bundle records with prepared20261030 manifest before FastMarket construction',prepared_manifest=str(P/'manifest.json'),prepared_manifest_sha256=SOURCE[str(P/'manifest.json')],selected_records=chosen,
 inherited_input_manifest=dict(path=str(input_path),sha256=SOURCE[str(input_path)],research_basis=input_manifest.get('research_basis'),scope_date=input_manifest.get('scope_date'),selection=input_manifest['selection']),
 selection_header={k:v for k,v in selection.items()if k!='lines'},
 original_completed_run_source_freeze=str(ROOT/'new_price_trend_v1/funding/SOURCE_FREEZE.json'),original_completed_run_freeze_sha256=SOURCE[str(ROOT/'new_price_trend_v1/funding/SOURCE_FREEZE.json')],known_windows=freeze['windows'],limitation='This binds the actual completed long/strong source wiring and two sample stocks, not all files in the repository.'))

snippet_specs=[
 ('actual_window_loader',ROOT/'new_price_trend_v1/funding/input_loader.py',12,58),
 ('actual_context_raw_record_override',W/'mainline-I-quarter-2025Q3-20261031/adapter.py',9,14),
 ('actual_context_constructs_FastMarket',W/'mainline-I-quarter-2025Q3-20261031/adapter.py',54,68),
 ('actual_fast_market_base_import',R/'temperature-sizing-20261026/code/common.py',6,12),
 ('actual_fast_market_quote_window',R/'temperature-sizing-20261026/code/fast_market.py',8,67),
 ('native_reader_daily_only',R/'rs-h1-execution-20261025/code/current_pool_bridge.py',69,106),
 ('native_quote_clock_construction',R/'ix-a-share-entry-20261025/code/multi_runner.py',182,243),
 ('native_daily_fill_window',R/'ix-a-share-entry-20261025/code/multi_runner.py',258,310),
 ('fact_observed_at_is_derived_clock',R/'rs-h1-execution-20261025/code/current_pool_bridge.py',298,348),
 ('initial_manifest_declared_close_time',R/'rs-h1-execution-20261025/code/build_inputs.py',44,51),
 ('selection_observed_at_is_snapshot',R/'rs-h1-execution-20261025/code/build_inputs.py',65,72),
 ('DecisionQuote_and_FillWindow_fields',R/'rs-h1-execution-20261025/code/sector_account.py',158,223),
 ('actual_OPEN_preview_and_funding',W/'case-stage-ledger-20261031/v3/joint_v3.py',302,324),
]
for args in snippet_specs:excerpt(*args)
rules_path=R/'pvr-act-comparison-20261027/execution-rules-v2.json';rules=readj(rules_path)
protocol_path=R/'a-share-selection-e0-20261024/inputs-v2/economic-protocol.json';protocol=readj(protocol_path)
save('DECLARED_CLOCK_AND_EXECUTION_PROTOCOL.json',dict(close_available_time_by_sample={r['series_id']:r['close_available_time']for r in records.values()if r['series_id']in['300085.SZ','300666.SZ']},rules_path=str(rules_path),rules_sha256=SOURCE[str(rules_path)],calendar_basis=rules.get('calendar_basis'),calendar_first={k:v[:2]for k,v in rules['calendars'].items()},decision_cutoff_first=rules['decision_cutoffs'][:2],
 protocol_path=str(protocol_path),protocol_sha256=SOURCE[str(protocol_path)],selected_protocol_fields={k:protocol[k]for k in ['daily_execution','participation_rate','sellable_lag_sessions','settlement_lag_sessions']if k in protocol},
 interpretation='These are explicit research clock/execution declarations. Known_at from Date+15:05 and event.at from supplied09:30 session are not provider trade/quote timestamps.'))
save('SOURCE_SNIPPET_INDEX.json',EXCERPTS);SOURCE[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SOURCE_SHA256.json',SOURCE)
save('SCOPE.json',dict(status='ACTUAL_BOUND_INPUT_SCHEMA_READ_COMPLETE',sample_stocks=2,parquet_files_read=6,source_snippets=len(EXCERPTS),new_market_or_account_instances=0,new_models_or_indicators=0,new_backtests_or_builds=0,new_quotes_fetched=0,originals_modified=False,claim_scope='Only these actual long/strong input manifests, two source-stock schemas/samples, and effective quote/window code; no claim that the entire repository has no minute data.'))
print(json.dumps([dict(sid=r['sid'],kind=r['kind'],rows=r['rows'],all_daily=r['dates_all_midnight'],observed_nonempty=r['observed_at_nonempty_rows'],observed_examples=r['observed_at_nonempty_examples'],intraday_columns=r['explicit_bid_ask_trade_time_minute_columns'])for r in out],ensure_ascii=False))
