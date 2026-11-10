"""Append-only authorized month continuation of the SAME reviewed runner."""
from pathlib import Path
from dataclasses import asdict
import argparse,hashlib,json,pickle,sys,time,traceback
O=Path(__file__).resolve().parent;CORE=O.parent/'C-rights-month-resume-v2-20261102'
sys.path.insert(0,str(CORE));import resume_runtime_v2 as C
sha=C.sha;read=C.read
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=C.E.encode)+'\n');tmp.replace(p)
def guard(arm):
 a=read(O/'AUTHORIZATION.json')
 for p,h in a['sources'].items():C.require(sha(p)==h,'month entry/source changed '+p)
 C.require(a['parent_approved'] and a['cutoff']=='2022-01-28' and arm in a['arms'],'wrong month execution scope')
 return a
def brief(r):
 at=r.last_completed_event;a=r.account;b=a.bridge(at)
 return dict(cursor=str(at),balance=b,fees=a.fees_cny,positions=len(a.positions),pending=len(a.pending),buys=len(a.buys),exits=len(a.exits),certificates=len(r.authority.certificates),New=r.budget.batch['new'],Carry=r.budget.batch['carry'],budget=r.budget.dumps())
def persist(r,arm,label,flow):
 root=CORE/'runs'/arm/'full';bankfile=root/'REGISTRY.json';bank=read(bankfile)
 C.require(not any(x['label']==label for x in bank['checkpoints']),'completed phase cannot replay')
 cp=root/(label+'.pkl');C.require(not cp.exists(),'checkpoint target exists')
 r.assert_observers();state=brief(r);sf=root/(label+'-FIELDS.json');save(sf,C.FP.snapshot(r));ff=root/(label+'-FLOW.json');save(ff,flow)
 r.checkpoint(cp)
 rec=dict(checkpoint=str(cp),sha256=sha(cp),provenance_sha256=sha(cp.with_suffix('.provenance.json')),fields=str(sf),fields_sha256=sha(sf),flow=str(ff),flow_sha256=sha(ff),cursor=str(r.last_completed_event),label=label,financial_sha256=hashlib.sha256(C.R.conservation_bytes(r)).hexdigest())
 # Preserve every prior registry version byte-for-byte; old checkpoint,
 # provenance, input, code and Jan13 reports are never overwritten.
 previous_sha=sha(bankfile);history=O/'registry_history'/arm/(previous_sha+'.json')
 if not history.exists():history.parent.mkdir(parents=True,exist_ok=True);history.write_bytes(bankfile.read_bytes())
 bank['checkpoints'].append(rec);save(bankfile,bank)
 progress=dict(arm=arm,record=rec,registry=str(bankfile),registry_sha256=sha(bankfile),previous_registry_sha256=previous_sha,state=state)
 save(O/'progress'/(arm+'.json'),progress);save(O/'event_states'/arm/(label+'.json'),state)
 return rec
def main():
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=['2022-C10','2022-C_BATCH20'],required=True);args=p.parse_args();arm=args.arm;a=guard(arm);origin=a['arms'][arm]
 C.require(not(O/'progress'/(arm+'.json')).exists(),'no silent resume/replay; use a separately explicit trusted recovery')
 C.require(sha(origin['checkpoint'])==origin['checkpoint_sha256'] and sha(origin['registry'])==origin['trusted_registry_sha256'],'Jan13 trusted anchor changed')
 r=None;phase=None;day=None
 try:
  r=C.ContinuationRunner.restore(origin['checkpoint'],registry_sha=origin['trusted_registry_sha256'])
  C.require(str(r.last_completed_event)=='2022-01-13 15:10:00+08:00' and r.mode==arm[5:] and r.window=='2022','wrong continuous Jan13 state')
  before=C.FP.snapshot(r);financial=C.R.conservation_bytes(r);g=a['grants'][arm]
  C.require(read(g['path'])['start_checkpoint_sha256']==sha(origin['checkpoint']),'new grant not bound to exact Jan13 anchor')
  r.accept_continuation_grant(g['path'],trusted_sha=g['sha256']);after=C.FP.snapshot(r);diff=C.FP.compare(before,after)
  C.require(set(diff['changed'])<=set(['runner.continuation_grant_record','runner.continuation_grant_history']) and C.R.conservation_bytes(r)==financial,'grant upgrade changed financial state')
  persist(r,arm,'GRANT-2022-JAN-END',dict(no_financial_event=True,complete_field_diff=diff,start_checkpoint_sha256=sha(origin['checkpoint']),grant_sha256=g['sha256']))
  days=[d for d in r.inputs.days if '2022-01-13'<d<='2022-01-28'];C.require(days==a['days'] and days[-1]=='2022-01-28','frozen month days mismatch')
  for day in days:
   phases=(['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']
   for phase in phases:
    C.require(not(O/'STOP.json').exists(),'another arm stopped: no further event')
    guard(arm);at=C.E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    C.require(at>r.last_completed_event,'completed old event may not replay')
    before_state=brief(r);n=len(r.account.fills);events=len(r.events);clock=r.last_completed_event;t=time.monotonic()
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    C.require(r.last_completed_event==at and len(r.events)==events+1 and r.events[-1]['phase']==phase,'exact one ordered phase required')
    if phase=='CLOSE':C.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','necessary CLOSE saved but optional planning incomplete; stop')
    flow=dict(day=day,phase=phase,before=before_state,after=brief(r),fills=[asdict(v) for v in r.account.fills[n:]],before_cursor=str(clock),cursor=str(at),added_events=1,seconds=time.monotonic()-t)
    persist(r,arm,day+'-'+phase,flow)
    print('COMMITTED',arm,day,phase,'fills',len(flow['fills']),'NAV',flow['after']['balance']['nav'],'seconds',round(time.monotonic()-t,2),flush=True)
  C.require(str(r.last_completed_event)=='2022-01-28 15:10:00+08:00','must stop at Jan final CLOSE')
  save(O/(arm+'-DONE.json'),dict(passed=True,cursor=str(r.last_completed_event),new_events=23,no_February=True,progress=read(O/'progress'/(arm+'.json'))))
 except BaseException as exc:
  error=dict(arm=arm,day=day,phase=phase,error=repr(exc),traceback=traceback.format_exc(),last_cursor=str(r.last_completed_event) if r else None,no_skip_no_auto_retry=True,last_trusted=read(O/'progress'/(arm+'.json')) if(O/'progress'/(arm+'.json')).exists() else origin)
  save(O/(arm+'-ERROR.json'),error)
  if r:
   target=O/(arm+'-FAILED_WORKING.pkl');target.write_bytes(pickle.dumps(r,pickle.HIGHEST_PROTOCOL));error['failed_working_sha256']=sha(target);save(O/(arm+'-ERROR.json'),error)
  try:
   with(O/'STOP.json').open('x') as f:json.dump(error,f,ensure_ascii=False,indent=2)
  except FileExistsError:pass
  raise
if __name__=='__main__':main()
