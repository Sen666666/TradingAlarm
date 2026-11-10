"""One extra session only, phase-by-phase processes. Never constructs an account."""
from pathlib import Path
import argparse,json,time,traceback,datetime
import c_horizon as C
E=C.E;P=C.P;HERE=C.HERE
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def snapshot(r,out,name):
 p=out/(name+'.pkl');r.checkpoint(p);at=r.last_completed_event
 # An import writes its existing prefix cursor; an ACTION updates it too.
 save(out/(name+'.json'),r.observable(at));return p
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--window',choices=C.DATES,required=True);ap.add_argument('--mode',choices=['C10','C_BATCH20'],required=True);ap.add_argument('--branch',choices=['full','physical'],required=True);ap.add_argument('--phase',choices=['IMPORT','ACTION','OPEN','CLOSE'],required=True);a=ap.parse_args()
 out=HERE/'runs'/(a.window+'-'+a.mode)/a.branch;out.mkdir(parents=True,exist_ok=True);r=None;t=time.perf_counter();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  C.guard();day=C.DATES[a.window];progress=out/'PROGRESS.json'
  if a.phase=='IMPORT':
   E.require(not progress.exists() and not (out/'state').exists(),'existing import; no silent repeated import')
   r=C.import_account(a.window,a.mode,a.branch,out/'state');p=out/'state/IMPORT.pkl';save(progress,dict(phase='IMPORT',checkpoint=str(p),checkpoint_sha256=P.sha(p),cursor=r.last_completed_event))
  else:
   prev=C.read(progress);p=Path(prev['checkpoint']);E.require(P.sha(p)==prev['checkpoint_sha256'],'progress checkpoint changed');r=C.HorizonRunner.restore(p)
   E.require(r.window==a.window and r.mode==a.mode and r.horizon_branch==a.branch,'wrong continuation identity')
   needs_actions=bool(r.inputs.actions(day));required={'ACTION':'IMPORT','OPEN':'ACTION' if needs_actions else 'IMPORT','CLOSE':'OPEN'}
   E.require(prev['phase']==required[a.phase],'completed or out-of-order phase must not replay')
   before=snapshot(r,out,'BEFORE_'+a.phase)
   if a.phase=='ACTION':r.corporate_actions(day)
   else:r.step(day,a.phase)
   if a.phase=='CLOSE':E.require(r.close_stages[r.last_completed_event.isoformat()]['optional_status']=='succeeded','required stage persisted; optional stage incomplete')
   p=snapshot(r,out,day+'-'+a.phase);save(progress,dict(phase=a.phase,checkpoint=str(p),checkpoint_sha256=P.sha(p),cursor=r.last_completed_event))
  save(out/(a.phase+'-TIMING.json'),dict(phase=a.phase,started_at=started,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.perf_counter()-t,cursor=r.last_completed_event,account_reset=False))
  print(json.dumps(dict(window=a.window,mode=a.mode,branch=a.branch,phase=a.phase,cursor=str(r.last_completed_event),seconds=time.perf_counter()-t)))
 except BaseException as exc:
  save(out/(a.phase+'-ERROR.json'),dict(target_day=C.DATES[a.window],phase=a.phase,last_completed=r.last_completed_event if r else None,error=repr(exc),traceback=traceback.format_exc(),no_automatic_rerun=True,started_at=started,failed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
  if r is not None:E.IO.write_pickle(out/(a.phase+'-FAILED_WORKING_STATE.pkl'),r)
  raise
if __name__=='__main__':main()
