"""Frozen779 signal cohort allPVRknown, close-only forward observation paths; no models."""
from pathlib import Path
import hashlib,json,time,datetime
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
COHORT=HERE.parent/'FROZEN_IBUY_PRIOR_RANKS.parquet'
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DAY='2026-01-15';ANCHOR=pd.Timestamp(DAY)
SOURCE_EXPECTED='11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def known(v):
 return isinstance(v,str)and bool(v.strip())and v.strip().lower()not in {'unknown','none','null','nan','na','<na>'}
def bit(a,b):return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)

def main():
 assert not(HERE/'FREEZE.json').exists(),'No silent replay or reselection'
 started=time.monotonic();cohort_hash=sha(COHORT);source_hash=sha(SOURCE);assert source_hash==SOURCE_EXPECTED
 assert cohort_hash=='d38790c89ccfbccab64ea6d015a54826ceda93d6bda6df651b8e71b441e238fe'
 f=pd.read_parquet(COHORT).copy().sort_values(['rank_ALL_LOCAL_I_BUY','sid'],na_position='last')
 assert len(f)==f.sid.nunique()==779 and f.day.eq(DAY).all()
 assert f.rank_ALL_LOCAL_I_BUY.dropna().astype(int).tolist()==list(range(1,780))
 assert int(f.PVR_rank_unknown.sum())==0 and int(f.rank_ALL_LOCAL_I_BUY.isna().sum())==0
 frozen=f.copy()
 frozen.to_parquet(HERE/'FROZEN_COHORT779.parquet',index=False);frozen.to_csv(HERE/'FROZEN_COHORT779.csv',index=False)
 dataset=ds.dataset(SOURCE);schema=set(dataset.schema.names)
 positive=[n for n in ['price_eligible','observed_bar','is_observed_bar']if n in schema]
 negative=[n for n in ['source_invalid','synthetic_event_bar']if n in schema]
 cols=['symbol','trade_date','close','amount','source']+positive+negative
 source_stat=SOURCE.stat();self_hash=sha(__file__)
 save(HERE/'FREEZE.json',dict(frozen_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),day=DAY,
    cohort_count=779,cohort_filter='parent frozen all779 known-True i_buy, allPVRknown; no future outcome selection',
    cohort_input_path=str(COHORT),cohort_input_sha256=cohort_hash,
    frozen_cohort_sha256=sha(HERE/'FROZEN_COHORT779.parquet'),
    symbols_and_original_rank=frozen[['sid','rank_ALL_LOCAL_I_BUY']].astype(object).where(pd.notna(frozen[['sid','rank_ALL_LOCAL_I_BUY']]),None).to_dict('records'),
    source_path=str(SOURCE),source_sha256=source_hash,source_bytes=source_stat.st_size,source_mtime_ns=source_stat.st_mtime_ns,
    driver_sha256=self_hash,columns_read=cols,positive_masks_present=positive,negative_masks_present=negative,
    horizons=[5,20],anchor='Known canonical qfq close on 2026-01-15',
    valid='close and amount positive finite; source nonempty/nonunknown; present original masks applied',
    stop='First explicit invalid or unknown/changed source terminates anchor block; no skipping/restart',
    missing_dates='No fill. Missing dates in global source date union are a gap proxy only; do not terminate an otherwise valid block.',
    return_formula='C_n/C0-1; max_up=max(0,max(C_1..C_n/C0-1)); max_adverse=min(0,min(C_1..C_n/C0-1))',
    censored='Unreached full horizon fields are null; partial extrema separately labelled. Source-tail reason and historical delisting/halt remain UNKNOWN.',
    no_OPEN=True,no_accounts=True,no_new_signals=True,no_fees_or_fill_assumptions=True))
 # Full-date union is merely an observed-data proxy, not an official calendar.
 global_dates=dataset.to_table(columns=['trade_date'],filter=ds.field('trade_date')>=ANCHOR).column('trade_date').unique().to_pylist()
 union=pd.DatetimeIndex(sorted(global_dates));date_pos={d:i for i,d in enumerate(union)}
 frame=dataset.to_table(columns=cols,filter=ds.field('symbol').isin(f.sid.tolist())&(ds.field('trade_date')>=ANCHOR)).to_pandas()
 assert not frame.duplicated(['symbol','trade_date']).any()
 groups={sid:g.sort_values('trade_date')for sid,g in frame.groupby('symbol',sort=False)}
 horizons=[];long=[]
 for base in frozen.itertuples(index=False):
  g=groups[base.sid];anchor=g.loc[g.trade_date.eq(ANCHOR)]
  assert len(anchor)==1
  a=anchor.iloc[0];c0=float(a.close)
  assert bit(c0,base.current_close_qfq)and np.isfinite(c0)and c0>0 and np.isfinite(a.amount)and a.amount>0
  assert known(a.source)
  valid=g.close.gt(0)&np.isfinite(g.close)&g.amount.gt(0)&np.isfinite(g.amount)
  for k in positive:valid&=g[k].fillna(False).astype(bool)
  for k in negative:valid&=~g[k].fillna(True).astype(bool)
  assert bool(valid.loc[anchor.index[0]])
  future=g.loc[g.trade_date.gt(ANCHOR)].copy();future['valid']=valid.loc[future.index]
  accepted=[];stop_reason='SOURCE_END';stop_date=None;previous=ANCHOR;gap_total=0
  for row in future.itertuples(index=False):
   if not known(row.source):stop_reason='SOURCE_UNKNOWN';stop_date=row.trade_date;break
   if row.source!=a.source:stop_reason='SOURCE_CHANGE';stop_date=row.trade_date;break
   if not row.valid:stop_reason='EXPLICIT_INVALID_PRICE_AMOUNT_OR_MASK';stop_date=row.trade_date;break
   skipped=max(0,date_pos[row.trade_date]-date_pos[previous]-1);gap_total+=skipped
   accepted.append((row.trade_date,float(row.close),float(row.amount),row.source,skipped,gap_total,(row.trade_date-previous).days))
   previous=row.trade_date
  n=len(accepted);tail=g.trade_date.max()
  out=dict(sid=base.sid,day=DAY,rank_ALL_LOCAL_I_BUY=None if pd.isna(base.rank_ALL_LOCAL_I_BUY)else int(base.rank_ALL_LOCAL_I_BUY),anchor_close=c0,anchor_source=a.source,PVR_rank_unknown=bool(base.PVR_rank_unknown),in_old1709_exact=bool(base.in_old1709_exact),
      source_tail_date=str(tail.date()),anchor_block_last_valid_date=str((accepted[-1][0]if n else ANCHOR).date()),
      block_available_future_observations=n,block_termination=stop_reason,
      block_stop_date=None if stop_date is None else str(stop_date.date()),
      observed_block_right_censored_at_source_tail=stop_reason=='SOURCE_END',
      source_tail_cause='UNKNOWN',historical_delisting_status='UNKNOWN',historical_halt_status='UNKNOWN',
      global_source_date_gap_proxy_within_block=gap_total)
  for h in [5,20]:
   part=accepted[:h];complete=len(part)==h;values=np.array([x[1]/c0-1 for x in part],dtype=float)
   prefix=f'h{h}_'
   out.update({prefix+'complete':complete,prefix+'observations_available':len(part),
       prefix+'nth_date':str(part[-1][0].date())if complete else None,
       prefix+'calendar_span_days':int((part[-1][0]-ANCHOR).days)if complete else None,
       prefix+'return':float(values[-1])if complete else None,
       prefix+'max_up':max(0.,float(values.max()))if complete else None,
       prefix+'max_adverse':min(0.,float(values.min()))if complete else None,
       prefix+'right_censored':not complete,prefix+'censor_reason':None if complete else stop_reason,
       prefix+'last_available_date':str(part[-1][0].date())if part else None,
       prefix+'partial_calendar_span_days':int((part[-1][0]-ANCHOR).days)if part else None,
       prefix+'partial_max_up':max(0.,float(values.max()))if len(values)else None,
       prefix+'partial_max_adverse':min(0.,float(values.min()))if len(values)else None,
       prefix+'source_union_missing_row_proxy':sum(x[4]for x in part)})
  horizons.append(out)
  for j,(dt,close,amount,source,gap,cumgap,calgap)in enumerate(accepted[:20],1):
   long.append(dict(sid=base.sid,day=DAY,rank_ALL_LOCAL_I_BUY=None if pd.isna(base.rank_ALL_LOCAL_I_BUY)else int(base.rank_ALL_LOCAL_I_BUY),future_observation=j,
       observation_date=str(dt.date()),calendar_days_from_anchor=int((dt-ANCHOR).days),
       calendar_days_from_prior_observation=int(calgap),close=close,amount_native=amount,source=source,
       close_change_from_anchor=close/c0-1,global_source_union_missing_rows_since_prior=int(gap),
       global_source_union_missing_rows_cumulative=int(cumgap)))
 h=pd.DataFrame(horizons);l=pd.DataFrame(long)
 assert len(h)==h.sid.nunique()==779 and not l.duplicated(['sid','future_observation']).any()
 h.to_parquet(HERE/'HORIZON_PATHS.parquet',index=False);l.to_parquet(HERE/'LONG_PATHS.parquet',index=False)
 h.to_csv(HERE/'HORIZON_PATHS.csv',index=False)
 assert sha(COHORT)==cohort_hash and sha(__file__)==self_hash
 assert SOURCE.stat().st_size==source_stat.st_size and SOURCE.stat().st_mtime_ns==source_stat.st_mtime_ns
 coverage=dict(status='COMPLETE_FROZEN779_CLOSE_PATHS_ALLPVRKNOWN_NO_ACCOUNT',rows=len(h),long_rows=len(l),elapsed_seconds=time.monotonic()-started,
    horizons={str(n):dict(complete=int(h[f'h{n}_complete'].sum()),censored=int(h[f'h{n}_right_censored'].sum()),
       censor_reasons=h.loc[h[f'h{n}_right_censored'],f'h{n}_censor_reason'].value_counts().to_dict(),
       actual_nth_dates=h.loc[h[f'h{n}_complete'],f'h{n}_nth_date'].value_counts().sort_index().to_dict())for n in [5,20]},
    common_endpoint_dates={str(n):str(union[union>ANCHOR][n-1].date())if len(union[union>ANCHOR])>=n else None for n in [5,20]},
    PVR_rank_unknown_preserved=int(h.PVR_rank_unknown.sum()),
    global_source_date_union_rows=len(union),global_source_date_union_first=str(union.min().date()),global_source_date_union_last=str(union.max().date()),
    block_termination_counts=h.block_termination.value_counts().to_dict(),source_tail_dates=h.source_tail_date.value_counts().sort_index().to_dict(),
    same_block_gap_proxy_stock_count=int(h.global_source_date_gap_proxy_within_block.gt(0).sum()),
    horizon_gap_proxy_stock_counts={str(n):int(h[f'h{n}_source_union_missing_row_proxy'].gt(0).sum())for n in [5,20]},
    output_sha256={n:sha(HERE/n)for n in ['HORIZON_PATHS.parquet','LONG_PATHS.parquet']},
    source_size_mtime_unchanged=True,no_signal_or_account_execution=True,no_OPEN_read=True,
    union_gap_not_official_calendar_or_halt=True,historical_delisting_unknown=True)
 save(HERE/'COVERAGE_METADATA.json',coverage)
 print(json.dumps(coverage,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
