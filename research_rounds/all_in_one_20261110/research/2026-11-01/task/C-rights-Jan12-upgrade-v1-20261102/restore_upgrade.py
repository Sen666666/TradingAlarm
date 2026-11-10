"""Cross-process restore/check only; no event or checkpoint upgrade is executed."""
from pathlib import Path
import json,sys
import upgrade_runtime as U
p=Path(sys.argv[1]);r=U.UpgradedRunner.restore(p);before=U.prefix_hashes(r);record=dict(r.rights_upgrade_record)
r,status=U.upgrade_runner(r,r.rights_upgrade_record['arm'])
assert status=='already_upgraded' and U.prefix_hashes(r)==before and record==r.rights_upgrade_record
print(json.dumps(dict(restored=True,arm=record['arm'],cursor=str(r.last_completed_event),prefix=before,duplicate_upgrade=status,certificates=len(r.authority.certificates),historical_events=0),ensure_ascii=False))
