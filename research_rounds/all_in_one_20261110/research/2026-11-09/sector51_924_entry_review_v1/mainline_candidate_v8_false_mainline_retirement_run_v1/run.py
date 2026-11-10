"""Admitted single offline M8 ablation, no live trades."""
from pathlib import Path
import json,sys,importlib.util,datetime,hashlib
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;C=O.parent/'mainline_candidate_v8_false_mainline_retirement'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
E='0e9a3358c126ed0b9b4143c8dae44770c05bd9324f56a63bff160a7cd32c049f'
H='5392a375eb7dfd1652f6d11073a004f0df6da8a2003a758e934aee9121be143a'
assert sha(C/'engine.py')==E and sha(C/'CONTRACT.md')==H
ap=read(O/'CONTRACT_APPROVAL.json')
assert ap['approved'] and ap['engine_sha256']==E and ap['contract_sha256']==H and ap['runner_sha256']==sha(__file__)
qa=read(C/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==E and qa['contract_sha256']==H and qa['count']==68
assert not (O/'RUN_STARTED.json').exists()
for p,h in read(C/'DEPENDENCY_SEAL.json')['hashes'].items():assert sha(p)==h,('DEPENDENCY_DRIFT',p)
sp=importlib.util.spec_from_file_location('admitted_m8',C/'engine.py');m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
assert m.self_check()['result']=='PASS'
data=m.Data(end='2024-10-31')
save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=E,contract_sha256=H,runner_sha256=sha(__file__),end='2024-10-31',comparison='Single false-sector/non-mainline expansion retirement; no shared risk pool'))
save(O/'RUN_STARTED.json',dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),end='2024-10-31'))
e=m.run_loop(m.Engine(data),checkpoint=False)
e.export(O/'once_20241031')
status=dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers),retirement_orders=sum(r['reason']==m.REASON for r in e.orders))
save(O/'RUN_STATUS.json',status)
print(json.dumps(status,ensure_ascii=False,default=str))
