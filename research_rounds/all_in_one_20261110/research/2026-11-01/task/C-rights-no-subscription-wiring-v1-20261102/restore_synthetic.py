"""Only accepts this package's generated fixture checkpoint directory."""
from pathlib import Path
import hashlib,json,pickle,sys
from synthetic_runner import SyntheticRightsRunner,HERE
from rights_wiring import conservation_bytes,state_value,canonical
p=Path(sys.argv[1]).resolve()
if p.parent!=(HERE/'synthetic-results').resolve():raise ValueError('synthetic checkpoint directory only; history import forbidden')
r=SyntheticRightsRunner.restore(p);before=hashlib.sha256(canonical(state_value(r)).encode()).hexdigest();result=r.corporate_actions('2025-07-03')
assert result['status']=='already_applied' and hashlib.sha256(canonical(state_value(r)).encode()).hexdigest()==before
print(json.dumps(dict(restored=True,mode=r.mode,duplicate=result['status'],financial_state_sha256=hashlib.sha256(conservation_bytes(r)).hexdigest(),synthetic_only=True)))
