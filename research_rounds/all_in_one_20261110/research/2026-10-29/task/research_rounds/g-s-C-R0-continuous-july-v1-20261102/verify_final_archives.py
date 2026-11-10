"""Hashes/actual final restore only. Reuse unchanged per-registration plan checks."""
from pathlib import Path
import json,pickle,time
import month_r0 as X
E=X.E;P=X.HERE

def main():
 pr=X.read(P/'runs/C10/PROGRESS.json');cp=Path(pr['checkpoint']);s=X.read(cp.with_suffix('.provenance.json'));E.require(X.sha(cp)==s['checkpoint_sha256'],'terminal bytes');r=pickle.loads(cp.read_bytes());r.account.owner=r
 E.require(r.binding()==s['binding'] and E.IO.runner_identity(r)==s['engine_identity'],'actual final identity');r.assert_observers()
 actual=json.loads(json.dumps(r.observable(r.last_completed_event),default=E.encode));E.require(actual==X.read(cp.with_suffix('.json')),'final complete observable differs')
 checked=[]
 for f in sorted((P/'runs/C10').glob('20*-*.pkl')):
  side=X.read(f.with_suffix('.provenance.json'));b=side['binding'];E.require(X.sha(f)==side['checkpoint_sha256'],'saved event checkpoint bytes changed')
  E.require(b['source']==r.source_binding() and b['engine']==s['binding']['engine'] and side['engine_identity']==s['engine_identity'] and b['account_class']==s['binding']['account_class'] and b['input_loader']==s['binding']['input_loader'],'saved event actual source/identity changed')
  grant=b['execution_authorization'];E.require(grant and X.sha(grant['path'])==grant['sha256'],'historical grant changed');g=X.read(grant['path']);E.require(g['parent_approved'] and g['financial_events_authorized'],'grant authorization missing')
  E.require(b['mode']=='C10' and b['risk_enabled'] and b['branch']=='full','unapproved actual account')
  checked.append(dict(path=str(f),sha256=side['checkpoint_sha256'],actual_engine_same=True,historical_execution_grant=grant))
 # Verify all old economic input/source bindings stayed immutable; full/physical
 # input hashing already enforced at preparation/read and actual runner guards.
 src=r.source_binding();files=[(k,v) for k,v in src.items() if Path(k).is_file()]
 E.require(all(X.sha(k)==v for k,v in files),'frozen source changed')
 X.save(P/'analysis/ARCHIVE_AND_FINAL_RESTORE.json',dict(passed=True,event_checkpoints=len(checked),rows=checked,actual_final_restore_complete_observable_equal=True,all_original_C_and_R0_observers=True,immutable_source_files=len(files),all_registration_solutions_recomputed_when_registered=True,unchanged_previous_solutions_not_repeated_here=True,financial_events=0,checkpoint_cursor=r.last_completed_event))
 print('ARCHIVES_FINAL_RESTORE_PASS',len(checked),flush=True)
if __name__=='__main__':main()
