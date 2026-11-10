"""One continuous fixed July path per original mode; no daily approval/auto replay."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,time,traceback
import month_r0 as X
E=X.E

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['C10','C_BATCH20'],required=True);p.add_argument('--authorization',type=Path,required=True);a=p.parse_args()
 g=X.read(a.authorization);E.require(g.get('parent_approved') is True and g.get('independent_audit_PASS') is True and g.get('financial_events_authorized') is True,'MONTH NOT AUTHORIZED; preparation only')
 out=X.HERE/'runs'/a.mode;out.mkdir(parents=True,exist_ok=True);r=None;t=time.perf_counter()
 try:
  prog=out/'PROGRESS.json'
  if prog.exists():
   z=X.read(prog);E.require(X.sha(z['checkpoint'])==z['sha256'],'last checkpoint changed');r=X.Runner.restore(z['checkpoint'])
  else:r=X.Runner.restore(X.read(X.HERE/'INITIAL_CHECKPOINTS.json')['accounts'][a.mode]['path'])
  r.bind_execution(a.authorization);X.save(out/'STARTED.json',dict(at=datetime.now(timezone.utc).isoformat(),cursor=r.last_completed_event,initial_state_hash=r.initial_state_hash,source=r.source_binding()))
  for day in r.inputs.days:
   for phase in ((['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']):
    at=E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    if r.last_completed_event and r.last_completed_event>=at:continue
    r.checkpoint(out/'BEFORE_EVENT.pkl');s=time.perf_counter();old=len(r.account.fills)
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','optional phase blocked; no auto-retry')
    cp=out/(day+'-'+phase+'.pkl');r.checkpoint(cp);X.save(out/(day+'-'+phase+'.json'),r.observable(at))
    X.save(prog,dict(checkpoint=str(cp),sha256=X.sha(cp),cursor=r.last_completed_event,phase=phase))
    X.save(out/(day+'-'+phase+'-FLOW.json'),dict(seconds=time.perf_counter()-s,new_fills=[X.asdict(f) for f in r.account.fills[old:]],bridge=r.account.bridge(at),memo_hits=r._memo_hits,memo_misses=r._memo_misses))
    if day=='2025-07-01':X.save(out/'FIRST_DAY_PREFIX.json',dict(cursor=r.last_completed_event,checkpoint=str(cp),sha256=X.sha(cp),ready_for_parallel_readonly_audit=True))
    print('COMPLETED_EVENT',a.mode,day,phase,'fills',len(r.account.fills)-old,'seconds',round(time.perf_counter()-s,3),flush=True)
  X.save(out/'COMPLETED.json',dict(actual_at=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-t,cursor=r.last_completed_event,checkpoint=X.read(prog),no_August=True))
 except BaseException as err:
  X.save(out/'ERROR.json',dict(error=repr(err),traceback=traceback.format_exc(),last_cursor=r.last_completed_event if r else None,no_auto_replay=True))
  if r:r.checkpoint(out/'FAILED_WORKING_STATE.pkl')
  raise
if __name__=='__main__':main()
