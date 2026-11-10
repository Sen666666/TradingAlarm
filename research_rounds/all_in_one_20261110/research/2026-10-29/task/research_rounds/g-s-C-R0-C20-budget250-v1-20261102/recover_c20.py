"""One explicit technical recovery, then same C20 account through Jul31."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,pickle,sys,json,time,traceback,subprocess
import budget250 as B
X=B.X;E=B.E;P=B.HERE;OLD=B.OLD;OUT=P/'runs/C_BATCH20';AT=B.AT

def old_load(path):
 side=X.read(path.with_suffix('.provenance.json'));E.require(X.sha(path)==side['checkpoint_sha256'],'original failed checkpoint changed');r=pickle.loads(path.read_bytes());r.account.owner=r
 E.require(type(r) is X.Runner and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'old frozen source/engine mismatch');r.assert_observers();return r

def freeze(r):
 files=[OLD/'runs/C_BATCH20/FAILED_WORKING_STATE.pkl',OLD/'C20_FAILED_PROJECTION_INPUT.json',OLD/'C20_PURE_SEARCH_RESULT.json',OLD/'C20_BLOCKED_STAGE_VERIFICATION.json']
 a=dict(scope='ONLY_C20_R0_JUL22_OPTIONAL_THEN_JUL31',parent_approved=True,financial_events_authorized=True,root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',old_technical_ceiling=100000,technical_ceiling=250000,no_economic_change=True,end='2025-07-31',runtime_sha256=X.sha(P/'budget250.py'),entry_sha256=X.sha(__file__),old_runtime_sha256=B.OLD_RUNTIME,old_entry_sha256=B.OLD_ENTRY,immutable_original_artifacts={str(f):X.sha(f) for f in files},legacy_certificate_ids=sorted(r.authority.certificates),legacy_source_binding_digest=E.digest(r.source_binding()),parent_authorization='Raise only exact-search technical budget to bounded250000; compare completed and failed pure Q/D; explicit optional-only retry with failure history, then original C20 throughJul31. No CLOSE necessary replay, no new account or changed economic predicate.')
 if B.AUTH.exists():E.require(X.read(B.AUTH)==a,'existing source transition authorization differs')
 else:X.save(B.AUTH,a)
 return a

def import_failed():
 cp=OLD/'runs/C_BATCH20/FAILED_WORKING_STATE.pkl';r=old_load(cp);E.require(r.mode=='C_BATCH20' and r.last_completed_event==AT and r.close_stages[AT.isoformat()]['optional_status']=='failed_exception','specific saved failure required')
 a=freeze(r);before=E.digest(B.economic_view(r));r.legacy_certificates=copy.deepcopy(r.authority.certificates);r.__class__=B.Runner;r.account.owner=r
 r.technical_recovery=dict(status='imported_necessary_only',parent_checkpoint=str(cp),parent_sha256=X.sha(cp),technical_ceiling=250000,old_ceiling=100000,original_cursor=str(AT),legacy_registry_unchanged=True)
 r.bind_execution(B.AUTH);E.require(E.digest(B.economic_view(r))==before,'source import changed complete economic/strategy prefix');r.assert_observers()
 P.mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);r.checkpoint(P/'IMPORT_NECESSARY.pkl');X.save(P/'IMPORT_MANIFEST.json',dict(prefix_before_sha256=before,prefix_after_sha256=E.digest(B.economic_view(r)),exact=True,old_checkpoint_sha256=a['immutable_original_artifacts'][str(cp)],old_certificates_not_rewritten=True,account_class_unchanged=True,actual_new_engine=E.IO.runner_identity(r),source_binding=r.source_binding()))
 return r

def pure_gates(r):
 t=time.perf_counter();records=[]
 for old in r.results:
  cert=old['certificate'];v=r.trusted[cert['trusted_id']];new=r._solve(v['snapshot'],v['demands'],v['evidence'],v['budget_before'])
  E.require(new==old['projection'],'250k changed completed exact batch')
  records.append(dict(at=old['at'],Q_D_and_entire_projection_exact=True,native_checks=new['native_checks'],hash=E.digest(new)))
  print('PAST_EXACT',old['at'],new['native_checks'],flush=True)
 original=X.read(OLD/'C20_FAILED_PROJECTION_INPUT.json');expected=X.read(OLD/'C20_PURE_SEARCH_RESULT.json')['pure_result']
 clone=pickle.loads(pickle.dumps(r));clone.account.owner=clone;st=clone.close_stages[AT.isoformat()];e=st['evidence'];ints=st['prepared_intents'];s,ds,wait=clone.provider(AT,ints,e);clone._init_or_bind(s,ints,e);bb=clone.budget.dumps()
 E.require(E.digest(dict(snapshot=s,demands=ds,evidence=e,budget_before=bb))==E.digest({k:original[k] for k in ('snapshot','demands','evidence','budget_before')}),'recovered pure input differs from original failed input')
 got=clone._solve(s,ds,e,bb);E.require(got==expected,'250k differs from saved exact1m result')
 # Carry only the exact immutable pure memo, after computing under THIS actual
 # 250k function/source/input token. No budget/financial state copied back.
 before=E.digest(B.economic_view(r));r._pure_projection_memo=copy.deepcopy(clone._pure_projection_memo);E.require(E.digest(B.economic_view(r))==before,'memo transfer changed economic state')
 X.save(P/'PURE_GATE.json',dict(passed=True,old_batches=records,failed_input_exact=True,failed_result_entire_exact=True,failed_checks=got['native_checks'],technical_ceiling=250000,actual_new_solver_sha256=X.sha(P/'budget250.py'),original_failed_input_sha256=X.sha(OLD/'C20_FAILED_PROJECTION_INPUT.json'),original_pure_result_sha256=X.sha(OLD/'C20_PURE_SEARCH_RESULT.json'),seconds=time.perf_counter()-t,financial_events=0))
 r.technical_recovery['pure_gate']=dict(path=str(P/'PURE_GATE.json'),sha256=X.sha(P/'PURE_GATE.json'))
 return got

def restore_gate(path):
 r=B.Runner.restore(path);before=E.digest(B.economic_view(r));tech=E.digest(r.technical_recovery);out=r.retry_technical_optional();E.require(out['state']=='TECHNICAL_RECOVERY_ALREADY_SUCCEEDED' and before==E.digest(B.economic_view(r)) and tech==E.digest(r.technical_recovery),'restore retry was not idempotent')
 E.require(json.loads(json.dumps(r.observable(AT),default=E.encode))==X.read(path.with_suffix('.json')),'cross-process complete state differs')
 X.save(P/'RESTORE_GATE.json',dict(passed=True,checkpoint_sha256=X.sha(path),actual_source_engine_equal=True,complete_observable_equal=True,idempotence=True,financial_events=0,source_sha256=X.sha(P/'budget250.py')));print('RESTORE_GATE_PASS',flush=True)

def continue_month(r):
 t=time.perf_counter();X.save(OUT/'CONTINUATION_STARTED.json',dict(at=datetime.now(timezone.utc).isoformat(),cursor=r.last_completed_event,source=r.source_binding(),technical_ceiling=250000))
 for day in r.inputs.days:
  if not '2025-07-23'<=day<='2025-07-31':continue
  for phase in ((['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']):
   at=E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
   if r.last_completed_event>=at:continue
   r.checkpoint(OUT/'BEFORE_EVENT.pkl');s=time.perf_counter();nf=len(r.account.fills)
   if phase=='ACTION':r.corporate_actions(day)
   else:r.step(day,phase)
   if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','optional planning did not finish')
   p=OUT/(day+'-'+phase+'.pkl');r.checkpoint(p);X.save(p.with_suffix('.json'),r.observable(at));X.save(OUT/'PROGRESS.json',dict(checkpoint=str(p),sha256=X.sha(p),cursor=r.last_completed_event,phase=phase));X.save(OUT/(day+'-'+phase+'-FLOW.json'),dict(seconds=time.perf_counter()-s,new_fills=[X.asdict(v) for v in r.account.fills[nf:]],bridge=r.account.bridge(at),memo_hits=r._memo_hits,memo_misses=r._memo_misses))
   print('COMPLETED_EVENT',day,phase,len(r.account.fills)-nf,round(time.perf_counter()-s,3),flush=True)
 X.save(OUT/'COMPLETED.json',dict(cutoff='2025-07-31',actual_at=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-t,cursor=r.last_completed_event,checkpoint=X.read(OUT/'PROGRESS.json'),no_August=True))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--restore-gate',type=Path);a=ap.parse_args()
 if a.restore_gate:return restore_gate(a.restore_gate)
 E.require(a.execute,'explicit authorized execute required');E.require(not (P/'IMPORT_NECESSARY.pkl').exists(),'no automatic re-import/replay of completed stages');r=None
 try:
  r=import_failed();pure_gates(r);r.checkpoint(P/'BEFORE_OPTIONAL.pkl');before=E.digest(B.economic_view(r));s=time.perf_counter();r.retry_technical_optional()
  after=E.digest(B.economic_view(r));tech=E.digest(r.technical_recovery);E.require(r.retry_technical_optional()['state']=='TECHNICAL_RECOVERY_ALREADY_SUCCEEDED' and after==E.digest(B.economic_view(r)) and tech==E.digest(r.technical_recovery),'same-process retry not idempotent')
  p=OUT/'2025-07-22-CLOSE.pkl';r.checkpoint(p);X.save(p.with_suffix('.json'),r.observable(AT));X.save(OUT/'2025-07-22-CLOSE-FLOW.json',dict(seconds=time.perf_counter()-s,new_fills=[],bridge=r.account.bridge(AT),memo_hits=r._memo_hits,memo_misses=r._memo_misses,optional_only=True));X.save(OUT/'PROGRESS.json',dict(checkpoint=str(p),sha256=X.sha(p),cursor=AT,phase='CLOSE'))
  X.save(P/'OPTIONAL_RECOVERY_GATE.json',dict(passed=True,source_import_exact=True,old_failed_attempts_preserved=True,necessary_phase_not_replayed=True,no_native_trades=True,same_process_idempotence=True,before_sha256=before,after_sha256=after,checkpoint_sha256=X.sha(p)))
  subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--restore-gate',str(p)],check=True)
  E.require(X.read(P/'RESTORE_GATE.json')['checkpoint_sha256']==X.sha(p),'wrong cross-process restore target');r.technical_recovery['restore_gate']=dict(path=str(P/'RESTORE_GATE.json'),sha256=X.sha(P/'RESTORE_GATE.json'));r.checkpoint(P/'READY_TO_CONTINUE.pkl')
  continue_month(r)
 except BaseException as ex:
  X.save(P/'RECOVERY_ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),cursor=r.last_completed_event if r else None,no_auto_replay=True))
  if r:r.checkpoint(P/'FAILED_RECOVERY_STATE.pkl')
  raise
if __name__=='__main__':main()
