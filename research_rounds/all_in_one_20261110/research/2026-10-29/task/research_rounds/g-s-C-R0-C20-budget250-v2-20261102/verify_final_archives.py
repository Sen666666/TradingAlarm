"""Actual final restore and mixed immutable old/new checkpoint provenance."""
from pathlib import Path
import pickle,json
import budget250 as B
X=B.X;E=B.E;P=B.HERE;OLD=B.OLD

def raw_load(p):
 side=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==side['checkpoint_sha256'],'checkpoint bytes changed');r=pickle.loads(p.read_bytes());r.account.owner=r;E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'actual source/class mismatch');r.assert_observers();return r,side

def main():
 B.guard();pr=X.read(P/'runs/C_BATCH20/PROGRESS.json');cp=Path(pr['checkpoint']);r,newside=raw_load(cp);E.require(type(r) is B.Runner and str(r.last_completed_event).startswith('2025-07-31 15:10'),'not completed new actual account')
 E.require(json.loads(json.dumps(r.observable(r.last_completed_event),default=E.encode))==X.read(cp.with_suffix('.json')),'final complete observable differs')
 before,oldside=raw_load(OLD/'runs/C_BATCH20/2025-07-22-OPEN.pkl');E.require(type(before) is X.Runner,'wrong original financial class')
 failed,fail_side=raw_load(OLD/'runs/C_BATCH20/FAILED_WORKING_STATE.pkl');E.require(r.legacy_certificates==failed.authority.certificates,'imported old certificate registry changed')
 for cid,c in r.legacy_certificates.items():E.require(r.authority.certificates[cid]==c,'old authority rewritten')
 checked=[];seen=set()
 for root,reference in [(OLD/'runs/C_BATCH20',oldside),(P/'runs/C_BATCH20',newside)]:
  for f in sorted(root.glob('20*-*.pkl')):
   E.require(f.name not in seen,'completed financial event duplicated');seen.add(f.name);side=X.read(f.with_suffix('.provenance.json'));b=side['binding']
   E.require(X.sha(f)==side['checkpoint_sha256'] and side['engine_identity']==reference['engine_identity'] and b['source']==reference['binding']['source'] and b['account_class']==reference['binding']['account_class'] and b['input_loader']==reference['binding']['input_loader'],'historical actual source/identity changed')
   g=b['execution_authorization'];E.require(X.sha(g['path'])==g['sha256'],'historical financial grant changed')
   checked.append(dict(file=str(f),sha256=side['checkpoint_sha256'],generation='old100k' if root.parent.parent==OLD else 'new250k',source_actual=True))
 for k,v in r.source_binding().items():
  if Path(k).is_file():E.require(X.sha(k)==v,'frozen source changed '+k)
 for k,v in X.read(B.AUTH)['immutable_original_artifacts'].items():E.require(X.sha(k)==v,'original failure/input/pure proof changed')
 o=r.technical_recovery['restore_outlet_fix'];E.require(X.sha(o['path'])==o['sha256'] and B.R.approved_payload is B.approved_payload,'actual restore/provenance accessor source changed')
 E.require(len(checked)==69 and len(r.events)==69 and len(r.authority.certificates)==23,'missing or duplicate original financial events/decision batches')
 X.save(P/'analysis/ARCHIVE_AND_FINAL_RESTORE.json',dict(passed=True,event_checkpoints=len(checked),event_history=len(r.events),decision_certificates=len(r.authority.certificates),legacy_certificates=len(r.legacy_certificates),new_certificates=len(r.authority.certificates)-len(r.legacy_certificates),final_complete_observable_equal=True,old_full_registry_and_failure_artifacts_unchanged=True,all_original_and_R0_observers=True,rows=checked,financial_events=0))
 print('ARCHIVE_AND_FINAL_PASS',len(checked))
if __name__=='__main__':main()
