"""Two explicit original-signal dates. Reuses immutable924 worker body, no924 run.

Only the worker output directory and physical cutoff date are parameterized.
The original stock_signal implementation is never modified. Dates run serially.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing as mp
import importlib.util,sys,hashlib,json,time,argparse
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent;ENTRY=ROOT.parent
IMPL=ENTRY/'full_local_signal_20240924_v1/signals/run_signals.py'
TARGET=ENTRY/'no_future_cap_selection_v1/target_signal_completion'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DATES=['2022-01-24','2026-01-15'];WORKERS=12
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if isinstance(v,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(v))
 if isinstance(v,np.generic):v=v.item()
 if v is pd.NA or v is pd.NaT:return None
 return None if isinstance(v,float)and not np.isfinite(v)else v
def save(p,v):Path(p).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load_worker():
 name='immutable_original_signal_block_worker'
 spec=importlib.util.spec_from_file_location(name,IMPL);m=importlib.util.module_from_spec(spec)
 sys.modules[name]=m;spec.loader.exec_module(m);return m
def worker(day,out,stage,block_id,symbols):
 m=load_worker();m.DAY=day;m.HERE=Path(out)
 return m.block_worker(stage,block_id,symbols)
def records(folder):return [r for p in sorted(Path(folder).glob('*.jsonl'))for r in load_worker().lines(p)]
def validate(out):
 f=read(out/'FREEZE.json');s=SOURCE.stat()
 assert s.st_size==f['source_bytes']and s.st_mtime_ns==f['source_mtime_ns']
 assert sha(__file__)==f['date_wrapper_sha256']and sha(IMPL)==f['immutable_worker_driver_sha256']
 for p,h in f['original_algorithm_code_sha256'].items():assert sha(p)==h
 assert sha(out/'REUSED_TARGETS.jsonl')==f['reused_jsonl_sha256']
 return f

def prepare(day,out):
 out.mkdir(parents=True,exist_ok=True);assert not(out/'FREEZE.json').exists()
 tf=read(TARGET/'FREEZE.json');actual=sha(SOURCE);assert actual==tf['source_sha256']
 for p,h in tf['original_algorithm_code_sha256'].items():assert sha(p)==h
 old_worker_freeze=read(IMPL.parent/'FREEZE.json');assert sha(IMPL)==old_worker_freeze['driver_sha256']
 assert sha(FEATURES)==old_worker_freeze['source_feature_sha256']
 tp=TARGET/'TARGET42.parquet';ts=read(TARGET/'SEAL.json')['files_sha256']
 expected=next(h for p,h in ts.items()if Path(p).resolve()==tp.resolve());assert sha(tp)==expected
 target=pd.read_parquet(tp);reused=target.loc[target.day.eq(day)&target.status.eq('EXACT_TARGET_STOCK_SIGNAL')].copy()
 assert len(reused)==(4 if day==DATES[0]else 6)
 feature=pd.read_parquet(FEATURES);feature=feature.loc[feature.day.eq(day)].copy()
 assert len(feature)==feature.sid.nunique()==5517
 roster=feature[['sid','target_row_present','source_observation_count_through_t']].rename(columns={'source_observation_count_through_t':'prefix_rows'})
 roster.to_csv(out/'UNIVERSE5517.csv',index=False)
 m=load_worker();saved=[]
 for r in reused.to_dict('records'):
  r['signal_status']=r['status'];r['reuse_source']='target42_exact';r['source_sha256']=actual
  saved.append(m.normalized(r))
 with(out/'REUSED_TARGETS.jsonl').open('x')as f:
  for r in saved:f.write(json.dumps(clean(r),ensure_ascii=False,allow_nan=False)+'\n')
 control_ids=sorted(reused.sid)[:3]
 stat=SOURCE.stat();remaining=set(roster.sid)-set(reused.sid)
 pending=roster.loc[roster.sid.isin(remaining)]
 model_rows=int(pending.loc[pending.target_row_present.eq(True),'prefix_rows'].sum())
 eta=1744.8520240830258*model_rows/13045291
 save(out/'FREEZE.json',dict(day=day,universe_symbols=5517,source_path=str(SOURCE),source_sha256=actual,
    source_bytes=stat.st_size,source_mtime_ns=stat.st_mtime_ns,
    original_algorithm_code_sha256=tf['original_algorithm_code_sha256'],date_wrapper_sha256=sha(__file__),
    immutable_worker_driver_path=str(IMPL),immutable_worker_driver_sha256=sha(IMPL),
    reused_target_output_sha256=sha(tp),reused_ids=sorted(reused.sid),reused_count=len(reused),
    reused_jsonl_sha256=sha(out/'REUSED_TARGETS.jsonl'),controls=control_ids,workers=WORKERS,
    universe_sha256=sha(out/'UNIVERSE5517.csv'),features_sha256=sha(FEATURES),
    remaining_symbols=len(remaining),remaining_target_present=int(pending.target_row_present.eq(True).sum()),
    remaining_model_prefix_rows=model_rows,ETA_seconds_from_prior_observed_throughput=eta,
    physical_prefix_rule='Immutable block worker receives this day, reads symbol-set AND trade_date<=day; no future frame/indicator passed',
    stock_only=True,zero_accounts=True,no_new_parameters=True,no_924_execution=True))
 print('FROZEN',day,'reused',len(reused),'remaining',len(remaining),'ETA_MIN',round(eta/60,2),flush=True)

def dispatch(day,out,stage,blocks):
 directory=out/stage;directory.mkdir(exist_ok=True)
 plan=directory/'BLOCK_PLAN.json'
 if plan.exists():assert read(plan)['blocks']==blocks
 else:save(plan,dict(day=day,blocks=blocks,workers=WORKERS,stage=stage))
 receipts=[]
 with ProcessPoolExecutor(max_workers=WORKERS,mp_context=mp.get_context('spawn'))as pool:
  futures=[pool.submit(worker,day,str(out),stage,j,s)for j,s in enumerate(blocks)]
  for f in as_completed(futures):
   receipts.append(f.result());save(directory/'BLOCK_RECEIPTS.json',receipts)

def run_date(day,resume=False):
 out=ROOT/day/'signals'
 if(out/'COMPLETION.json').exists():
  assert resume,'Completed date is immutable; do not rerun'
  print('ALREADY_COMPLETE_SKIP',day,flush=True);return
 if not(out/'FREEZE.json').exists():prepare(day,out)
 else:assert resume,'Explicit --resume required for partial date'
 frozen=validate(out);m=load_worker()
 reused={r['sid']:r for r in m.lines(out/'REUSED_TARGETS.jsonl')}
 # Bounded three existing target controls only; no benchmark16 or parameter test.
 dispatch(day,out,'controls',[[s]for s in frozen['controls']])
 controls=records(out/'controls')
 for r in controls:
  assert r['signal_status']=='EXACT_TARGET_STOCK_SIGNAL'
  for k in FIELDS:assert m.same(r[k],reused[r['sid']][k]),('control mismatch',day,r['sid'],k)
 save(out/'CONTROL_EQUALITY.json',dict(day=day,controls=frozen['controls'],all19_original_fields_exact=True))
 roster=pd.read_csv(out/'UNIVERSE5517.csv');lengths=dict(zip(roster.sid,roster.prefix_rows))
 symbols=sorted(set(roster.sid)-set(reused));blocks=m.balanced(symbols,lengths,(len(symbols)+23)//24)
 print('START_FULL',day,'symbols',len(symbols),'blocks',len(blocks),'workers',WORKERS,flush=True)
 started=time.monotonic();dispatch(day,out,'full',blocks);elapsed=time.monotonic()-started;validate(out)
 fresh=records(out/'full');assert len(fresh)==len({r['sid']for r in fresh})==len(symbols)
 merged=dict(reused)
 for r in fresh:
  assert r['sid']not in merged;r['reuse_source']='new_full_batch';merged[r['sid']]=r
 assert set(merged)==set(roster.sid)and len(merged)==5517
 result=pd.DataFrame([merged[s]for s in sorted(merged)]);assert result.day.eq(day).all()
 exact=result.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL')
 assert result.loc[exact,'prefix_end_day'].eq(day).all()
 assert result.prefix_end_day.dropna().le(day).all()
 result.to_parquet(out/'ALL_SIGNALS.parquet',index=False);result.to_csv(out/'ALL_SIGNALS.csv',index=False)
 save(out/'COMPLETION.json',dict(status='COMPLETE_LOCAL5517_FIXED_DAY_ORIGINAL_STOCK_ONLY',day=day,rows=5517,
    status_counts=result.signal_status.value_counts().to_dict(),reuse_count=len(reused),new_unique_requests=len(fresh),
    full_batch_wall_seconds=elapsed,source_sha256=frozen['source_sha256'],
    all_signals_sha256=sha(out/'ALL_SIGNALS.parquet'),date_wrapper_sha256=sha(__file__),
    immutable_worker_driver_sha256=sha(IMPL),original_algorithm_code_sha256=frozen['original_algorithm_code_sha256'],
    control_equality=True,no_accounts=True,no_new_parameters=True,no_924_execution=True,
    helper_interpretation='Producer e0-only helpers are not full known-buy; root independently guards exact/e0/g readiness',
    errors_missing_unready_preserved=True))
 print('DATE_COMPLETE',day,'WALL_MIN',round(elapsed/60,3),'STATUS',result.signal_status.value_counts().to_dict(),flush=True)
 assert not result.signal_status.eq('SOURCE_OR_PURE_SIGNAL_ERROR').any(),'Preserved errors require inspection before next date'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dates',nargs='+',choices=DATES,default=DATES);p.add_argument('--resume',action='store_true');z=p.parse_args()
 assert z.dates==sorted(z.dates),'Dates must run in frozen chronological order'
 for day in z.dates:run_date(day,z.resume)
