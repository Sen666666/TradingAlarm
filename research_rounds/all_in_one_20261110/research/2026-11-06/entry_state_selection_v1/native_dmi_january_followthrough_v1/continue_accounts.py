"""Import-safe, single-run native DMI checkpoint suffix. No live orders."""
from pathlib import Path
from datetime import datetime,time as dtime
import sys,os,json,gzip,pickle,time,gc,traceback,argparse,inspect
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;OLD=R/'native_dmi_two_month_continuous_v1'
sys.path.insert(0,str(OLD));import run_bounded as B
E,C,A,N,J,L,IO=B.E,B.C,B.A,B.N,B.J,B.L,B.IO
np,pd=B.np,B.pd
END='2026-05-15';WINDOWS=('2022Jan','2026Jan')
IMMUTABLE={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}

class FeatureLookup:
 def __init__(self):
  f=pd.read_parquet(O/'ALL_CONTINUATION_DMI_FEATURES.parquet');nd=f.day.nunique();ns=f.sid.nunique()
  self.days={d:i for i,d in enumerate(f.day.iloc[:nd])};self.sids={s:i for i,s in enumerate(f.sid.iloc[::nd])}
  assert ns==len(self.sids)==1709 and len(self.days)==nd and len(f)==ns*nd
  assert np.array_equal(f.sid.to_numpy().reshape(ns,nd),np.repeat(f.sid.iloc[::nd].to_numpy()[:,None],nd,axis=1))
  assert np.array_equal(f.day.to_numpy().reshape(ns,nd),np.tile(f.day.iloc[:nd].to_numpy(),(ns,1)))
  self.values=f.d.to_numpy().reshape(ns,nd).copy()
 def __contains__(self,key):return key[0] in self.sids and key[1] in self.days
 def __getitem__(self,key):return self.values[self.sids[key[0]],self.days[key[1]]]

class RankAudit:
 def __init__(self,path):self.f=gzip.open(path,'wt');self.count=0;self.unknown=0;self.moved=0
 def append(self,row):
  self.f.write(json.dumps(row,default=J.C.encoded,allow_nan=False)+'\n');self.count+=1;self.unknown+=row['d'] is None;self.moved+=row['rank']!=row['original_PVR_rank']
 def close(self):self.f.close()

def verify_original():
 B.verify_original()
 for p,h in B.read(OLD/'STUDY_FREEZE.json').items():assert B.sha(p)==h,('JAN_STUDY_DRIFT',p)
 for window in WINDOWS:
  for arm in ('PVR','DMI'):
   root=OLD/(window+'_'+arm)
   for name,h in B.read(root/'OUTPUT_SHA256.json').items():assert B.sha(root/name)==h,('JAN_OUTPUT_DRIFT',root,name)
 for name,h in B.read(O/'FEATURE_SEAL.json').items():assert B.sha(O/name)==h,('FEATURE_SEAL_DRIFT',name)
 assert C.END==END

def verify_freeze(full=True):
 p=O/'STUDY_FREEZE.json';z=B.read(p)
 for name,h in z.items():
  if full or name in [str(Path(__file__)),str(O/'PROTOCOL.json')]:assert B.sha(name)==h,('NEW_STUDY_DRIFT',name)
 return B.sha(p)

def release_gate():
 seal=verify_freeze();a=B.read(O/'PRELAUNCH_AUDIT.json');p=B.read(O/'PARENT_RELEASE.json')
 assert a['passed'] and a['study_freeze_sha256']==seal
 assert p['released'] and p['study_freeze_sha256']==seal and p['prelaunch_audit_sha256']==B.sha(O/'PRELAUNCH_AUDIT.json')
 assert B.read(O/'PVR_PREFIX_GATE.json')['passed'] and B.read(O/'FEATURE_QA.json')['passed']
 return seal

