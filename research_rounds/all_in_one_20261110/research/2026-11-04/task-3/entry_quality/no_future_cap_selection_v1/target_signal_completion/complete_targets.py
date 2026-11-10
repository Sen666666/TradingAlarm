"""Exactly six stocks x seven independently clipped prefixes; no accounts."""
from pathlib import Path
import hashlib,json,time,sys,multiprocessing as mp,traceback
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent
ENTRY=HERE.parents[1]
ORIGINAL=ENTRY/'selection_qualification_closeout_v1/eligibility_source'
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
SYMBOLS=['000620.SZ','300085.SZ','002583.SZ','300666.SZ','603061.SH','301611.SZ']
DAYS=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
COLS=['symbol','trade_date','open','high','low','close','volume','amount','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date','source']
BUDGET=90

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
 if isinstance(x,np.generic):x=x.item()
 if x is pd.NA or x is pd.NaT:return None
 return None if isinstance(x,float)and not np.isfinite(x)else x
def save(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def bit(a,b):return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)

def worker(sid):
 sys.path.insert(0,str(ORIGINAL))
 import stock_signal as pure
 started=time.monotonic();total_model=0
 path=HERE/(sid.replace('.','_')+'.jsonl')
 try:
  with path.open('x')as stream:
   for day in DAYS:
    t=time.monotonic()
    # Read each <=t input independently. No future daily frame or indicator is reused.
    frame=ds.dataset(SOURCE).to_table(columns=COLS,filter=(ds.field('symbol')==sid)&(ds.field('trade_date')<=pd.Timestamp(day))).to_pandas().sort_values('trade_date')
    assert frame.trade_date.is_unique and (frame.trade_date<=pd.Timestamp(day)).all()
    current=frame.loc[frame.trade_date.eq(pd.Timestamp(day))]
    r=dict(sid=sid,day=day,status='MISSING_TARGET_BAR',input_prefix_rows=len(frame),target_source_row_present=not current.empty,
        prefix_end_day=None if frame.empty else str(frame.trade_date.iloc[-1].date()),
        input_prefix_first=None if frame.empty else str(frame.trade_date.iloc[0].date()),
        input_prefix_last=None if frame.empty else str(frame.trade_date.iloc[-1].date()),
        actual_max_input_day=None if frame.empty else str(frame.trade_date.max().date()),
        future_rows_passed=0,model_invoked=False,full_S0_eligibility_q=None,
        clock='Daily source trade_date <= target only; source historical available_at not certified',
        scope='STOCK_ONLY_E0_G1_I_NOT_ORDER_OR_TRADING_AUTHORIZATION')
    if len(current):
     assert len(current)==1 and frame.source.nunique(dropna=False)==1 and frame.source.notna().all()
     cur=current.iloc[0]
     r['source_target_row']={k:cur[k]for k in COLS}
     r['qfq_reference_after_target']=cur.reference_trade_date>pd.Timestamp(day)
     f=frame.set_index('trade_date')[['open','high','low','close','volume']].copy();f['segment_id']=0
     model_start=time.monotonic();out=pure.calculate(f);elapsed=time.monotonic()-model_start;total_model+=elapsed
     r.update(model_invoked=True,model_seconds=elapsed,eligible_price_observations=len(out))
     if pd.Timestamp(day)in out.index:
      r.update(status='EXACT_TARGET_STOCK_SIGNAL',signal=out.loc[pd.Timestamp(day)].to_dict())
      assert bit(r['signal']['close'],cur.close)
     else:r['status']='TARGET_REJECTED_BY_ORIGINAL_ELIGIBLE_PRICE_MASK'
    r['total_request_seconds']=time.monotonic()-t
    stream.write(json.dumps(clean(r),ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
  save(HERE/(sid.replace('.','_')+'_DONE.json'),dict(sid=sid,status='COMPLETE',requests=7,model_seconds=total_model,wall_seconds=time.monotonic()-started,output_sha256=sha(path)))
 except BaseException as e:
  save(HERE/(sid.replace('.','_')+'_ERROR.json'),dict(sid=sid,error=repr(e),traceback=traceback.format_exc()))
  raise

def main():
 assert not(HERE/'FREEZE.json').exists(),'Do not repeat this batch'
 old=json.loads((ORIGINAL/'fixed35/SAMPLE_FREEZE.json').read_text())
 actual=sha(SOURCE);assert actual==old['source_sha256'][str(SOURCE)]
 codes={p:h for p,h in old['algorithm_code_sha256'].items()if p.endswith('.py')}
 for p,h in codes.items():assert sha(p)==h,('original code changed',p)
 stat=SOURCE.stat();selfsha=sha(__file__)
 save(HERE/'FREEZE.json',dict(symbols=SYMBOLS,days=DAYS,requests=42,source_path=str(SOURCE),source_sha256=actual,
    source_bytes=stat.st_size,source_mtime_ns=stat.st_mtime_ns,original_algorithm_code_sha256=codes,
    driver_sha256=selfsha,max_workers=6,wall_compute_budget_seconds=BUDGET,
    physical_input_rule='For every stock/date request: dataset filter sid AND trade_date <= t, call original stock_signal.calculate only if exact t bar exists; no future frame/indicator reused',
    expected_missing_requests=[dict(sid=s,day=d)for s in ['603061.SH','301611.SZ']for d in DAYS[:2]],
    zero_accounts=True,no_current_cap_input=True,no_new_parameters=True))
 print('FROZEN_START_6_WORKERS_42_REQUESTS_BUDGET_90_SECONDS',flush=True)
 started=time.monotonic();ctx=mp.get_context('spawn');procs=[ctx.Process(target=worker,args=(s,))for s in SYMBOLS]
 for p in procs:p.start()
 while any(p.is_alive()for p in procs)and time.monotonic()-started<BUDGET:
  for p in procs:p.join(timeout=.02)
  time.sleep(.1)
 exceeded=any(p.is_alive()for p in procs)
 if exceeded:
  for p in procs:
   if p.is_alive():p.terminate()
 for p in procs:p.join()
 wall=time.monotonic()-started
 if exceeded or any(p.exitcode!=0 for p in procs):
  save(HERE/'STOPPED.json',dict(status='STOPPED_NO_AUTOMATIC_RETRY',exceeded_90_second_budget=exceeded,exitcodes=[p.exitcode for p in procs],wall_seconds=wall))
  print('STOPPED',wall,flush=True);return
 rows=[]
 for sid in SYMBOLS:
  rows.extend(json.loads(x)for x in(HERE/(sid.replace('.','_')+'.jsonl')).read_text().splitlines())
 assert len(rows)==42 and len({(r['sid'],r['day'])for r in rows})==42
 statuses=pd.Series([r['status']for r in rows]).value_counts().to_dict()
 assert statuses=={'EXACT_TARGET_STOCK_SIGNAL':38,'MISSING_TARGET_BAR':4}
 fixed=pd.read_parquet(ORIGINAL/'fixed35/FIXED35_2024_09_24.parquet').set_index('sid')
 pilot={r['sid']:r['target']for r in json.loads((ORIGINAL/'PILOT.json').read_text())['rows']}
 equal=[]
 for sid,previous,kind in [('300085.SZ',fixed.loc['300085.SZ'].to_dict(),'FIXED35'),('000620.SZ',pilot['000620.SZ'],'PILOT'),('002583.SZ',pilot['002583.SZ'],'PILOT')]:
  r=next(x for x in rows if x['sid']==sid and x['day']=='2024-09-24')['signal']
  for field,value in r.items():
   v=previous[field]
   assert (pd.isna(value)and pd.isna(v))or(value==v),(sid,field,value,v)
  equal.append(dict(sid=sid,day='2024-09-24',previous=kind,all_signal_fields_exact_equal=True))
 save(HERE/'TARGET42.json',rows)
 flattened=[]
 for r in rows:
  rec={k:v for k,v in r.items()if k not in ['signal','source_target_row']}
  rec.update(r.get('signal',{}))
  rec.update({'source_'+k:v for k,v in r.get('source_target_row',{}).items()})
  flattened.append(rec)
 f=pd.DataFrame(flattened);f.to_csv(HERE/'TARGET42.csv',index=False);f.to_parquet(HERE/'TARGET42.parquet',index=False)
 assert SOURCE.stat().st_size==stat.st_size and SOURCE.stat().st_mtime_ns==stat.st_mtime_ns
 assert sha(__file__)==selfsha
 for p,h in codes.items():assert sha(p)==h
 save(HERE/'COMPLETION.json',dict(status='COMPLETE_BOUNDED_6_STOCK_7_DATE_ORIGINAL_SIGNAL_COMPLETION',status_counts=statuses,
    requests=42,model_invocations=38,wall_compute_seconds=wall,max_workers=6,
    input_source_hash_bound=True,source_size_mtime_unchanged_during_compute=True,
    exact_signal_field_checks=equal,source_prefix_cut_per_request=True,
    signal_only_not_full_S0_or_order_permission=True,zero_accounts=True,zero_cap_inputs=True,
    per_worker=[json.loads((HERE/(sid.replace('.','_')+'_DONE.json')).read_text())for sid in SYMBOLS]))
 print('COMPLETE',json.dumps(dict(statuses=statuses,wall_compute_seconds=wall,prior_three_exact=True)),flush=True)

if __name__=='__main__':main()
