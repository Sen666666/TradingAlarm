from pathlib import Path
import json,hashlib,datetime,os
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';assert not (R/'results').exists();assert json.loads((R/'preflight.json').read_text())['passed'];assert json.loads((R/'review-before-accounts.json').read_text())['approved_for_fixed_54_accounts']
files=list(R.glob('*.py'))+list(R.glob('*.md'))+[R/'cases.json',R/'inputs.json',R/'preflight.json',R/'prefix-checks.csv',R/'signal-review.csv',R/'review-before-accounts.json']+list((R/'prepared').rglob('*.parquet'))+list((R/'prepared').rglob('*.json'))+list((R/'contexts').rglob('*.parquet'))+list((R/'mechanism').glob('*'))+list((R/'review').glob('*.png'))
files += list((R.parent/'market-regimes-exit-20261024/inputs').glob('*.parquet'))+list((R.parent/'pv-participation-response-20261020/code').glob('*.py'))+list((R.parent/'fixed-scenarios-v1').glob('*'))
files += [P/'model.py',P/'legacy.py',P/'engine.py',P/'freeze.json',P/'results/v0/summary.csv',P/'cases.json',P/'results/v0/audit.json']
for policy in ['E0','R','E2','HOLD']:
 for f in (P/'results/v0/accounts').glob(f'*__{policy}__*'):files+=list(f.glob('*'))
for case in json.loads((R/'cases.json').read_text()):files+=[P/'prepared'/case['id']/'R.parquet',P/'prepared'/case['id']/'initial.json']
manifest={os.path.relpath(p,R):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()};assert hashlib.sha256((R/'engine.py').read_bytes()).hexdigest()==hashlib.sha256((P/'engine.py').read_bytes()).hexdigest()
(R/'freeze.json').write_text(json.dumps(dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidate='R1-IR-20261024',new_engine_account_budget=54,control_accounts_reused=216,reference_paths=54,policy_changes_allowed=0,sha256=manifest),ensure_ascii=False,indent=2));print('FROZEN',len(manifest),flush=True)
