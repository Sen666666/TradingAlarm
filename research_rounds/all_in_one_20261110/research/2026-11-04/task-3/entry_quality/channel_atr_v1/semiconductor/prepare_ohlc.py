"""Read-only canonical OHLC export; no channel, ATR, account or candidate run."""
from pathlib import Path
import hashlib,json,math
import pandas as pd
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
FIXED=O.parents[1]/'cp_effective_progress_v1/semiconductor/FIXED25_COHORT.json'
RAW_CANONICAL=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
TARGETS={'603061.SH':['2026-01-16','2026-01-19','2026-01-20','2026-01-28','2026-02-12'],'300623.SZ':['2026-01-29','2026-02-02','2026-02-03','2026-02-05','2026-03-04']}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x)
 if x is pd.NA or x is pd.NaT:return None
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
m={r['symbol']:r for r in json.loads(MANIFEST.read_text())};sources={str(MANIFEST):sha(MANIFEST),str(FIXED):sha(FIXED)};coverage=[];targets=[]
for sid,days in TARGETS.items():
 p=Path(next(x for x in m[sid]['source_sha256'] if x.endswith('/signal.parquet')));assert sha(p)==m[sid]['source_sha256'][str(p)];sources[str(p)]=sha(p)
 f=pd.read_parquet(p).loc[:'2026-06-30'].copy();assert f.index.is_unique and f.index.is_monotonic_increasing
 assert f[['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor']].notna().all().all()
 assert f[['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor']].gt(0).all().all()
 assert (f.high>=f[['open','close','low']].max(axis=1)).all() and (f.low<=f[['open','close','high']].min(axis=1)).all()
 errs={k:float((f[k]-f['raw_'+k]*f.adjustment_factor).abs().max()) for k in ['open','high','low','close']}
 out=O/(sid.replace('.','_')+'_ORIGINAL_OHLC_FULL_PREFIX.parquet');f.to_parquet(out,index=True)
 for day in days:
  t=pd.Timestamp(day);assert t in f.index;targets.append(dict(sid=sid,day=day,original_row=f.loc[t].to_dict(),scope='Original market inputs only, not a channel/ATR output or executable fill.'))
 w=f.loc['2026-01-01':'2026-06-30']
 kind=[dict(source_kind=k,first=str(g.index[0].date()),last=str(g.index[-1].date()),rows=len(g)) for k,g in f.groupby('source_kind',sort=False)]
 coverage.append(dict(sid=sid,original_source=str(p),original_source_sha256=sha(p),prepared_prefix_path=str(out.resolve()),prepared_prefix_sha256=sha(out),first_day=str(f.index[0].date()),last_day=str(f.index[-1].date()),full_rows=len(f),H1_rows=len(w),requested_days=days,requested_missing=[],H1_OHLC_missing=w[['open','high','low','close']].isna().sum().to_dict(),source_invalid_rows=int(f.source_invalid.sum()),synthetic_rows=int(f.synthetic_event_bar.sum()),observed_rows=int(f.observed_bar.sum()),H1_observed_rows=int(w.observed_bar.sum()),OHLC_factor_max_binary64_abs_error=errs,source_kind_coverage=kind,source_metadata_price_adjustment=list(f.price_adjustment.unique()),price_adjustment_note='The prepared numeric OHLC equal raw_OHLC times adjustment_factor; source price_adjustment raw is a source label, not permission to mix units.',explicit_halt_flag=False,explicit_limit_status_or_prices=False,bid_ask_or_tick=False))
save('OHLC_COVERAGE.json',coverage);save('TEN_FIXED_ORIGINAL_ROWS.json',targets)
schema=pq.ParquetFile(RAW_CANONICAL).schema.names
save('EXECUTION_DATA_GAPS.json',dict(canonical_daily_schema=schema,signal_schema=list(f.columns),explicit_halt_or_limit_fields_in_checked_sources=False,checked_sources=['canonical signal.parquet','canonical daily_bars.parquet schema','two referenced tail-history JSON bar schemas'],tail_bar_schema=['date','open','high','low','close','volume','amount'],flags_available=['price_eligible','volume_eligible','source_invalid','observed_bar','synthetic_event_bar','quality_status'],limits=['No stop/fill feasibility from daily OHLC or positive volume alone.','No broker/exchange halt, limit queue, tick or bid/ask state was supplied.','Historical adjustment_factor provenance/publication is not a certified PIT corporate-action feed.','Current bar H/L and ATR only known after completed CLOSE.']))
save('INPUT_PREPARATION_RECEIPT.json',dict(status='PASS_ORIGINAL_OHLC_PREPARATION_ONLY',stocks=2,full_rows=sum(r['full_rows'] for r in coverage),fixed_days=len(targets),fixed25_index=str(FIXED),source_sha256=sources,script_sha256=sha(__file__),new_channel_calculations=0,new_ATR_calculations=0,new_accounts=0,new_quantities=0,new_returns=0))
print(json.dumps(dict(stocks=2,full_rows=sum(r['full_rows'] for r in coverage),fixed_days=len(targets),new_channel_or_ATR=0)))
