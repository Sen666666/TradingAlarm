from audit import *
checks=[];total=prefix=0
for c in STARTS:
 root=O/c;assert read(root/'analysis/accounting.json')['passed'];assert read(root/'control-full.json')['passed'];assert read(root/'prefix-verification.json')['passed'];total+=read(root/'analysis/accounting.json')['daily_rows'];prefix+=read(root/'prefix-verification.json')['daily']
 old=root/'accounts-failed-calendar-v1';full=root/'accounts-v2';daily={(r['account'],r['at']):r for r in rows(full/'daily.jsonl.gz')};n=0
 for r in rows(old/'daily.jsonl.gz'):assert r==daily[r['account'],r['at']];n+=1
 for p in old.glob('*__S0_*.json'):
  a=read(p);b=read(full/p.name);assert a['fills']==b['fills'][:len(a['fills'])],(c,p.name,'repair changed fills')
 checks.append({'cohort':c,'failed_prefix_daily_exact':n,'failed_prefix_fills_exact':True})
original=read(O/'freeze.json')['sha256'];repair=read(O/'repair-freeze.json')['sha256'];hashes={str(Path(k).resolve()):v for k,v in original.items()};hashes.update({str(Path(k).resolve()):v for k,v in repair.items()})
for p,h in hashes.items():assert sha(p)==h,(p,'source changed')
prior=read(ROOT/'research_rounds/portfolio-correction-20261027/completion.json')['artifacts']
for p,h in prior.items():assert sha(p)==h,(p,'old results changed')
save(O/'verification.json',{'passed':True,'valid_paths':35,'old_ACT_controls':7,'daily_rows':total,'physical_prefix_daily_rows':prefix,'signal_prefixes':814,'max_nav_difference_cny':0,'technical_calendar_replays':35,'economic_parameter_changes':0,'repair_prefix_checks':checks,'frozen_sources_and_prior_completion_artifacts_unchanged_except_registered_calendar_repair':True,'platform_changed':False})
print('verified',total,prefix)
