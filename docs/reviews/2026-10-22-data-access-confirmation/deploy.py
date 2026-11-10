from pathlib import Path
import hashlib,json,shutil
w=Path('/Users/bytedance/Documents/ChatGPT/money')
f=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
d=Path(__file__).resolve().parent
m=json.loads((d/'manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (d/'receipt.json').exists()
for x in m['files']:
 assert sha(w/x['relative'])==sha(f/x['relative'])==x['before']
 assert sha(d/'staged'/x['relative'])==x['after']
for x in m['files']:
 rel=x['relative'];backup=f/d.relative_to(w)/'prior'/rel
 backup.parent.mkdir(parents=True,exist_ok=True);assert not backup.exists()
 shutil.copy2(f/rel,backup)
 shutil.copy2(d/'staged'/rel,f/rel);shutil.copy2(d/'staged'/rel,w/rel)
 assert sha(f/rel)==sha(w/rel)==x['after']
receipt={'verified_files':len(m['files']),'user_confirmation':m['user_confirmation'],'accounts_run':0,'network_requests':0}
(d/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
for name in ['manifest.json','receipt.json','deploy.py']:
 target=f/d.relative_to(w)/name;assert not target.exists();shutil.copy2(d/name,target)
print(json.dumps(receipt,ensure_ascii=False))
