"""Freeze explicit repair/retry; reuse immutable prefix and trusted IMPORT/ACTION."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;B=O.parent/'C-rights-month-resume-20261102';P=O.parent/'C-rights-Jan13-action-v3-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 assert not(O/'SOURCE_FREEZE.json').exists(),'already frozen'
 x=read(B/'IDENTITY.json');assert sha(x['parent_registry'])=='8bed1bd324fcee86ac989aa7287c741e63fd15a0bb61ee0adaeb42e878b090f6'
 x['version']='C_MONTH_RIGHTS_RESUME_2';x['previous_failed_source_sha256']=sha(B/'SOURCE_FREEZE.json');x['previous_failed_manifest_sha256']=sha(B/'BLOCKED_SHA256.json');x['import_sources']={}
 for arm,parent in x['arms'].items():
  for branch in ['full','physical']:
   bank=B/'runs'/arm/branch/'REGISTRY.json'
   if bank.exists():
    rows=read(bank)['checkpoints'];assert len(rows)==1 and rows[0]['label']=='IMPORT';r=rows[0]
    x['import_sources'][arm+'|'+branch]=dict(kind='IMPORT',checkpoint=r['checkpoint'],sha256=r['sha256'],registry_sha256=sha(bank))
   else:x['import_sources'][arm+'|'+branch]=dict(kind='ACTION',checkpoint=parent['checkpoint'],sha256=parent['sha256'])
 (O/'INPUT_FREEZE.json').write_bytes((B/'INPUT_FREEZE.json').read_bytes());save(O/'IDENTITY.json',x)
 grants={}
 for arm,parent in x['arms'].items():
  for branch,inp in x['inputs'].items():
   p=O/'grants'/(arm+'-'+branch+'.json');g=dict(parent_approved=True,scope='C_EXISTING_ACCOUNT_MONTH_CONTINUATION',runtime_identity_sha256=sha(O/'IDENTITY.json'),arm=arm,mode=arm[5:],window='2022',branch=branch,base_ACTION_checkpoint_sha256=parent['sha256'],input_manifest_sha256=inp['sha256'],days=['2022-01-13'],phases=['OPEN','CLOSE'],no_account_reset=True,technical_control=branch=='physical',approval_source='parent explicit repair of clock-read guard and bounded retry after proven atomic rollback; Jan13 two2022 only')
   save(p,g);grants[arm+'|'+branch]=dict(path=str(p),sha256=sha(p))
 save(O/'INITIAL_GRANTS.json',grants)
 files=list(O.glob('*.py'))+[O/'CONTRACT.txt',O/'INPUT_FREEZE.json',O/'IDENTITY.json',O/'INITIAL_GRANTS.json',B/'continuation_runtime.py',B/'SOURCE_FREEZE.json',B/'IDENTITY.json',B/'BLOCKED_SHA256.json',P/'SOURCE_FREEZE.json',P/'OUTPUT_REGISTRY.json',Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-C-nextsession-native-20261102/compare_branches.py')]
 files += [Path(v['path']) for v in grants.values()]
 files += [B/'runs'/arm/branch/'REGISTRY.json' for arm in ['2022-C10'] for branch in ['full','physical']]
 save(O/'SOURCE_FREEZE.json',dict(identity_sha256=sha(O/'IDENTITY.json'),sources={str(p):sha(p) for p in files}));print('FROZEN_REPAIR',sha(O/'IDENTITY.json'),flush=True)
if __name__=='__main__':main()
