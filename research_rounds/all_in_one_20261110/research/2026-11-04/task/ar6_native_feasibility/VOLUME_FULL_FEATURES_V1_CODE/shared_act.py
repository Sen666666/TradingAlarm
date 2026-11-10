"""One original full-roster ACT feature gate. No account/runner or market-state feedback."""
from pathlib import Path
import ast,copy,hashlib,json,signal,time,sys,traceback
import pandas as pd,numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');END='2026-06-30'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str));tmp.replace(p)
def original_and_neutral(source):
 tree=ast.parse(Path(source).read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='compute_recovery')
 realenv=dict(np=np,pd=pd);exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),realenv)
 neutral=copy.deepcopy(node);changes=0
 for n in ast.walk(neutral):
  if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='u':
   expected=ast.parse('r*np.minimum(1,np.sqrt(q))',mode='eval').body
   assert ast.dump(n.value)==ast.dump(expected),'original ACT multiplier expression changed'
   # The known multiplier becomes one; its original unknown mask is retained.
   n.value=ast.parse('r.where(np.minimum(1,np.sqrt(q)).notna())',mode='eval').body;changes+=1
 assert changes==1
 neutral=ast.fix_missing_locations(neutral);env=dict(np=np,pd=pd);exec(compile(ast.Module(body=[neutral],type_ignores=[]),str(source)+'::known-multiplier-neutral-only','exec'),env)
 return realenv['compute_recovery'],env['compute_recovery'],ast.dump(node,include_attributes=False),ast.dump(neutral,include_attributes=False)
def load_original_inputs(manifest):
 # Exact Q4 caller stock order and sector mapping, never completion-order aggregation.
 signals={};absent=[];coverage=[];meta=read(manifest['metadata_path'])
 for r in manifest['stock_order']:
  sid=r['sid'];p=Path(r['signal_path']);assert sha(p)==r['signal_sha256'],('signal source changed',sid)
  f=pd.read_parquet(p,columns=['close','amount','price_eligible','observed_bar','synthetic_event_bar','segment_id']).loc[:END]
  valid=f.price_eligible&f.observed_bar&~f.synthetic_event_bar
  if valid.any():signals[sid]=f
  else:absent.append(sid)
  coverage.append(dict(sid=sid,raw_rows=len(f),ACT_valid_rows=int(valid.sum()),status='OBSERVED'if valid.any()else'NA_NO_OBSERVATION_THROUGH_CUTOFF',sector=meta[sid]['sector_id']))
 assert len(manifest['stock_order'])==1709 and len(absent)==22 and absent==manifest['empty_ids_expected']
 roster=pd.DataFrame([dict(symbol=sid,sector_id=meta[sid]['sector_id'])for sid in signals])
 return signals,roster,coverage
def multiplier_mask_audit(signals,roster):
 rows=[]
 for sid in roster.symbol:
  f=signals[sid];raw=f.loc[f.price_eligible&f.observed_bar&~f.synthetic_event_bar];stats=dict(sid=sid,observations=0,unknown_multiplier=0,unknown_multiplier_after64=0,naive_r_would_add_known=0)
  dig=hashlib.sha256()
  for seg,g in raw.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();m=np.minimum(1,np.sqrt(q));u=r*m;n=r.where(m.notna())
   assert u.notna().equals(n.notna()),('ACT neutral calculation availability changed',sid,seg)
   known=m.notna();ready=np.arange(len(g))>=64;stats['observations']+=len(g);stats['unknown_multiplier']+=int((~known).sum());stats['unknown_multiplier_after64']+=int(((~known)&ready).sum());stats['naive_r_would_add_known']+=int((r.notna()&~known).sum());dig.update(str(seg).encode());dig.update(g.index.as_unit('ns').asi8.tobytes());dig.update(known.to_numpy(bool).tobytes())
  stats['multiplier_known_mask_sha256']=dig.hexdigest();rows.append(stats)
 return rows
def differences(actual,expected):
 out={}
 assert actual.index.equals(expected.index)and set(actual.columns)==set(expected.columns)
 for c in expected:
  a=actual[c];b=expected[c];same=a.eq(b)|(a.isna()&b.isna());bad=~same
  if bad.any():
   ds=a[bad].index;numeric=pd.api.types.is_numeric_dtype(a.dtype)and not pd.api.types.is_bool_dtype(a.dtype)
   out[c]=dict(count=int(bad.sum()),max_abs=float((a-b).abs().max())if numeric else None,first=[dict(day=str(d.date()),actual=str(a.loc[d]),expected=str(b.loc[d]))for d in ds[:12]])
 return out
