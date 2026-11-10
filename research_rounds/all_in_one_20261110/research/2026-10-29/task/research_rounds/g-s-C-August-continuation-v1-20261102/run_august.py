"""One append-only four-cell August runner; full Aug1 prefix is reused."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
import argparse,time,traceback,pickle
import august_runtime as A
E=A.E
def state(path):
 s=A.read(Path(path).with_suffix('.provenance.json'));cls=A.R0Runner if s['binding']['cell'].endswith('_R0') else A.BaselineRunner
 return cls.restore(path)
def snap(r,out,label):
 p=out/(label+'.pkl');r.checkpoint(p);A.save(p.with_suffix('.json'),r.observable(r.last_completed_event));return p
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cell',choices=['C10','C20','C10_R0','C20_R0'],required=True);ap.add_argument('--branch',choices=['full','physical'],default='full');ap.add_argument('--until',default='2025-08-29');ap.add_argument('--restore-only',type=Path);a=ap.parse_args()
 root=A.HERE/('runs' if a.branch=='full' else 'physical-runs')/a.cell;root.mkdir(parents=True,exist_ok=True);r=None;t=time.perf_counter()
 try:
  A.guard()
  if a.restore_only:
   r=state(a.restore_only);raw=A.read(a.restore_only.with_suffix('.json'));got=A.read_json_view(r)
   E.require(raw==got,'cross-process full observable differs');A.save(a.restore_only.parent/'RESTORE_GATE.json',dict(passed=True,checkpoint_sha256=A.sha(a.restore_only),economic_sha256=E.digest(A.economic(r)),cursor=r.last_completed_event,financial_events=0));return
  E.require('2025-08-01'<=a.until<='2025-08-29' and (a.branch=='full' or a.until=='2025-08-01'),'wrong cutoff/branch')
  progress=root/'PROGRESS.json'
  if progress.exists():
   rec=A.read(progress);E.require(A.sha(rec['checkpoint'])==rec['sha256'],'progress changed');r=state(rec['checkpoint'])
  else:
   r=A.import_account(a.cell,a.branch,root/'import');p=root/'import/IMPORT.pkl';A.save(progress,dict(checkpoint=str(p),sha256=A.sha(p),cursor=r.last_completed_event,phase='IMPORT'))
  A.save(root/'STARTED.json',dict(at=datetime.now(timezone.utc).isoformat(),cursor=r.last_completed_event,until=a.until,source=r.source_binding()))
  for day in r.inputs.days:
   if day<'2025-08-01' or day>a.until:continue
   for phase in ((['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']):
    at=E.iso(day+('T00:00:00+08:00' if phase=='ACTION' else 'T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    if r.last_completed_event>=at:continue
    before=snap(r,root,'BEFORE_EVENT');et=time.perf_counter();nf=len(r.account.fills)
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','optional stage incomplete; no auto-replay')
    p=snap(r,root,day+'-'+phase);A.save(progress,dict(checkpoint=str(p),sha256=A.sha(p),cursor=r.last_completed_event,phase=phase))
    record=dict(day=day,phase=phase,seconds=time.perf_counter()-et,new_fills=[asdict(f) for f in r.account.fills[nf:]],bridge=r.account.bridge(at),memo_hits=r._memo_hits,memo_misses=r._memo_misses,checkpoint_sha256=A.sha(p))
    A.save(root/(day+'-'+phase+'-FLOW.json'),record)
    print('COMPLETED_EVENT',a.cell,a.branch,day,phase,'fills',len(r.account.fills)-nf,'seconds',round(record['seconds'],3),'NAV',record['bridge']['nav'],flush=True)
  A.save(root/('COMPLETED.json' if a.until=='2025-08-29' else 'PREFIX_COMPLETED.json'),dict(at=datetime.now(timezone.utc).isoformat(),cutoff=a.until,cursor=r.last_completed_event,seconds=time.perf_counter()-t,checkpoint=A.read(progress),no_September=True))
 except BaseException as ex:
  A.save(root/'ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),cursor=r.last_completed_event if r else None,no_auto_replay=True))
  if r:r.checkpoint(root/'FAILED_WORKING_STATE.pkl')
  raise
if __name__=='__main__':main()