def make_context(window,out):
 print('LOAD_CONTEXT',window,flush=True);shared,receipts,cp,states,ir,identity=C.inputs();facts=shared[2];print('CONTEXT_INPUTS_READY',window,flush=True)
 closures=facts.row.__closure__;assert closures
 assert any(inspect.ismethod(x.cell_contents) and x.cell_contents.__self__ is facts for x in closures)
 original=shared[1]
 factors=E.FactorSource({sid:E.OpenFactorTimeline(raw,original.actions.get(sid,[]),method=shared[0].series[sid].record['adjustment']['method'],end=END) for sid,raw in original.raw.items() if not raw.empty})
 r,m=B.make_runner(shared,receipts,cp,states,ir,factors,window,out)
 assert r.facts.original is facts and facts.market is m and r.market is m
 assert all(a.market is m and a.facts is r.facts for a in r.accounts.values())
 assert m.phase is None
 return r,m,identity

def restore(r,path):
 """Exact immutable-context retention, full single-unpickle economic object graph."""
 meta=B.read(path.with_suffix('.json'));prov=B.read(path.with_suffix('.provenance.json'))
 h=B.sha(path);assert h==meta['sha256']==prov['checkpoint_sha256']
 expected=IO.assert_checkpoint_identity(r,path)
 for p,v in meta['source_freeze'].items():assert B.sha(p)==v,('CHECKPOINT_SOURCE_DRIFT',p)
 with path.open('rb') as f:p=pickle.load(f)
 assert set(p['accounts'])=={'PVR'} and p['source_freeze']==meta['source_freeze']
 assert p['runner']['source_freeze']==p['source_freeze']
 for k in ['integration_policy','rank_scores_manifest_sha256','remove_confirmed60']:
  assert p['runner'][k]==getattr(r,k),('POLICY_MISMATCH',k)
 assert p['runner']['rank_scores_manifest_sha256']==N.SCORES.manifest_sha256
 assert str(p['last_completed_event'])==meta['at']==prov['last_completed_event']
 kept={k:v for k,v in vars(r).items() if k in IMMUTABLE};a=r.accounts['PVR'];market,facts=a.market,a.facts
 r.__dict__=dict(p['runner'],**kept);r.accounts={'PVR':a}
 a.__dict__=dict(p['accounts']['PVR'],market=market,facts=facts)
 assert set(vars(r))-IMMUTABLE==set(p['runner'])
 assert set(vars(a))-{'market','facts'}==set(p['accounts']['PVR'])
 assert all(vars(r)[k] is v for k,v in p['runner'].items())
 assert all(vars(a)[k] is v for k,v in p['accounts']['PVR'].items())
 assert all(vars(r)[k] is v for k,v in kept.items() if k!='accounts')
 assert r.market is market and r.facts is facts and r.facts.original.market is market
 assert IO.runner_identity(r)==expected;r.assert_native_wiring()
 assert a.label=='PVR' and a.budget.exhausted_policy=='record_only'
 payload=E.payload(r);assert E.digest(payload)==E.digest(dict(runner=p['runner'],accounts=p['accounts']))
 report=dict(passed=True,path=str(path),checkpoint_sha256=h,source_freeze_count=len(p['source_freeze']),engine_identity_exact=True,all_fields_assigned_by_identity=True,all_internal_aliases_retained=True,fresh_context_retained=True,account_keys=list(r.accounts),runner_fields=len(p['runner']),account_fields=len(vars(a))-2,economic_payload_sha256=E.digest(payload),last_completed_event=p['last_completed_event'])
 return p['last_completed_event'],report

def events_after(r,m,last,stop=None):
 end=J.M.N.iso((stop or END)+'T15:10:00+08:00')
 opens={x for x in m.sessions['A'] if last<x<=end};closes={x for x in m.cutoffs if last<x<=end}
 acts={datetime.combine(datetime.fromisoformat(d).date(),dtime.min,J.M.N.TZ) for d in r.actions_by_date}
 events=sorted(opens|closes|{x for x in acts if last<x<=end})
 assert events and events[0]>last and max(closes)==end
 return events,opens,closes

def clear_memo():
 g=J.BP.A.eligibility.__globals__;assert all(k in g for k in ('memo','memo_at','memo_counts'))
 g['memo']={};g['memo_at']=None;g['memo_counts'].clear()

