"""Read audited saved logs, no restore/step/event/clock/account method call."""
from pathlib import Path
import sys,pickle,json,hashlib
O=Path(__file__).resolve().parent;P=O.parent
CORE=P/'C-rights-month-resume-v2-20261102';BASE=P/'C-2022-month-native-baseline-20261102'
sys.path.insert(0,str(CORE));import resume_runtime_v2 as C
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
idx=BASE/'CONTINUATION_CHECKPOINTS.json';rec=next(z for z in C.read(idx)['accounts'] if z['arm']=='2022-C10')
C.guard();assert sha(rec['registry'])==rec['trusted_registry_sha256']
bank=C.read(rec['registry']);reg=next(z for z in bank['checkpoints'] if z['checkpoint']==rec['checkpoint']);assert reg['sha256']==rec['checkpoint_sha256']
raw=Path(rec['checkpoint']).read_bytes();assert hashlib.sha256(raw).hexdigest()==reg['sha256']
assert sha(Path(rec['checkpoint']).with_suffix('.provenance.json'))==reg['provenance_sha256']
r=pickle.loads(raw);expected=C.read(reg['fields']);assert sha(reg['fields'])==reg['fields_sha256'] and C.FP.snapshot(r)==expected
out=dict(mapping=r.mapping,canonical_registry=r.account.canonical_registry,results=r.results,events=r.events)
(O/'JAN_C10_SAVED_LOGS.json').write_text(json.dumps(out,default=C.E.encode,ensure_ascii=False)+'\n')
assert C.FP.snapshot(r)==expected
proof=dict(passed=True,financial_events=0,account_construction=0,restore_calls=0,current_fields_before_after_exact=True,read_paths={str(p):sha(p) for p in [idx,Path(rec['registry']),Path(rec['checkpoint']),Path(reg['fields']),Path(__file__)]},output_sha256=sha(O/'JAN_C10_SAVED_LOGS.json'))
(O/'JAN_EXTRACTION_CHECKS.json').write_text(json.dumps(proof,indent=2)+'\n')
print('JAN_SAVED_LOG_ONLY_PASS',len(r.mapping),flush=True)
