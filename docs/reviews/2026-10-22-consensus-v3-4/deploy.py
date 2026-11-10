from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime

STAGE = Path(__file__).resolve().parent
ROOT = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
WORK = Path('/Users/bytedance/Documents/ChatGPT/money')
manifest = json.loads((STAGE/'manifest.json').read_text())
destination = ROOT/'docs/reviews/2026-10-22-consensus-v3-4'
assert not destination.exists(), 'delivery already exists'
for name, h in manifest['files'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == h['before'], ('source changed', name)
    assert hashlib.sha256((STAGE/'staged'/name).read_bytes()).hexdigest() == h['after'], ('staged changed', name)
destination.mkdir(parents=True)
shutil.copy2(STAGE/'manifest.json', destination/'manifest.json')
shutil.copy2(STAGE/'changes.diff', destination/'changes.diff')
shutil.copytree(STAGE/'prior', destination/'prior')
for name, h in manifest['files'].items():
    for target_root in (ROOT, WORK):
        target = target_root/name
        if target_root==WORK and target.exists():
            backup=STAGE/'workspace-prior'/name
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,backup)
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_name(target.name+'.v34-staged')
        assert not temp.exists()
        temp.write_bytes((STAGE/'staged'/name).read_bytes())
        temp.replace(target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==h['after']
review_source=WORK/'docs/reviews/2026-10-22-route-and-objective'
review_target=ROOT/'docs/reviews/2026-10-22-route-and-objective'
review_target.mkdir(exist_ok=False)
for name in ('REVIEW.md','evidence.json'):
    shutil.copy2(review_source/name,review_target/name)
receipt={'delivered_at':datetime.now().astimezone().isoformat(),'formal_root':str(ROOT),'workspace_root':str(WORK),'files':manifest['files'],'verified_formal_and_workspace':True,'historical_results_modified':False,'new_economic_accounts':0}
for base in (STAGE,destination):
    (base/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'updated_files':len(manifest['files']),'verified':True,'receipt':str(destination/'receipt.json')},ensure_ascii=False))
