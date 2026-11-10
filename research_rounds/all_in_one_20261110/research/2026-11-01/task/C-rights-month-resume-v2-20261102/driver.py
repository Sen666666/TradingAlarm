"""One phase per process; exact registered restore, no ACTION in event loop."""
from pathlib import Path
from dataclasses import asdict
import argparse,hashlib,json,pickle,traceback
import resume_runtime_v2 as C
from compare_resume_v2 import hashes
O=C.O;DAY='2022-01-13'
def save(p,x):
 Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=C.E.encode)+'\n')
def persist(r,out,label,flow):
 r.assert_observers()
 for cert in r.authority.certificates.values():r.verify_native(cert)
 projection=hashes(r);fields=C.FP.snapshot(r)
 sf=out/(label+'-FIELDS.json');save(sf,fields);save(out/(label+'-FLOW.json'),flow);save(out/(label+'-COMPARISON.json'),projection)
 cp=out/(label+'.pkl');r.checkpoint(cp)
 rec=dict(checkpoint=str(cp),sha256=C.sha(cp),provenance_sha256=C.sha(cp.with_suffix('.provenance.json')),fields=str(sf),fields_sha256=C.sha(sf),comparison=str(out/(label+'-COMPARISON.json')),comparison_sha256=C.sha(out/(label+'-COMPARISON.json')),flow=str(out/(label+'-FLOW.json')),flow_sha256=C.sha(out/(label+'-FLOW.json')),cursor=str(r.last_completed_event),label=label,financial_sha256=hashlib.sha256(C.R.conservation_bytes(r)).hexdigest())
 bankfile=out/'REGISTRY.json';bank=C.read(bankfile) if bankfile.exists() else dict(identity_sha256=C.sha(O/'IDENTITY.json'),checkpoints=[])
 C.require(not any(v['label']==label for v in bank['checkpoints']),'registered phase already exists');bank['checkpoints'].append(rec);save(bankfile,bank)
 print('REGISTERED',out.parent.name,out.name,label,rec['sha256'],'registry',C.sha(bankfile),flush=True)
 return rec
def restore_latest(out):
 bank=out/'REGISTRY.json';rec=C.read(bank)['checkpoints'][-1]
 return C.ContinuationRunner.restore(rec['checkpoint'],registry_sha=C.sha(bank))
def main():
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=['2022-C10','2022-C_BATCH20'],required=True);p.add_argument('--branch',choices=['full','physical'],required=True);p.add_argument('--phase',choices=['IMPORT','OPEN','CLOSE','CHECK'],required=True);a=p.parse_args()
 out=O/'runs'/a.arm/a.branch;out.mkdir(parents=True,exist_ok=True);r=None
 try:
  if a.phase=='IMPORT':
   C.require(not (out/'REGISTRY.json').exists(),'import already registered');r,e=C.import_action(a.arm,a.branch);persist(r,out,'IMPORT',e);return
  r=restore_latest(out)
  if a.phase=='CHECK':
   before=C.FP.snapshot(r);rejected=[]
   g=C.read(O/'INITIAL_GRANTS.json');other='2022-C_BATCH20' if a.arm=='2022-C10' else '2022-C10'
   for label,fn in [('Jan14',lambda:r.execution_guard('2022-01-14','OPEN')),('native_arbitrary_clock',lambda:r.event(C.E.iso('2022-01-13T09:31:00+08:00'))),('wrong_arm_grant',lambda:C.validate(r,g[other+'|'+a.branch]['path'],g[other+'|'+a.branch]['sha256'])),('wrong_registry',lambda:C.ContinuationRunner.restore(C.read(out/'REGISTRY.json')['checkpoints'][-1]['checkpoint'],registry_sha='0'*64)),('unregistered_snapshot',lambda:C.ContinuationRunner.restore(out/'arbitrary.pkl',registry_sha=C.sha(out/'REGISTRY.json'))),('old_ACTION_registry_rejects_new_class',lambda:C.A.ActionRunner.restore(C.read(out/'REGISTRY.json')['checkpoints'][-1]['checkpoint'],registry_sha=C.guard()['parent_registry_sha256']))]:
    try:fn()
    except ValueError:rejected.append(label)
    else:raise ValueError('forbidden scope accepted '+label)
   C.require(C.FP.snapshot(r)==before,'read-only rejection tests changed state')
   save(out/'RESTORE_CHECK.json',dict(passed=True,cursor=str(r.last_completed_event),full_fields_exact=True,certificates_recomputed=len(r.authority.certificates),rejected=rejected,no_ACTION_replay=True));print('CHECKED',a.arm,a.branch,flush=True);return
  expected=C.A.AT if a.phase=='OPEN' else C.E.iso(DAY+'T09:30:00+08:00')
  C.require(r.last_completed_event==expected,'unexpected starting cursor; no automatic replay')
  count=len(r.events);actions=C.FP.digest(r.no_subscription_actions);action_log=C.FP.digest(r.action_log);oldfills=len(r.account.fills);before_balance=r.account.bridge(r.last_completed_event);before_budget=r.budget.dumps();before_event=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
  (out/('BEFORE-'+a.phase+'.pkl')).write_bytes(before_event)
  r.step(DAY,a.phase)
  at=C.E.iso(DAY+('T09:30:00+08:00' if a.phase=='OPEN' else 'T15:10:00+08:00'))
  C.require(r.last_completed_event==at and len(r.events)==count+1 and r.events[-1]['phase']==a.phase,'one exact financial phase required')
  C.require(C.FP.digest(r.no_subscription_actions)==actions and C.FP.digest(r.action_log)==action_log,'completed ACTION was changed/replayed')
  if a.phase=='CLOSE':C.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','native optional close did not finish; stop')
  flow=dict(before_balance=before_balance,after_balance=r.account.bridge(at),budget_before=before_budget,budget_after=r.budget.dumps(),fills=[asdict(v) for v in r.account.fills[oldfills:]],added_events=1,added_ACTIONs=0,phase=a.phase,at=at)
  persist(r,out,DAY+'-'+a.phase,flow)
 except Exception as exc:
  error=dict(error=repr(exc),traceback=traceback.format_exc(),last_cursor=str(r.last_completed_event) if r else None,phase=a.phase,automatic_retry=False)
  save(out/('ERROR-'+a.phase+'.json'),error)
  if r:(out/('FAILED-'+a.phase+'.pkl')).write_bytes(pickle.dumps(r,pickle.HIGHEST_PROTOCOL))
  raise
if __name__=='__main__':main()
