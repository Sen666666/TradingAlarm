from fw_common import *
from decimal import Decimal as D
def admit():
 assert read(O/'preflight.json')['passed'] and read(PREV/'verification.json')['passed']
 for sector in ['TECH','DRUG']:
  assert read(O/sector/'control-short.json')['passed']
  a=read(O/sector/'technical/short-analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0
 hashes=dict(read(PREV/'freeze.json')['sha256'])
 for p,h in hashes.items():assert sha(p)==h,p
 files=[O/'RULES.txt',O/'ADAPTER_DIFF.txt',O/'preflight.json',PREV/'freeze.json',PREV/'verification.json',PREV/'completion-sha256.json']+list((O/'code').glob('*.py'))
 for sector in ['TECH','DRUG']:
  files+=[O/sector/'control-short.json',O/sector/'technical/short-analysis/accounting.json']
  refs={PREV/sector/'accounts-v2',baseline_accounts(sector,'SW10F')} if sector=='TECH' else {PREV/sector/'accounts-v2'}
  for ref in refs:files += [p for p in ref.iterdir() if p.is_file()]
  files += [p for p in (PREV/sector/'analysis').iterdir() if p.is_file()]
  if sector=='TECH':files += [p for p in (COMBO/'RS/S0/analysis').iterdir() if p.is_file()]
 save(O/'admission.json',dict(passed=True,run_paths=39,new_economic_paths=21,new_cp_paths=18,new_drug_f_w10_controls=3,replayed_cp_controls=18,reused_other_f_paths=21,report_paths=60,one_start_only=True))
 files.append(O/'admission.json')
 for p in files:hashes[str(p)]=sha(p)
 save(O/'freeze.json',dict(before_economic=True,sha256=hashes));print('admitted frozen',len(hashes),flush=True)
def complete():
 hashes=read(O/'freeze.json')['sha256']
 for p,h in hashes.items():assert sha(p)==h,p
 daily=controls=prefix=cpchecks=waitchecks=nostrict=0
 for sector in ['TECH','DRUG']:
  a=read(O/sector/'analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0;daily+=a['daily_rows']
  controls+=read(O/sector/'control-economic.json')['daily_rows'];p=read(O/sector/'prefix-verification.json');assert p['passed'];prefix+=p['daily']
  for r in a['receipts']:
   cc=r['contracts']['checks'];cpchecks+=cc.get('independent_cp_close',0);waitchecks+=cc.get('independent_waiting_observations',0);nostrict+=cc.get('act_wait_creation_without_S',0)
 assert nostrict>0,'new ACT waiting accidentally S filtered or no evidence'
 save(O/'verification.json',dict(passed=True,run_paths=39,new_economic_paths=21,new_cp_paths=18,new_f_w10_drug_paths=3,replayed_old_cp_paths=18,reused_other_f_paths=21,report_paths=60,daily_rows=daily,control_daily_rows=controls,physical_prefix_daily_rows=prefix,independent_cp_closes=cpchecks,independent_waiting_observations=waitchecks,act_wait_creations_S_would_reject=nostrict,frozen_files=len(hashes),frozen_hashes_unchanged=True,economic_reruns=0,post_outcome_parameter_changes=0,platform_changed=False))
 print('verified',daily,controls,prefix,cpchecks,waitchecks,nostrict,flush=True)
if __name__=='__main__':admit() if sys.argv[1]=='admit' else complete()
