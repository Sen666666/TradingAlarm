"""Authorized four next sessions and their isolated physical controls only."""
import subprocess,sys,json
from pathlib import Path
import c_horizon as C
HERE=C.HERE
def main():
 C.guard();assert C.read(HERE/'PREFLIGHT_GATE.json')['passed'];assert C.read(HERE/'INPUT_GATE.json')['passed']
 done=[]
 for window in ('2025_26','2022'):
  for mode in ('C10','C_BATCH20'):
   for branch in ('full','physical'):
    phases=(['ACTION'] if window=='2025_26' else [])+['OPEN','CLOSE'];out=HERE/'runs'/(window+'-'+mode)/branch
    previous=C.read(out/'PROGRESS.json')['phase']
    # Only explicitly recorded durable phases may be resumed; never redo.
    for phase in phases:
     order=['IMPORT']+phases
     if order.index(previous)>=order.index(phase):continue
     prefix=out/phase
     with prefix.with_suffix('.out').open('w') as so,prefix.with_suffix('.err').open('w') as se:
      result=subprocess.run([sys.executable,'-B',str(HERE/'day_driver.py'),'--window',window,'--mode',mode,'--branch',branch,'--phase',phase],stdout=so,stderr=se)
     if result.returncode:raise RuntimeError('atomic stop; inspect '+str(prefix)+'-ERROR.json / .err; no completed phase rerun')
     previous=phase;print('COMPLETED_PHASE',window,mode,branch,phase,flush=True)
   result=subprocess.run([sys.executable,'-B',str(HERE/'compare_branches.py'),window,mode])
   if result.returncode:raise RuntimeError('comparison failed; finance already completed remains preserved')
   done.append(window+'-'+mode)
 C.E.IO.write_json(HERE/'COMPLETED.json',dict(formal_paths=done,physical_controls=done,only_next_day=True,old_events_replayed=0,next_dates=C.DATES,no_further_date_authorized=True))
if __name__=='__main__':main()
