from pathlib import Path
import hashlib,json,datetime
from checks import check
R=Path(__file__).resolve().parent
paths=[R/x for x in ['PROTOCOL.md','model.py','engine.py','prepare.py','run.py','checks.py','freeze.py','inputs.json','raw-review.json']]+list((R/'inputs').glob('*.parquet'))+list((R/'raw').glob('*.png'))
paths += [R/'../pv-participation-response-20261020/code'/x for x in ['numeric.py','participation.py']]
payload={'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'account_results_seen':False,'checks':check(),'sha256':{str(p.relative_to(R)) if p.is_relative_to(R) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
p=R/'freeze.json'
with p.open('x') as f:json.dump(payload,f,indent=2)
print('Frozen',len(paths),'files; real accounts not yet run')
