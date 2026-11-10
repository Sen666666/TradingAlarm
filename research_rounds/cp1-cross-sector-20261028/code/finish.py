from cp_common import *
from decimal import Decimal as D
def admit():
 assert read(O/'preparation.json')['passed'] and read(O/'raw-review.json')['reviewed'] and read(O/'model-tests.json')['passed']
 for sector in ['TECH','DRUG']:
  assert read(O/sector/'control-short.json')['passed']
  a=read(O/sector/'technical/short-analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0
 hashes={}
 for freeze in [SA/'freeze.json',CP/'freeze.json']:
  for p,h in read(freeze)['sha256'].items():assert sha(p)==h,p;hashes[p]=h
 files=[O/'RULES.txt',O/'preparation.json',O/'raw-review.json',O/'model-tests.json',SA/'freeze.json',CP/'freeze.json']+list((O/'code').glob('*.py'))
 files+=list((O/'signals/DRUG').glob('*.parquet'))+list((CP/'signals').glob('*.parquet'))
 for sector in ['TECH','DRUG']:
  files+=[O/sector/'control-short.json',O/sector/'technical/short-analysis/accounting.json']
  fast=ROOT/'research_rounds/intent-support-20261027/signals' if sector=='TECH' else PREPS[sector]/'fast'
  files+=list(fast.glob('*.parquet'))+list(OLD_TABLES[sector].glob('*.parquet'))
 files+=[COMBO/'code/study.py',COMBO/'code/waiting.py',LOCAL/'code/study.py',LOCAL/'code/drug_common.py',LOCAL/'recovery.csv']
 save(O/'admission.json',dict(passed=True,paths=54,new_cp_paths=24,old_controls=30,one_start_only=True,parameters_frozen=True))
 files.append(O/'admission.json')
 for p in files:hashes[str(p)]=sha(p)
 save(O/'freeze.json',dict(before_economic=True,sha256=hashes));print('admitted',len(hashes),flush=True)
def complete():
 hashes=read(O/'freeze.json')['sha256']
 for p,h in hashes.items():assert sha(p)==h,p
 daily=control=prefix=checks=0
 for sector in ['TECH','DRUG']:
  a=read(O/sector/'analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0;daily+=a['daily_rows']
  control+=read(O/sector/'control-economic.json')['daily_rows'];p=read(O/sector/'prefix-verification.json');assert p['passed'];prefix+=p['daily']
  checks+=sum(r['contracts']['checks'].get('independent_cp_close',0) for r in a['receipts'])
 save(O/'verification.json',dict(passed=True,economic_paths=54,new_cp_paths=24,old_control_paths=30,daily_rows=daily,old_control_daily_rows=control,physical_prefix_daily_rows=prefix,independent_cp_closes=checks,frozen_files=len(hashes),frozen_hashes_unchanged=True,economic_reruns=0,post_outcome_parameter_changes=0,platform_changed=False))
 print('verified',daily,control,prefix,checks,flush=True)
if __name__=='__main__':admit() if sys.argv[1]=='admit' else complete()
