"""Exactly two saved-state target projections; no finance/event progression."""
from selector import *
import time,traceback
def read(p):return json.loads(Path(p).read_text())
def main():
 assert sha(O/'CONTRACT_V2.txt')==CONTRACT_SHA and read(O/'SYNTHETIC_RESULTS.json')['passed']
 out=O/'results';out.mkdir(exist_ok=False)
 save(O/'PROJECTION_AUTHORIZATION.json',dict(scope='original Jan6 and Jul3 conditional target projections + synthetic only',parent='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',
   contract_sha256=CONTRACT_SHA,code={p.name:sha(p) for p in sorted(O.glob('*.py'))},input_files={k:sha(O/'inputs'/(k+'.json')) for k in ('2025_26','2022')},financial_events=0))
 for k in ('2025_26','2022'):
  x=read(O/'inputs'/(k+'.json'));s=x['snapshot'];A=x['A_demands'];B=x['B_demands'];path=out/k;path.mkdir();start=time.monotonic();history=[]
  try:
   a=J.solve(s,A);save(path/'A_JF2.json',a)
   def progress(row):
    history.append(row);save(path/'PROGRESS.json',dict(completed=history,seconds=time.monotonic()-start,financial_events=0))
    if len(history)%5==0 or row['q']:print('B_STEP',k,len(history),row['sid'],row['q'],len(row.get('D',{})),round(time.monotonic()-start,2),flush=True)
    if time.monotonic()-start>180:raise RuntimeError('technical static projection time bound; no approximate output')
   b=solve_B(s,B,progress=progress);save(path/'B.json',b)
   proof=dict(common_financial_snapshot_sha256=J.digest(s),same_joint_guard_sha256=sha(J.__file__),A_raw_items=len(A),B_fresh_items=len(B),
     seconds=time.monotonic()-start,A_scope=x['evidence']['A_scope'],B_scope=x['evidence']['B_scope'],financial_events=0)
   save(path/'VERIFICATION.json',proof)
   print('COMPLETE_STATIC',k,'A',a['Q'],'B_new',sum(bool(q) for q in b['Q'].values()),'B_donors',len(b['D']),'checks',b['native_checks'],'seconds',round(proof['seconds'],2),flush=True)
  except BaseException as e:
   save(path/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),completed_candidate_trace=history,seconds=time.monotonic()-start,financial_events=0));raise
if __name__=='__main__':main()
