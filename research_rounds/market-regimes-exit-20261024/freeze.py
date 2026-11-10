from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parent
paths=[R/x for x in ['PROTOCOL.md','cases.json','inputs.json','model.py','engine.py','prepare.py','preflight.py','run.py','audit.py','freeze.py','review-before-accounts.json']]
for folder in ['inputs','prepared','review','tail-download']:
 paths.extend(p for p in (R/folder).rglob('*') if p.is_file())
paths.extend(R/'../pv-participation-response-20261020/code'/p for p in ['numeric.py','participation.py'])
payload={'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_case_results_seen':False,'already_viewed_development_history':True,'accounts':240,'parameter_search':False,'sha256':{str(p.relative_to(R)) if p.is_relative_to(R) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
with (R/'freeze.json').open('x') as f:json.dump(payload,f,indent=2)
print('Frozen',len(paths),'files before accounts')
