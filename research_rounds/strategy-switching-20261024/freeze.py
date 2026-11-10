from pathlib import Path
import hashlib,json,datetime
R=Path(__file__).resolve().parent;assert not (R/'results').exists();assert json.loads((R/'review-before-accounts.json').read_text())['approved_for_finite_accounts'];assert json.loads((R/'preflight.json').read_text())['passed']
paths=list(R.glob('*.py'))+list(R.glob('*.md'))+[R/'cases.json',R/'preflight.json',R/'prefix-checks.csv',R/'signal-review.csv',R/'review-before-accounts.json']+list((R/'prepared').rglob('*'))+list((R/'contexts').rglob('*'))+list((R/'review').glob('*.png'))
paths += list((R.parent/'market-regimes-exit-20261024/inputs').glob('*.parquet'))+list((R.parent/'pv-participation-response-20261020/code').glob('*.py'))+list((R.parent/'fixed-scenarios-v1').glob('*'))
import czsc
paths += [Path(czsc.__file__)]+list(Path(czsc.__file__).parent.glob('*.so'))
import os
manifest={os.path.relpath(p,R):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
(R/'freeze.json').write_text(json.dumps(dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),accounts_authorized=486,policy_changes_allowed=0,sha256=manifest),ensure_ascii=False,indent=2));print('FROZEN',len(manifest))
