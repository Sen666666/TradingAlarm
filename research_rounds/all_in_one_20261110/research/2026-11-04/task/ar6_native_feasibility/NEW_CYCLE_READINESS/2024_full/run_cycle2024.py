"""Prepared own-state2024 launch only; execution requires exact root grant."""
from pathlib import Path
import argparse,gc,time,traceback
import cycle2024_adapter as C
def manifest_path(p):return C.root(p)/'PROPOSED_FULL_EXECUTION_FREEZE.json'
def prepare(policy):
 root=C.root(policy);gate=C.read(root/'TECHNICAL_GATE.json');cross=C.read(root/'CROSS_PROCESS_GATE.json')
 assert gate['passed']and cross['passed']and cross['separate_process']
 base=gate['source_freeze'];assert C.source_freeze(policy)==base
 for p,h in base.items():assert C.sha(p)==h
 cp=root/'first-session/full-input/checkpoint.pkl'
 paths=[Path(__file__),C.O/'FULL2024_CARD.txt',root/'TECHNICAL_GATE.json',root/'CROSS_PROCESS_GATE.json',cp,cp.with_suffix('.json'),cp.with_suffix('.provenance.json')]
 entry=dict(base);entry.update({str(p.resolve()):C.sha(p)for p in paths})
 value=dict(policy=policy,scope='ONE_OWN_STATE_2024_CONTINUATION',end='2024-12-31',
  resume_after='2024-01-02 15:10:00+08:00',firstday_checkpoint=str(cp),checkpoint_source_freeze=base,
  entry_sources=entry,firstday_not_rerun=True,financial_authorized_by_preparation=False)
 path=manifest_path(policy)
 if path.exists():assert C.read(path)==value
 else:C.save(path,value)
 proposal=dict(approved=False,policy=policy,scope=value['scope'],end=value['end'],resume_after=value['resume_after'],
  execution_freeze_sha256=C.sha(path),adapter_sha256=C.sha(C.__file__),binding_sha256=C.sha(C.binding_path(policy)))
 C.save(root/'PROPOSED_FULL_2024_AUTHORIZATION.json',proposal)
 print('PREPARED_NO_EXECUTION',policy,C.sha(path),flush=True)

def execute(a):
 policy=a.policy;root=C.root(policy);path=manifest_path(policy);f=C.read(path);auth=C.read(a.authorization_file)
 assert a.authorization_file.resolve()==(root/'FULL_2024_RUN_AUTHORIZATION.json').resolve()
 assert auth['approved']is True and auth['scope']=='ONE_OWN_STATE_2024_CONTINUATION'and auth['policy']==policy
 assert auth['end']==f['end']=='2024-12-31'and auth['resume_after']==f['resume_after']=='2024-01-02 15:10:00+08:00'
 assert auth['execution_freeze_sha256']==C.sha(path)and auth['adapter_sha256']==C.sha(C.__file__)and auth['binding_sha256']==C.sha(C.binding_path(policy))
 assert all(C.sha(p)==h for p,h in f['entry_sources'].items())
 out=root/'run-2024';assert not(out/'DONE.json').exists(),'completed2024 cannot repeat'
 if not a.resume_checkpoint:assert not(out/'checkpoint.pkl').exists()and not(out/'FAILURE.json').exists(),'partial/failure requires explicit reconciliation/resume'
 started=time.monotonic();C.N.configure_scores(C.NEW_SCORE)
 shared,receipts,cp,states,ir,identity=C.inputs();r=C.CLASSES[policy](shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 r.source_freeze=dict(f['checkpoint_source_freeze']);resume=a.resume_checkpoint or Path(f['firstday_checkpoint'])
 if a.resume_checkpoint:assert resume.resolve().parent==out.resolve(),'only own same-path CP may resume'
 with C.IO.atomic_runner_outputs(r,C.L,out,canonicalize=C.J.W.canon):cursor=r.restore(resume)
 if not a.resume_checkpoint:assert str(cursor)==f['resume_after']
 extra=dict(f['entry_sources']);extra[str(a.authorization_file.resolve())]=C.sha(a.authorization_file)
 C.save(out/'EXECUTION_FREEZE.json',dict(checkpoint_source_freeze_preserved=r.source_freeze,entry_sources=extra,identity=identity))
 C.save(out/('RESUME_METADATA.json'if a.resume_checkpoint else'RUN_METADATA.json'),dict(policy=policy,parent_2023_NAV=C.read(C.binding_path(policy))['parent_NAV'],
  resume_after=str(cursor),Jan2_not_replayed=True,no_account_reset=True,authorization_file=str(a.authorization_file),authorization_sha256=C.sha(a.authorization_file),
  execution_freeze_sha256=C.sha(path),initial_economic_state='each own2023 path plus already committed Jan2 technical prefix'))
 print('CYCLE2024_STARTED',policy,str(cursor),flush=True)
 with C.IO.atomic_runner_outputs(r,C.L,out,canonicalize=C.J.W.canon):complete=r.run_prepared(out,a.seconds,resume_after=cursor,end='2024-12-31')
 assert all(C.sha(p)==h for p,h in extra.items())
 C.save(out/'TIMING.json',dict(completed=complete,total_seconds=time.monotonic()-started,event_loop_seconds=r.run_seconds if complete else None,automatic_exception_retry=False))
 print('CYCLE2024_SAVED',policy,complete,str(r.accounts['B'].current_nav),round(time.monotonic()-started,2),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--policy',choices=['original','no60'],required=True);ap.add_argument('--prepare',action='store_true');ap.add_argument('--execute',action='store_true')
 ap.add_argument('--authorization-file',type=Path);ap.add_argument('--resume-checkpoint',type=Path);ap.add_argument('--seconds',type=float,default=600);a=ap.parse_args();assert a.prepare!=a.execute
 try:
  if a.prepare:prepare(a.policy)
  else:assert a.authorization_file;execute(a)
 except BaseException as e:
  if a.execute:C.save(C.root(a.policy)/'run-2024/FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
  raise