def compare_exact(actual,expected,label,out):
 a=E.canon(actual);b=E.canon(expected);diff=B.H.first_difference(a,b)
 if diff:B.save(out/'MISMATCH.json',dict(scope=label,diff=diff));raise AssertionError((label,diff))
 return dict(rows=len(a) if isinstance(a,list) else len(a.keys()),sha256=E.digest(a))

def record_at(x):
 if 'at' in x:return x['at']
 if x.get('kind')=='fill':return x['receipt']['at']
 if x.get('kind')=='dividend_accrual':return x['receivable']['ex_at']
 raise AssertionError(('UNKNOWN_AUDIT_TIME_SCHEMA',x))

def saved_event_time(x,key):
 value=record_at(x) if key=='account_history' else x[key]
 if key=='day':value=str(value)+'T15:10:00+08:00'
 return pd.Timestamp(value)

def baseline_prefix(r,at,last,out,old_account):
 """Compare exact saved original retained path, not a rerun as reference."""
 cut=str(at);a=r.accounts['PVR'];checks={};is_close=at.hour>=15
 for name in ('trades','decisions','audit','journal'):
  aa=getattr(a,'audit_log' if name=='audit' else name)
  bb=[x for x in old_account[name] if saved_event_time(x,'account_history')<=at]
  checks[name]=compare_exact(aa,bb,name,out)
 for file,attr,dt in [('daily','daily','at'),('opportunities','opportunities','day'),('funding','funding','at'),('industry','stage_events','day'),('balances','balance_audit','at'),('rank-policy','rank_log','day')]:
  # Restored month contains January logs; compare suffix only to avoid inherited output trims.
  lo=str(last.date());hi=str(at.date())
  aa=[x for x in getattr(r,attr) if last<saved_event_time(x,dt)<=at]
  bb=[x for x in B.rows(B.BASE/'pair'/(file+'.jsonl.gz')) if x['account']=='PVR' and last<saved_event_time(x,dt)<=at]
  checks[file]=compare_exact(aa,bb,file,out)
 aa=[dict(x,at=x['at'].isoformat()) for x in r.open_checks if last<x['at']<=at]
 bb=[x for x in B.rows(B.BASE/'OPEN_CASH_CHECKS.jsonl.gz') if x['account']=='PVR' and last<pd.Timestamp(x['at'])<=at]
 checks['OPEN_CASH_CHECKS']=compare_exact(aa,bb,'OPEN_CASH_CHECKS',out)
 if a.decisions and a.decisions[-1]['at']==at:
  checks['pending_final_rank_state']=compare_exact([{k:v for k,v in i.items() if k not in ['quote','clock','CP1_trace']} for i in a.pending],old_account['decisions'][len(a.decisions)-1]['intents'],'pending_state',out)
 return checks

def engineering(window):
 out=O/'engineering'/(window+'_verified2');out.mkdir(parents=True,exist_ok=False);B.claim(out/'ENGINEERING_ONCE.lock')
 started=time.monotonic();r,m,identity=make_context(window,out)
 with IO.atomic_runner_outputs(r,L,out,canonicalize=E.canon):
  path=OLD/(window+'_PVR')/'final_checkpoint/checkpoint.pkl';last,proof=restore(r,path)
  B.save(out/'RESTORE_PROOF.json',proof)
  first=min(x for x in m.sessions['A'] if x>last);stop=str(first.date())
  seq,opens,closes=events_after(r,m,last,stop=stop)
  J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:stop];clear_memo()
  with gzip.open(B.BASE/'pair/PVR.json.gz','rt') as f:old=json.load(f)
  checkpoints=[]
  for at in seq:
   E.event(r,m,at,opens,closes,None)
   if at in opens or at in closes:
    checks=baseline_prefix(r,at,last,out,old)
    checkpoints.append(dict(at=at,phase='OPEN' if at in opens else 'CLOSE',exact_checks=checks,full_restored_payload_sha256=E.digest(E.payload(r))))
  assert len(checkpoints)==2 and checkpoints[0]['phase']=='OPEN' and checkpoints[1]['phase']=='CLOSE'
  z=dict(passed=True,window=window,source_checkpoint=str(path),source_checkpoint_sha256=B.sha(path),events=[str(x) for x in seq],event_order='E.event: set_phase, settle_due, actions, payments, opening/planning',engineering_clone_only=True,retained_economic_paths=0,checks=checkpoints,seconds=time.monotonic()-started)
  B.save(out/'RESULT.json',z)
 print('ENGINEERING_PASS',window,round(time.monotonic()-started,1),flush=True)