def run_gate(freeze_path,outroot):
 f=read(freeze_path);assert f['root_approved_once_ACT_only']is True and f['max_ACT_seconds']==180
 assert all(sha(p)==h for p,h in f['source_sha256'].items()),'ACT source or input binding changed'
 out=Path(outroot);assert not out.exists(),'single ACT gate target already exists';out.mkdir(parents=True)
 started=time.monotonic()
 def timeout(*args):raise TimeoutError('ACT180second hard budget exceeded')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(180)
 try:
  sources=f['source_sha256'];source=f['compute_recovery_source'];real_fn,neutral_fn,realast,neutralast=original_and_neutral(source)
  save(out/'AST_BINDING.json',dict(original_function_AST_sha256=hashlib.sha256(realast.encode()).hexdigest(),neutral_function_AST_sha256=hashlib.sha256(neutralast.encode()).hexdigest(),only_delta='u=r*known_multiplier ->r.where(original_multiplier.notna())',actual_ACT_state_executed=False))
  inp=read(f['input_manifest']);signals,roster,coverage=load_original_inputs(inp);save(out/'INPUT_COVERAGE.json',coverage);save(out/'ROSTER_ORDER.json',roster.to_dict('records'))
  real=real_fn(signals,roster);real['fast_on']=real.breadth.gt(.6)
  # Two parses are diagnostic. Actual runtime parse remains the strict primary control.
  prior=pd.read_csv(f['reference_recovery_csv'],index_col=0,parse_dates=True)
  prior.index=prior.index.as_unit('ns');real.index=real.index.as_unit('ns')  # representation only; dates/times unchanged
  assert prior.index.max()<=pd.Timestamp(END) and prior.index.equals(real.index),'ACT full comparable date domain mismatch'
  result=real.reindex(columns=prior.columns);result.to_parquet(out/'REAL_COLD.parquet');result.to_csv(out/'REAL_COLD.csv')
  diff=differences(result,prior)
  if diff:
   rt=pd.read_csv(f['reference_recovery_csv'],index_col=0,parse_dates=True,float_precision='round_trip')
   save(out/'TRUE_PARITY_FAILURE.json',dict(status='STOPPED_STRICT_RUNTIME_CSV_VALUE_DIFFERENCE',differences=diff,round_trip_parse_differences=differences(result,rt),recomputed_csv_bytes_equal_reference=(Path(f['reference_recovery_csv']).read_bytes()==(out/'REAL_COLD.csv').read_bytes()),no_tolerance_or_old_M_substitution=True,neutral_not_run=True,seconds=time.monotonic()-started,account_objects=0))
   save(out/'STATUS.json',dict(status='TRUE_ACT_PARITY_NOT_PASSED_STOP',seconds=time.monotonic()-started,full_workers_started=0,neutral_computed=False));return False
  save(out/'TRUE_PARITY_PASS.json',dict(passed=True,rows=len(result),columns=list(result),exact=True,control_parse='original pandas.read_csv default as original runtime',seconds=time.monotonic()-started))
  masks=multiplier_mask_audit(signals,roster);save(out/'MULTIPLIER_MASK_AUDIT.json',masks)
  neutral=neutral_fn(signals,roster);neutral['fast_on']=neutral.breadth.gt(.6)
  pd.testing.assert_series_equal(neutral.market,real.market,check_exact=True,check_names=False,check_freq=False)
  pd.testing.assert_series_equal(neutral.prior_high63,real.prior_high63,check_exact=True,check_names=False,check_freq=False)
  neutral.to_parquet(out/'NEUTRAL_FEATURES.parquet');neutral.to_csv(out/'NEUTRAL_FEATURES.csv')
  assert all(sha(p)==h for p,h in sources.items())and all(sha(r['signal_path'])==r['signal_sha256']for r in inp['stock_order'])
  save(out/'STATUS.json',dict(status='ACT_SHARED_FEATURE_GATE_PASS',rows=len(real),stock_roster=1709,active_stock_inputs=len(roster),empty_NA=22,strict_real_parity=True,original_multiplier_mask_preserved=True,price_M_and_priorMAX_exact=True,source_post_exact=True,seconds=time.monotonic()-started,ACT_on_computed=False,account_runner_objects=0,full_workers_started=0,full_export_authorized=False));return True
 except BaseException as e:
  save(out/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),seconds=time.monotonic()-started,no_retry=True,neutral_and_full_not_accepted=True));raise
 finally:signal.alarm(0)
