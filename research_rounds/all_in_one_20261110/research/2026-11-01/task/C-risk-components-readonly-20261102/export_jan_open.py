"""Strict registered read-only Jan13 OPEN export; never calls an event."""
from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parent
CORE=O.parent/'C-rights-month-resume-v2-20261102'
sys.path.insert(0,str(CORE))
import resume_runtime_v2 as C
arm=sys.argv[1]
index=O.parent/'C-2022-month-native-baseline-20261102/CONTINUATION_CHECKPOINTS.json'
rec=next(x for x in C.read(index)['accounts'] if x['arm']==arm)
p=Path(rec['checkpoint']).with_name('2022-01-13-OPEN.pkl')
r=C.ContinuationRunner.restore(p,registry_sha=rec['trusted_registry_sha256'])
before=C.FP.snapshot(r)
x=r.observable(r.last_completed_event)
assert C.FP.snapshot(r)==before,'read-only export changed full state'
out=O/(arm+'-2022-01-13-OPEN.json')
out.write_text(json.dumps(x,ensure_ascii=False,default=C.E.encode)+'\n')
proof={'checkpoint':str(p),'checkpoint_sha256':C.sha(p),'registry':rec['registry'],
 'trusted_registry_index':str(index),'trusted_registry_index_sha256':C.sha(index),
 'registry_sha256':rec['trusted_registry_sha256'],'last_completed':str(r.last_completed_event),
 'complete_state_unchanged':True,'financial_events':0,'export_sha256':C.sha(out)}
(O/(arm+'-EXPORT-PROOF.json')).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(arm,'READ_ONLY_OPEN_EXPORTED',flush=True)