def freeze():
 verify_original();results=[B.read(O/'engineering'/(w+'_verified2')/'RESULT.json') for w in WINDOWS]
 assert all(x['passed'] for x in results) and B.read(O/'COMPARATOR_REGRESSION.json')['passed']
 B.save(O/'PVR_PREFIX_GATE.json',dict(passed=True,windows=results,retained_PVR_suffix_runs=0))
 files={str(p):B.sha(p) for p in [Path(__file__),O/'build_features.py',O/'PROTOCOL.json',O/'FEATURE_SEAL.json',O/'FEATURE_QA.json',O/'FEATURE_INPUT_SHA256.json',O/'ALL_CONTINUATION_DMI_FEATURES.parquet',O/'PVR_PREFIX_GATE.json',O/'check_comparator.py',O/'COMPARATOR_REGRESSION.json',O/'ENGINEERING_PREPARATION_FAILURES.json',O/'FEATURE_PREPARATION_ATTEMPT1.json']}
 files.update(B.read(O/'FEATURE_INPUT_SHA256.json'));files.update(B.read(OLD/'STUDY_FREEZE.json'))
 for w in WINDOWS:
  for name in ['RESULT.json','RESTORE_PROOF.json']:files[str(O/'engineering'/(w+'_verified2')/name)]=B.sha(O/'engineering'/(w+'_verified2')/name)
  for arm in ('PVR','DMI'):
   root=OLD/(w+'_'+arm)
   for n in ['OUTPUT_SHA256.json','DONE.json','OPEN_RESTART_POISON_GATE.json','final_checkpoint/checkpoint.pkl','final_checkpoint/checkpoint.json','final_checkpoint/checkpoint.provenance.json']:files[str(root/n)]=B.sha(root/n)
 for n in ['CLOSE_PHYSICAL_PREFIX_QA.json','close_prefix_gate.py','DMI_RELEASE_AUDIT.json','PRELAUNCH_AUDIT.json','FINAL_INDEPENDENT_AUDIT.json']:files[str(OLD/n)]=B.sha(OLD/n)
 for n in ['OUTPUT_HASHES.json','RUNTIME_DEPENDENCY_FREEZE.json','DONE.json']:files[str(B.BASE/n)]=B.sha(B.BASE/n)
 assert not (O/'STUDY_FREEZE.json').exists();B.save(O/'STUDY_FREEZE.json',files)
 print('FROZEN',B.sha(O/'STUDY_FREEZE.json'),len(files),flush=True)

