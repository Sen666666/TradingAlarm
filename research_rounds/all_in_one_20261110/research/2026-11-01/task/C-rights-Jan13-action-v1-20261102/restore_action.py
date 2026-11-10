"""Restore registered ACTION output with caller-supplied trusted registry SHA."""
from pathlib import Path
import argparse,json
import action_runtime as A
from state_snapshot import snapshot
def main():
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--registry-sha',required=True);a=p.parse_args()
 r=A.ActionRunner.restore(a.checkpoint,registry_sha=a.registry_sha);before=snapshot(r);evidence=dict(r.action_evidence);at=r.last_completed_event
 result=r.corporate_actions('2022-01-13');A.require(result['status']=='already_applied' and snapshot(r)==before and r.last_completed_event==at and evidence==r.action_evidence,'duplicate ACTION changed state')
 rejected=[]
 old=A.original_entry(r.action_activation['arm'])
 for label,fn in [('OPEN',lambda:r.step('2022-01-13','OPEN')),('CLOSE',lambda:r.step('2022-01-13','CLOSE')),('native_event',lambda:r.event(at)),('other_ACTION_day',lambda:r.execution_guard('2022-01-14')),
  ('wrong_registry_SHA',lambda:A.ActionRunner.restore(a.checkpoint,registry_sha='0'*64)),('arbitrary_snapshot',lambda:A.ActionRunner.restore(A.HERE/'arbitrary.pkl',registry_sha=a.registry_sha)),
  ('Jan12_not_in_ACTION_registry',lambda:A.ActionRunner.restore(old['checkpoint'],registry_sha=a.registry_sha)),('Jan13_not_in_original_Jan12_registry',lambda:A.U.UpgradedRunner.restore(a.checkpoint))]:
  try:fn()
  except ValueError:rejected.append(label)
  else:raise AssertionError('forbidden phase admitted '+label)
 print(json.dumps(dict(passed=True,arm=r.action_activation['arm'],cursor=str(r.last_completed_event),duplicate_ACTION=result['status'],all_post_fields_exact=True,legacy_certificates_recomputed=len(r.authority.certificates),conservation_sha256=A.conservation_sha(r),rejected=rejected,extra_historical_events=0),ensure_ascii=False))
if __name__=='__main__':main()
