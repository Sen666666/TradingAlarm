"""Analysis/restore-outlet correction only, never replay recovered optional plan.
Used only if the frozen entry rejects a restore solely for memo-hit metadata.
Financial continuation itself calls the unchanged frozen continue_month().
"""
from pathlib import Path
import sys,json,time,traceback
import budget250 as B
import recover_c20 as C
E=B.E;X=B.X;P=B.HERE;OUT=C.OUT

def main():
 E.require(sys.argv[1:]==['--execute'],'explicit authorized restore correction only')
 p=OUT/'2025-07-22-CLOSE.pkl';pr=X.read(OUT/'PROGRESS.json');E.require(pr['checkpoint']==str(p) and pr['phase']=='CLOSE' and str(pr['cursor']).startswith('2025-07-22 15:10'),'must not replay or duplicate any later account event')
 E.require(X.read(P/'OPTIONAL_RECOVERY_GATE.json')['passed'],'optional recovery not completed')
 error=X.read(P/'RECOVERY_ERROR.json');E.require('CalledProcessError' in error['error'],'only frozen child restore-gate outlet failure may be corrected')
 r=None
 try:
  r=B.Runner.restore(p);actual=json.loads(json.dumps(r.observable(B.AT),default=E.encode));expected=X.read(p.with_suffix('.json'))
  ac=actual.pop('pure_projection_cache');ec=expected.pop('pure_projection_cache');E.require(actual==expected,'restore has differences beyond diagnostic memo counters')
  E.require(ac['misses']==ec['misses'] and ac['hits']==ec['hits']+1,'unexpected restore memo activity')
  before=E.digest(B.economic_view(r));tech=E.digest(r.technical_recovery);E.require(r.retry_technical_optional()['state']=='TECHNICAL_RECOVERY_ALREADY_SUCCEEDED' and before==E.digest(B.economic_view(r)) and tech==E.digest(r.technical_recovery),'restored optional retry changed complete state')
  X.save(P/'RESTORE_GATE.json',dict(passed=True,checkpoint_sha256=X.sha(p),actual_source_engine_equal=True,complete_observable_equal_except_diagnostic_memo_counters=True,memo_before=ec,memo_after=ac,memo_difference_reason='one actual verify_native cache hit during restore, no financial change',idempotence=True,financial_events=0,source_sha256=X.sha(P/'budget250.py'),analysis_outlet_source=str(Path(__file__).resolve()),analysis_outlet_sha256=X.sha(__file__),frozen_entry_failure_preserved=True))
  r.technical_recovery['restore_gate']=dict(path=str(P/'RESTORE_GATE.json'),sha256=X.sha(P/'RESTORE_GATE.json'));r.technical_recovery['restore_outlet_fix']=dict(path=str(Path(__file__).resolve()),sha256=X.sha(__file__),no_optional_replay=True)
  E.require(before==E.digest(B.economic_view(r)),'restore metadata changed finance or strategy');r.checkpoint(P/'READY_TO_CONTINUE.pkl')
  print('RESTORE_CORRECTION_GATE_PASS',flush=True);C.continue_month(r)
 except BaseException as ex:
  X.save(P/'POST_RESTORE_ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),cursor=r.last_completed_event if r else None,no_auto_replay=True))
  if r:r.checkpoint(P/'FAILED_POST_RESTORE_STATE.pkl')
  raise
if __name__=='__main__':main()
