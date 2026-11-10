from pathlib import Path
import hashlib,json,shutil
w=Path('/Users/bytedance/Documents/ChatGPT/money');f=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm');d=Path(__file__).resolve().parent
m=json.loads((d/'manifest.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (d/'receipt.json').exists()
for x in m['files']:assert sha(f/x['relative'])==x['before'] and sha(d/'staged'/x['relative'])==x['after']
for x in m['files']:
 rel=x['relative'];backup=f/d.relative_to(w)/'prior'/rel;backup.parent.mkdir(parents=True,exist_ok=True);assert not backup.exists();shutil.copy2(f/rel,backup)
 old=w/rel
 if old.exists():
  local=d/'workspace-prior'/rel;local.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old,local)
 shutil.copy2(d/'staged'/rel,f/rel);shutil.copy2(d/'staged'/rel,w/rel);assert sha(f/rel)==x['after']
for rel in ['research_rounds/current-pool-20261022/README.md','research_rounds/current-pool-20261022/scope.json']:
 dest=f/rel;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();shutil.copy2(w/rel,dest);assert sha(w/rel)==sha(dest)
(d/'receipt.json').write_text(json.dumps({'verified_entry_updates':len(m['files']),'new_research_entry':True,'account_runs':0},indent=2)+'\n')
for name in ['manifest.json','receipt.json','deploy.py']:
 target=f/d.relative_to(w)/name;assert not target.exists();shutil.copy2(d/name,target)
print('Updated scope in seven current entries; prior documents preserved.')
