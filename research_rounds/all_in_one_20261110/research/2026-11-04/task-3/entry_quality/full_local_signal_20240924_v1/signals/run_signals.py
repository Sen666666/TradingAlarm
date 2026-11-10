"""Durable stock-only original signal export. Default runs ONLY frozen pilot16.

--full is a separate explicit invocation; no automatic promotion after pilot.
Resume reads complete append-only JSONL records and never reruns completed/error IDs.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing as mp
import hashlib,json,time,sys,traceback,resource,argparse,os
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
ORIGINAL=ENTRY/'selection_qualification_closeout_v1/eligibility_source'
TARGET=ENTRY/'no_future_cap_selection_v1/target_signal_completion'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
MEMBER=ENTRY/'local_observable_selection_v1/coverage_audit/CANONICAL5517_EXACT_OLD1709_MEMBERSHIP.csv'
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DAY='2024-09-24';WORKERS=12
COLS=['symbol','trade_date','open','high','low','close','volume','amount','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date','source']
SIGNAL=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']

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
def same(a,b):
 if pd.isna(a)and pd.isna(b):return True
 if isinstance(a,(float,np.floating))and isinstance(b,(float,np.floating)):
  return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)
 return a==b
def normalized(r):
 r=dict(r);ready=r.get('e0_ready')==1
 r['stock_hold_signal']=bool(r['i_target'])if ready else None
 r['stock_fresh_core_signal']=bool(r['i_target']and r['i_buy'])if ready else None
 r['stock_signal_readiness']='READY'if ready else'UNKNOWN_NOT_READY'
 r['full_S0_eligibility_q']=None
 return r
def lines(p):
 result=[]
 if not Path(p).exists():return result
 for number,s in enumerate(Path(p).read_text().splitlines(),1):
  try:result.append(json.loads(s))
  except json.JSONDecodeError:
   raise ValueError(f'Truncated/corrupt journal {p}:{number}; retained unchanged; inspect before resume')
 return result

def prepare():
 assert not(HERE/'FREEZE.json').exists()
 old=read(ORIGINAL/'fixed35/SAMPLE_FREEZE.json');actual=sha(SOURCE)
 assert actual==old['source_sha256'][str(SOURCE)]
 codes={p:h for p,h in old['algorithm_code_sha256'].items()if p.endswith('.py')}
 for p,h in codes.items():assert sha(p)==h
 inputs=[];raw=[]
 stop=read(ORIGINAL/'STOP_SEAL.json')
 for p in sorted(ORIGINAL.glob('SHARD_*_STOCK_SIGNAL.jsonl')):
  assert sha(p)==stop['files'][p.name]
  inputs.append(dict(path=str(p),sha256=sha(p),kind='partial72'))
  for r in lines(p):raw.append((r,'partial72',str(p)))
 fpath=ORIGINAL/'fixed35/FIXED35_2024_09_24.parquet';fseal=read(ORIGINAL/'fixed35/SEAL.json')
 assert sha(fpath)==fseal['files'][fpath.name]
 inputs.append(dict(path=str(fpath),sha256=sha(fpath),kind='fixed35'))
 for r in pd.read_parquet(fpath).to_dict('records'):raw.append((r,'fixed35',str(fpath)))
 tf=read(TARGET/'FREEZE.json');tseal=read(TARGET/'SEAL.json');tp=TARGET/'TARGET42.parquet'
 assert tf['source_sha256']==actual and tf['original_algorithm_code_sha256']==codes
 target_seal_key=next(k for k in tseal['files_sha256']if Path(k).resolve()==tp.resolve())
 assert sha(tp)==tseal['files_sha256'][target_seal_key]
 inputs.append(dict(path=str(tp),sha256=sha(tp),kind='target6'))
 for r in pd.read_parquet(tp).query('day==@DAY').to_dict('records'):
  r['signal_status']=r['status'];raw.append((r,'target6',str(tp)))
 reused={};duplicate_checks=[]
 for r,kind,path in raw:
  assert r['day']==DAY and r['signal_status']=='EXACT_TARGET_STOCK_SIGNAL'
  r['reuse_kind']=kind;r['reuse_path']=path;r['source_sha256']=actual
  r['prefix_end_day']=r.get('prefix_end_day',r.get('source_last_prefix_day'))
  if r['sid']in reused:
   prior=reused[r['sid']]
   for k in SIGNAL:assert same(r[k],prior[k]),('reuse mismatch',r['sid'],k,r[k],prior[k])
   duplicate_checks.append(dict(sid=r['sid'],all19_original_fields_exact=True))
  else:reused[r['sid']]=normalized(r)
 assert len(reused)==110
 assert sha(FEATURES)==old['source_sha256'][str(FEATURES)]
 features=pd.read_parquet(FEATURES).query('day==@DAY').copy()
 member=pd.read_csv(MEMBER).set_index('symbol')
 assert len(features)==features.sid.nunique()==5517
 features['in_old1709']=features.sid.map(member.in_old1709)
 features['exchange']=features.sid.str[-2:]
 roster=features[['sid','target_row_present','source_observation_count_through_t','in_old1709','exchange']].copy()
 roster=roster.rename(columns={'source_observation_count_through_t':'prefix_rows'})
 roster.to_csv(HERE/'UNIVERSE5517.csv',index=False)
 # Two predetermined existing controls, then cross exchange/membership cells,
 # then length quantiles. No outcomes, grades or target returns enter selection.
 partial=sorted({r['sid']for r,k,p in raw if k=='partial72'})
 fixed=sorted({r['sid']for r,k,p in raw if k=='fixed35'}-set(partial))
 controls=[partial[0],fixed[0]]
 available=roster.loc[roster.target_row_present.eq(True)&~roster.sid.isin(reused)]
 selected=list(controls);reasons={s:'prior_saved_exact_control'for s in controls}
 def add_nearest(group,target,why):
  candidates=group.loc[~group.sid.isin(selected)].copy()
  if candidates.empty:return
  candidates['distance']=(candidates.prefix_rows-target).abs()
  sid=candidates.sort_values(['distance','sid']).iloc[0].sid
  selected.append(sid);reasons[sid]=why
 for exchange in ['SH','SZ','BJ']:
  for oldpool in [True,False]:
   g=available.loc[available.exchange.eq(exchange)&available.in_old1709.eq(oldpool)]
   if len(g):add_nearest(g,float(g.prefix_rows.median()),f'{exchange}/old1709={oldpool}/median_prefix')
 for q in [0,.1,.25,.5,.75,.9,1,.33,.67,.05,.95,.2,.8]:
  if len(selected)>=16:break
  add_nearest(available,float(available.prefix_rows.quantile(q)),f'available_prefix_quantile={q:.8f}')
 assert len(selected)==len(set(selected))==16
 pilot=roster.set_index('sid').loc[selected].reset_index();pilot['selection_reason']=pilot.sid.map(reasons)
 pilot['is_prior_control']=pilot.sid.isin(controls);pilot.to_csv(HERE/'PILOT16_PLAN.csv',index=False)
 with(HERE/'REUSED110.jsonl').open('x')as f:
  for sid in sorted(reused):f.write(json.dumps(clean(reused[sid]),ensure_ascii=False,allow_nan=False)+'\n')
 stat=SOURCE.stat()
 binding=dict(day=DAY,universe_symbols=5517,source_path=str(SOURCE),source_sha256=actual,source_bytes=stat.st_size,source_mtime_ns=stat.st_mtime_ns,
    original_algorithm_code_sha256=codes,driver_sha256=sha(__file__),workers=WORKERS,
    reused_unique=110,reuse_inputs=inputs,duplicate_signal_checks=duplicate_checks,
    universe_file_sha256=sha(HERE/'UNIVERSE5517.csv'),pilot_plan_sha256=sha(HERE/'PILOT16_PLAN.csv'),
    reused_jsonl_sha256=sha(HERE/'REUSED110.jsonl'),pilot_symbols=selected,pilot_controls=controls,
    source_feature_sha256=sha(FEATURES),membership_file_sha256=sha(MEMBER),
    physical_prefix_rule='Each block reads required columns once with symbol set AND trade_date<=2024-09-24. Missing exact target never calls calculate. No indicator reused from a future frame.',
    stock_not_ready='Preserve original e0/I/G state fields; normalized stock_hold/fresh remain None UNKNOWN when original e0_ready!=1.',
    journal_rule='Each complete stock writes/flushed JSONL. Resume validates all identities, skips persisted IDs including errors, never retries errors or truncates prior journals automatically.',
    full_not_started=True,no_accounts=True,no_parameters_changed=True)
 save(HERE/'FREEZE.json',binding)
 print('PREPARED_REUSE110_PILOT16_ONLY',selected,flush=True)

def validate():
 f=read(HERE/'FREEZE.json');stat=SOURCE.stat()
 assert stat.st_size==f['source_bytes']and stat.st_mtime_ns==f['source_mtime_ns']
 assert sha(__file__)==f['driver_sha256']
 for p,h in f['original_algorithm_code_sha256'].items():assert sha(p)==h
 for name,key in [('UNIVERSE5517.csv','universe_file_sha256'),('PILOT16_PLAN.csv','pilot_plan_sha256'),('REUSED110.jsonl','reused_jsonl_sha256')]:assert sha(HERE/name)==f[key]
 return f

def block_worker(stage,block_id,symbols):
 sys.path.insert(0,str(ORIGINAL));import stock_signal as pure
 freeze=read(HERE/'FREEZE.json');directory=HERE/stage;directory.mkdir(exist_ok=True)
 prefix=f'block_{block_id:04d}_part_';existing=sorted(directory.glob(prefix+'*.jsonl'))
 done={r['sid']for p in existing for r in lines(p)}
 pending=[s for s in symbols if s not in done]
 if not pending:return dict(block_id=block_id,new_records=0)
 target=directory/(prefix+f'{len(existing):03d}.jsonl')
 start=time.monotonic()
 data=ds.dataset(SOURCE).to_table(columns=COLS,filter=ds.field('symbol').isin(pending)&(ds.field('trade_date')<=pd.Timestamp(DAY))).to_pandas()
 groups={sid:g.sort_values('trade_date')for sid,g in data.groupby('symbol',sort=False)}
 load=time.monotonic()-start;records=[]
 with target.open('x')as stream:
  for sid in pending:
   begin=time.monotonic();g=groups.get(sid,pd.DataFrame(columns=COLS));current=g.loc[g.trade_date.eq(pd.Timestamp(DAY))]
   r=dict(sid=sid,day=DAY,signal_status='MISSING_TARGET_BAR',target_source_row_present=not current.empty,
       prefix_end_day=None if g.empty else str(g.trade_date.iloc[-1].date()),input_prefix_rows=len(g),
       input_prefix_first=None if g.empty else str(g.trade_date.iloc[0].date()),
       source_sha256=freeze['source_sha256'],algorithm_binding=str(HERE/'FREEZE.json'),
       full_S0_eligibility_q=None,stock_hold_signal=None,stock_fresh_core_signal=None,
       stock_signal_readiness='UNKNOWN_NO_EXACT_TARGET',model_invoked=False)
   try:
    assert g.trade_date.is_unique and(g.trade_date<=pd.Timestamp(DAY)).all()
    if not current.empty:
     assert len(current)==1 and g.source.nunique(dropna=False)==1 and g.source.notna().all()
     cur=current.iloc[0]
     for k in COLS:r['source_'+k]=cur[k]
     frame=g.set_index('trade_date')[['open','high','low','close','volume']].copy();frame['segment_id']=0
     before=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_SELF)
     out=pure.calculate(frame)
     cpu1=resource.getrusage(resource.RUSAGE_SELF)
     r.update(model_invoked=True,model_seconds=time.monotonic()-before,
        model_cpu_seconds=cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,
        eligible_price_observations=len(out))
     if pd.Timestamp(DAY)in out.index:
      r.update(out.loc[pd.Timestamp(DAY)].to_dict());r=normalized(r);r['signal_status']='EXACT_TARGET_STOCK_SIGNAL'
     else:r['signal_status']='TARGET_REJECTED_BY_ORIGINAL_ELIGIBLE_PRICE_MASK'
   except Exception as e:
    r['signal_status']='SOURCE_OR_PURE_SIGNAL_ERROR';r['error']=repr(e);r['traceback']=traceback.format_exc()
    for k in SIGNAL:r[k]=None
    r['stock_hold_signal']=None;r['stock_fresh_core_signal']=None;r['stock_signal_readiness']='UNKNOWN_ERROR'
   r['request_seconds']=time.monotonic()-begin;records.append(clean(r))
   stream.write(json.dumps(clean(r),ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
   save(directory/f'block_{block_id:04d}_PROGRESS.json',dict(block_id=block_id,completed_in_part=len(records),symbols_in_block=len(symbols),last_sid=sid,last_status=r['signal_status']))
 save(directory/f'block_{block_id:04d}_part_{len(existing):03d}_DONE.json',dict(block_id=block_id,records=len(records),load_seconds=load,wall_seconds=time.monotonic()-start,journal_sha256=sha(target)))
 return dict(block_id=block_id,new_records=len(records),errors=sum(r['signal_status']=='SOURCE_OR_PURE_SIGNAL_ERROR'for r in records))

def balanced(symbols,lengths,n):
 buckets=[[]for _ in range(n)];load=[0]*n
 for sid in sorted(symbols,key=lambda s:(-lengths[s],s)):
  j=min(range(n),key=lambda j:(load[j],len(buckets[j]),j));buckets[j].append(sid);load[j]+=lengths[sid]
 return [x for x in buckets if x]

def run(stage):
 freeze=validate();roster=pd.read_csv(HERE/'UNIVERSE5517.csv');lengths=dict(zip(roster.sid,roster.prefix_rows))
 if stage=='pilot':symbols=freeze['pilot_symbols'];blocks=balanced(symbols,lengths,WORKERS)
 else:
  assert(HERE/'PILOT_SUMMARY.json').exists(),'Discuss measured pilot ETA before explicit --full'
  assert not read(HERE/'PILOT_SUMMARY.json')['status_counts'].get('SOURCE_OR_PURE_SIGNAL_ERROR',0),'Inspect pilot error before full'
  done={r['sid']for r in lines(HERE/'REUSED110.jsonl')}
  done|={r['sid']for p in(HERE/'pilot').glob('*.jsonl')for r in lines(p)}
  symbols=sorted(set(roster.sid)-done);blocks=balanced(symbols,lengths,max(1,(len(symbols)+23)//24))
 directory=HERE/stage;directory.mkdir(exist_ok=True)
 plan=directory/'BLOCK_PLAN.json'
 if plan.exists():assert read(plan)['blocks']==blocks
 else:save(plan,dict(stage=stage,blocks=blocks,symbols=len(symbols),workers=WORKERS))
 print('START',stage,'symbols',len(symbols),'blocks',len(blocks),flush=True)
 started=time.monotonic();receipts=[]
 with ProcessPoolExecutor(max_workers=WORKERS,mp_context=mp.get_context('spawn'))as pool:
  jobs=[pool.submit(block_worker,stage,i,s)for i,s in enumerate(blocks)]
  for future in as_completed(jobs):
   receipts.append(future.result());save(directory/'BLOCK_RECEIPTS.json',receipts)
 elapsed=time.monotonic()-started;validate()
 allrows=[r for p in sorted(directory.glob('*.jsonl'))for r in lines(p)]
 assert len(allrows)==len({r['sid']for r in allrows})==len(symbols)
 summary=dict(stage=stage,wall_seconds=elapsed,rows=len(allrows),status_counts=pd.Series([r['signal_status']for r in allrows]).value_counts().to_dict(),new_accounts=0)
 if stage=='pilot':
  reused={r['sid']:r for r in lines(HERE/'REUSED110.jsonl')};comparisons=[]
  for r in allrows:
   if r['sid']in freeze['pilot_controls']:
    for k in SIGNAL:assert same(r[k],reused[r['sid']][k]),('pilot mismatch',r['sid'],k)
    comparisons.append(dict(sid=r['sid'],all19_original_fields_exact=True))
  summary['control_equality']=comparisons
  fresh=[r for r in allrows if r['sid']not in reused]
  remaining=set(roster.sid)-set(reused)-{r['sid']for r in allrows}
  remaining_observed=roster.loc[roster.sid.isin(remaining)&roster.target_row_present.eq(True)]
  sample_obs=sum(r['input_prefix_rows']for r in allrows if r['model_invoked'])
  wall_model=sum(r.get('model_seconds',0)for r in allrows)
  cpu_model=sum(r.get('model_cpu_seconds',0)for r in allrows)
  observed_work=int(remaining_observed.prefix_rows.sum())
  summary.update(model_wall_seconds_sum=wall_model,model_cpu_seconds_sum=cpu_model,pilot_prefix_rows=sample_obs,
    new_reusable_pilot_symbols=len(fresh),remaining_symbols=len(remaining),remaining_exact_target_symbols=len(remaining_observed),remaining_model_prefix_rows=observed_work,
    ETA_seconds_model_sum_div12=observed_work*(wall_model/sample_obs)/WORKERS,
    ETA_seconds_batch_throughput=observed_work/sample_obs*elapsed,
    ETA_is_extrapolation_not_promise=True,full_not_started=True)
  pd.DataFrame(allrows).to_parquet(HERE/'PILOT16.parquet',index=False);pd.DataFrame(allrows).to_csv(HERE/'PILOT16.csv',index=False)
  save(HERE/'PILOT_SUMMARY.json',summary)
 else:
  save(HERE/'FULL_SUMMARY.json',summary)
  merged={r['sid']:dict(r,reuse_source=r['reuse_kind'])for r in lines(HERE/'REUSED110.jsonl')}
  for p in sorted((HERE/'pilot').glob('*.jsonl')):
   for r in lines(p):
    if r['sid']not in merged:merged[r['sid']]=dict(r,reuse_source='new_pilot16')
  for r in allrows:
   assert r['sid']not in merged
   merged[r['sid']]=dict(r,reuse_source='new_full_batch')
  assert set(merged)==set(roster.sid)and len(merged)==5517
  result=pd.DataFrame([merged[s]for s in sorted(merged)])
  result.to_parquet(HERE/'ALL_SIGNALS.parquet',index=False)
  result.to_csv(HERE/'ALL_SIGNALS.csv',index=False)
  save(HERE/'COMPLETION.json',dict(status='COMPLETE_LOCAL5517_SINGLE_DAY_STOCK_ONLY_SIGNALS',day=DAY,rows=5517,
    status_counts=result.signal_status.value_counts().to_dict(),reuse_source_counts=result.reuse_source.value_counts().to_dict(),
    exact_target_but_not_ready=int((result.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL')&~result.e0_ready.eq(1)).sum()),
    full_batch_wall_seconds=elapsed,source_sha256=freeze['source_sha256'],
    original_algorithm_code_sha256=freeze['original_algorithm_code_sha256'],
    all_signals_sha256=sha(HERE/'ALL_SIGNALS.parquet'),columns=list(result.columns),
    errors_and_missing_not_false=True,no_accounts=True,no_new_parameters=True,not_full_S0=True))
 print('FINISHED',json.dumps(clean(summary),ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--resume-pilot',action='store_true');z=p.parse_args()
 if not z.full and not z.resume_pilot:prepare()
 run('full'if z.full else'pilot')
