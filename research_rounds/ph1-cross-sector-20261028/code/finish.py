"""Admission and completion gates; never launches an account."""
from ph_common import *
from decimal import Decimal

def admit():
 assert read(O/'event-validation.json')['passed']
 assert read(O/'raw-review.json')['reviewed']
 assert read(O/'shadow/review.json')['reviewed']
 assert read(O/'shadow/root-review.json')['reviewed']
 assert read(O/'tests.json')['passed']
 assert read(O/'risk-tests.json')['passed']
 for sector in PREPS:
  assert read(O/sector/'A_E0/control-short.json')['passed']
  for variant in VARIANTS:
   z=read(O/sector/variant/'technical/short-analysis/accounting.json')
   assert z['passed'] and Decimal(z['max_nav_difference'])==0
 hashes=dict(read(SA/'freeze.json')['sha256'])
 for p,h in hashes.items():assert sha(p)==h,p
 events=read(O/'event-validation.json')
 event_hashes=dict(events['source_sha256'])
 for r in events['records']:
  event_hashes.update(r['inputs']);event_hashes[r['output']]=r['output_sha256']
 for p,h in event_hashes.items():assert sha(p)==h,p
 hashes.update(event_hashes)
 for name,key in [('tests.json','sources'),('risk-tests.json','source_hashes')]:
  for p,h in read(O/name)[key].items():assert sha(p)==h,p;hashes[p]=h
 # The previous round's sources, data and audits remain frozen. Add the actual
 # fast-event inputs, the exact E0 event tables, and every new executable source.
 files=[O/'RULES.txt',O/'analysis-plan.txt',DESIGN/'DESIGN.txt',DESIGN/'DESIGN_RECEIPT.json',O/'event-validation.json',O/'raw-review.json',O/'tests.json',O/'risk-tests.json',SA/'freeze.json',SA/'completion-sha256.json']
 files.extend(O.glob('code/*.py'))
 files.extend(p for p in (O/'shadow').rglob('*') if p.is_file())
 for sector in PREPS:
  files.extend(FAST[sector]/f'{sid}.parquet' for sid in pool(sector).symbol)
  files.extend((O/'events'/sector).glob('*.parquet'))
  files.append(O/sector/'A_E0/control-short.json')
  files.extend(O/sector/v/'technical/short-analysis/accounting.json' for v in VARIANTS)
 save(O/'admission.json',dict(passed=True,economic_paths=36,old_control_paths=6,new_paths=30,mechanism_revision_allowed=1,revision_path_limit=6,parameters_frozen=True,short_daily_rows=1692,raw_windows=12))
 files.append(O/'admission.json')
 for p in files:hashes[str(p)]=sha(p)
 save(O/'freeze.json',dict(before_economic=True,sha256=hashes))
 print('admitted 36 paths; frozen files',len(hashes),flush=True)

def complete():
 hashes=read(O/'freeze.json')['sha256']
 for p,h in hashes.items():assert sha(p)==h,p
 daily=prefix=controls=0
 for sector in PREPS:
  c=read(O/sector/'A_E0/control-full.json');assert c['passed'];controls+=c['daily_rows']
  for variant in VARIANTS:
   root=O/sector/variant
   a=read(root/'analysis/accounting.json');assert a['passed'] and Decimal(a['max_nav_difference'])==0;daily+=a['daily_rows']
   p=read(root/'prefix-verification.json');assert p['passed'];prefix+=p['daily']
 assert read(O/'analysis-ph1/verification.json')['passed']
 save(O/'verification.json',dict(passed=True,economic_paths=36,new_paths=30,old_control_paths=6,daily_rows=daily,physical_prefix_daily_rows=prefix,old_control_daily_rows=controls,signal_prefixes=910,economic_reruns=0,post_outcome_parameter_changes=0,frozen_files=len(hashes),frozen_hashes_unchanged=True,platform_changed=False))
 print('verified',daily,prefix,controls,flush=True)

if __name__=='__main__':admit() if sys.argv[1]=='admit' else complete()
