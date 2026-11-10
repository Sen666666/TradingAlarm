"""Amend only two audited input defects; original numeric tables are reused."""
from loader import *
from prepare import filtered,structure_observations
import shutil,time
OLD=W/'g-s-readonly-historical-loader-20261101'

def main():
 out=O/'input-v1';assert not out.exists();t=time.monotonic()
 assert sha(OLD/'INPUT_PACKAGE_SHA256.json')=='d0b618d9689e1b8f782776ae3b3405875e8c48aa1f01ddd6d614bef5b804d8c4'
 oldindex=read(OLD/'INPUT_PACKAGE_SHA256.json')
 for rel,h in oldindex.items():assert sha(OLD/'input-v2'/rel)==h
 shutil.copytree(OLD/'input-v2',out)
 inventory={r['symbol']:r for r in read(B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')}
 bindings=read(out/'SOURCE_BINDINGS.json');summary={}
 for k in ('2022','2025_26'):
  root=out/k;m=read(root/'MANIFEST.json');meta=read(root/'metadata.json');facts=pd.read_parquet(root/'facts.parquet')
  groups={sid:z.day.tolist() for sid,z in facts.groupby('sid',sort=False)}
  for n,sid in enumerate(m['fixed_ids']):
   p=Path(inventory[sid]['refs']['facts']);assert sha(p)==bindings[str(p)]
   f=filtered(p,m['days'][-1]);obs=groups.get(sid,[])
   meta[sid].pop('structures');meta[sid]['structure_observations']=structure_observations(sid,f,obs)
   if (n+1)%600==0:print('AMEND_METADATA',k,n+1,round(time.monotonic()-t,2),flush=True)
  write(root/'metadata.json',meta);m['files']['metadata']['sha256']=sha(root/'metadata.json')
  seed=read(root/'bootstrap.json');z=pd.read_parquet(root/'f1_observations.parquet');changed=0
  for i,r in z.iterrows():
   correct=seed[r['node_id']]['original_F1_scope'];assert r['policy_scope']==seed[r['node_id']]['policy_scope']
   changed+=int(r['original_F1_scope']!=correct);z.at[i,'original_F1_scope']=correct
  z.to_parquet(root/'f1_observations.parquet',index=False);m['files']['f1_observations']['sha256']=sha(root/'f1_observations.parquet')
  m['schema']=SCHEMA;m['amendment']=dict(base_manifest_sha256=sha(OLD/'input-v2'/k/'MANIFEST.json'),changes=['observation-clock structure metadata','seed-bound original_F1_scope'])
  write(root/'MANIFEST.json',m)
  untouched={name:r['sha256'] for name,r in m['files'].items() if name not in ('metadata','f1_observations')}
  assert untouched=={name:r['sha256'] for name,r in read(OLD/'input-v2'/k/'MANIFEST.json')['files'].items() if name not in ('metadata','f1_observations')}
  summary[k]=dict(identities=1709,scope_rows=len(z),scope_alias_rows_corrected=changed,other_file_hashes_exact=untouched,manifest_sha256=sha(root/'MANIFEST.json'))
 write(out/'BASE_EXPORT_FREEZE.json',read(out/'FREEZE.json'))
 write(out/'FREEZE.json',dict(kind='isolated read-only input amendment',base=str(OLD/'input-v2'),base_package_sha256=sha(OLD/'INPUT_PACKAGE_SHA256.json'),summary=summary,
   unchanged_bootstrap_package_sha256='693bcafee5236c69f37cb063e458ba47e4637ffefe013de787432ed08a34bcc9',accounts=0,financial_events=0,intents=0,seconds=time.monotonic()-t))
 print(canonical(summary),flush=True)
if __name__=='__main__':main()