def run(window):
 seal=release_gate();verify_original();out=O/(window+'_DMI');out.mkdir(exist_ok=False);B.claim(out/'RUN_ONCE.lock')
 started=time.monotonic();r=None;last=None;failed=None;count=0;audit=None
 try:
  r,m,identity=make_context(window,out);feat=FeatureLookup()
  with IO.atomic_runner_outputs(r,L,out,canonicalize=E.canon):
   source=OLD/(window+'_DMI')/'final_checkpoint/checkpoint.pkl';last,proof=restore(r,source)
   B.save(out/'RESTORE_PROOF.json',proof);initial=r.daily[-1]
   assert str(last.date())==B.WINDOWS[window][1]
   B.save(out/'INITIAL_STATE.json',dict(window=window,initial_daily=initial,last_completed=last,source_checkpoint=str(source),source_checkpoint_sha256=B.sha(source),source_January_initial_state=str(OLD/(window+'_DMI')/'INITIAL_STATE.json'),policy='DMI continuously, original ACT, no profit add gate',starting_payload_sha256=proof['economic_payload_sha256']))
   seq,opens,closes=events_after(r,m,last);expected_days=len(closes)
   J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:END];clear_memo()
   audit=RankAudit(out/'DMI_RANK_AUDIT.jsonl.gz');start_counts={k:len(getattr(r,k)) for k in B.OUTPUT_LOGS};starttr=len(r.accounts['PVR'].trades)
   for at in seq:
    failed=at;verify_freeze(full=False)
    # First suffix OPEN consumes frozen January pending unchanged. Every suffix
    # CLOSE must execute the same January driver reorder, including final CLOSE.
    B.execute_event(r,m,at,opens,closes,'DMI',feat,audit);last=at;count+=1;failed=None
    if at in closes and ((pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month or at==max(closes)):
     print('MONTH',window,str(at.date()),str(r.accounts['PVR'].current_nav),'seconds',round(time.monotonic()-started,1),flush=True)
   audit.close();assert len(r.daily)-start_counts['daily']==expected_days and str(last.date())==END
   assert verify_freeze()==seal;verify_original()
   r.source_freeze.update({str(p):B.sha(p) for p in [Path(__file__),O/'PROTOCOL.json',O/'STUDY_FREEZE.json',O/'ALL_CONTINUATION_DMI_FEATURES.parquet',O/'PRELAUNCH_AUDIT.json',O/'PARENT_RELEASE.json']})
   r.checkpoint(out/'final_checkpoint',last);r.dump_joint(out/'pair')
   IO.write_gzip_jsonl(out/'OPEN_CASH_CHECKS.jsonl.gz',r.open_checks,encoder=J.C.encoded)
   IO.write_gzip_jsonl(out/'SHARED_WINDOW_AUDIT.jsonl.gz',m.exec_rows,encoder=J.C.encoded)
   a=r.accounts['PVR'];end=r.daily[-1];tr=a.trades[starttr:]
   B.save(out/'DONE.json',dict(completed=True,study_freeze_sha256=seal,window=window,arm='DMI',last_event=last,retained_suffix_events=count,suffix_days=expected_days,daily_rows_total=len(r.daily),initial_NAV=initial['nav'],ending_NAV=end['nav'],initial_fees=initial['fees_cny'],final_fees=end['fees_cny'],suffix_fees=end['fees_cny']-initial['fees_cny'],suffix_buy_fills=sum(t['side']=='buy' for t in tr),suffix_sell_fills=sum(t['side']=='sell' for t in tr),pending_end=len(a.pending),positions_end=len(end['positions']),rank_rows=audit.count,rank_UNKNOWN=audit.unknown,rank_moved=audit.moved,rank_audit_scope='suffix only; January original rank file is immutable and separate',output_log_start_counts=start_counts,initial_checkpoint_sha256=proof['checkpoint_sha256'],seconds=time.monotonic()-started,original_sources_unchanged=True,no_forced_exit=True,real_orders=False,fixed_future_NONPIT=True,tradability_UNKNOWN=True,development_seen_not_OOS=True))
  B.save(out/'OUTPUT_SHA256.json',{str(p.relative_to(out)):B.sha(p) for p in out.rglob('*') if p.is_file() and p.name!='OUTPUT_SHA256.json'})
  print('DONE',window,round(time.monotonic()-started,1),flush=True)
 except BaseException as e:
  if audit:
   try:audit.close()
   except BaseException:pass
  B.save(out/'FAILURE_NO_AUTO_RETRY.json',dict(error=repr(e),traceback=traceback.format_exc(),last_completed_event=last,failed_event=failed,retained_suffix_events=count,no_automatic_economic_rerun=True,partial_state_not_resumable=True))
  if r is not None:
   try:IO.write_pickle(out/'PARTIAL_DIAGNOSTIC_NOT_CHECKPOINT.pkl',dict(last_completed_event=last,failed_event=failed,payload=E.payload(r)))
   except BaseException as q:B.save(out/'PARTIAL_SNAPSHOT_FAILURE.json',dict(error=repr(q)))
  raise

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['engineering','freeze','run']);p.add_argument('--window',choices=WINDOWS);x=p.parse_args()
 if x.phase=='freeze':freeze()
 elif x.phase=='engineering':assert x.window;engineering(x.window)
 else:assert x.window;run(x.window)
if __name__=='__main__':main()
