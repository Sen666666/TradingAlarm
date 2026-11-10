"""Install only the three user-authorized, staged research documentation files."""
from pathlib import Path
import json,hashlib,os
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((O/'repo-doc-patch/INSTALL_MANIFEST.json').read_text())
allowed={f'/Users/bytedance/Documents/ChatGPT/money/docs/{s}' for s in ['RESEARCH_CONSENSUS.md','NEXT_RESEARCH_TASKS.md','RESEARCH_REVIEW_CHECKLIST.md']}
assert set(m)==allowed
for name,r in m.items():
 p=Path(name);q=Path(r['staged']);assert sha(q)==r['after']
 assert (sha(p) if p.exists() else None)==r['expected_before'],('destination changed; do not overwrite',name)
for name,r in m.items():
 p=Path(name);q=Path(r['staged']);t=p.with_name(p.name+'.review-install.tmp')
 with t.open('wb') as f:f.write(q.read_bytes());f.flush();os.fsync(f.fileno())
 t.replace(p);assert sha(p)==r['after']
(O/'REPO_DOC_INSTALL_RESULT.json').write_text(json.dumps(dict(installed=True,files=m,scope='research documentation only; no source, data, accounts or runtime changes'),ensure_ascii=False,indent=2)+'\n')
print('INSTALLED 3 research documentation files; all before/after hashes exact')
