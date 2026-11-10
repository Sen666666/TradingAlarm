from sa_common import *
from decimal import Decimal
import sys

def admit():
 for name in ['data-validation.json','trace-validation.json']:
  assert read(O/name)['passed'],name
 for name in ['raw-review.json','overlay-review.json']:
  assert read(O/name)['reviewed'],name
 for sector in PREPS:
  assert read(O/f'signal-validation-{sector}.json')['passed']
  assert read(O/sector/'OLD/control-short.json')['passed']
  for version in ['OLD','AMT']:
   z=read(O/sector/version/'technical/short-analysis/accounting.json')
   assert z['passed'] and Decimal(z['max_nav_difference'])==0
 save(O/'admission.json',{'passed':True,'economic_paths':12,'new_candidate_paths':6,'old_control_paths':6,'post_outcome_parameter_changes_allowed':False})
 files=[O/'RULES.txt',O/'admission.json',O/'raw-review.json',O/'overlay-review.json',O/'data-validation.json',O/'trace-validation.json',PRIOR/'execution-rules-v2.json',PRIOR/'input/manifest.json',LOCAL/'recovery.csv',LOCAL/'PROFILE.json',ROOT/'research_rounds/actual-risk-recovery-20261027/recovery.csv',ROOT/'research_rounds/sfw3-rs-baseline-20261028/registry.json',FORM/'registry.json',SFOLD/'code/study.py',LOCAL/'code/study.py',LOCAL/'code/drug_common.py']
 for folder in [O/'code',FORM/'code',ROOT/'research_rounds/actual-risk-recovery-20261027/code',ROOT/'research_rounds/tech-finite-compound-20261026/code',ROOT/'research_rounds/swf-pvr-combination-20261028/code']:
  files.extend(folder.glob('*.py'))
 hashes={str(p):sha(p) for p in files}
 for sector,prep in PREPS.items():
  validation=read(O/f'signal-validation-{sector}.json');hashes.update(validation['input_sha256']);hashes.update(validation['output_sha256'])
  files=[POOLS[sector],prep/'manifest.json',prep/'h1.npz',prep/'recovery.csv',*prep.glob('facts/*.parquet'),*prep.glob('bars/*.parquet'),*prep.glob('actions/*')]
  for p in files:
   if p.is_file():hashes[str(p)]=sha(p)
 for p,h in read(FORM/'registry.json')['source_sha256'].items():assert sha(ROOT/p)==h;hashes[str(ROOT/p)]=h
 for p,h in read(ROOT/'research_rounds/sfw3-rs-baseline-20261028/registry.json')['source_sha256'].items():assert sha(p)==h;hashes[p]=h
 save(O/'freeze.json',{'before_economic':True,'sha256':hashes})
 print('admitted 12 paths; frozen files',len(hashes),flush=True)

def complete():
 for p,h in read(O/'freeze.json')['sha256'].items():assert sha(p)==h,p
 daily=prefix=controls=0
 for sector in PREPS:
  c=read(O/sector/'OLD/control-full.json');assert c['passed'];controls+=c['daily_rows']
  for version in ['OLD','AMT']:
   a=read(O/sector/version/'analysis/accounting.json');assert a['passed'] and Decimal(a['max_nav_difference'])==0;daily+=a['daily_rows']
   a=read(O/sector/version/'prefix-verification.json');assert a['passed'];prefix+=a['daily']
 save(O/'verification.json',{'passed':True,'economic_paths':12,'new_candidate_paths':6,'old_controls':6,'daily_rows':daily,'physical_prefix_daily_rows':prefix,'old_control_daily_rows':controls,'signal_prefixes':910,'economic_reruns':0,'post_outcome_parameter_changes':0,'frozen_hashes_unchanged':True,'platform_changed':False,'technical_failure':'empty-prefix segment dtype validation only; see FAILURES.txt'})
 print('verified',daily,prefix,controls,flush=True)
if __name__=='__main__':admit() if sys.argv[1]=='admit' else complete()
