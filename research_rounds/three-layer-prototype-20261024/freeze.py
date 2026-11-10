from pathlib import Path
import hashlib,json,datetime
HERE=Path(__file__).resolve().parent
FILES=['model.py','run_study.py','PROTOCOL.md','raw-review.json','cases.json','input-freeze.json','prepare.py','freeze.py']
out=HERE/'freeze.json'
with out.open('x') as f:json.dump(dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in FILES},candidate_count=1,mechanism_revision_budget=0,account_runs=0),f,ensure_ascii=False,indent=2)
print(out)
