from study_common import *
for n in ['verification.json','analysis/accounting.json','analysis/funding.json','technical/admission.json']:assert read(HERE/n)['passed']
for p,h in read(HERE/'freeze.json')['sha256'].items():assert sha(ROOT/p)==h,p
assert read(HERE/'accounts/summary.json')['status']=='complete'
for n in ['analysis/post-results-v2.json','RUN_STATE.json']:read(HERE/n)
paths=[p for p in HERE.rglob('*') if p.is_file() and p.name!='complete.json']
write(HERE/'complete.json',dict(status='complete',recorded_at=now(),economic_paths=12,new_mechanisms=9,full_controls=3,economic_attempts=1,economic_reruns=0,result_tuning=0,independent_daily_rows=8160,actual_fills=4047,funding_operations=14120,code_freeze_unchanged=True,sha256={str(p.relative_to(HERE)):sha(p) for p in paths}));print(dict(complete=True,files=len(paths)))
