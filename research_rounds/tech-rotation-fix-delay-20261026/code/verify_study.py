from study_common import *
admit=import_path('current_fix_admission',HERE/'code/admit.py')
def main():
 controls=admit.identity(HERE/'accounts','2026-10-26');counts={}
 for k in ['daily','decisions']:
  a=[x for x in rows(HERE/'accounts'/(k+'.jsonl.gz')) if x['at'][:10]<='2024-12-31'];b=list(rows(HERE/'technical/prefix'/(k+'.jsonl.gz')));assert a==b,k;counts[k]=len(a)
 for k in ['fills','audit_log']:
  n=0
  for aid in read(HERE/'accounts/summary.json')['accounts']:
   a=[x for x in read(HERE/'accounts'/(aid+'.json'))[k] if admit.at(x)[:10]<='2024-12-31'];b=read(HERE/'technical/prefix'/(aid+'.json'))[k];assert a==b,(aid,k);n+=len(a)
  counts[k]=n
 frozen=read(HERE/'freeze.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in frozen.items())
 old_frozen=read(BASE/'account-freeze-v2.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in old_frozen.items())
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in registry.items())
 write(HERE/'verification.json',dict(passed=True,recorded_at=now(),full_original_controls=controls,physically_truncated_prefix=counts,freeze_files_unchanged=len(frozen),prior_freeze_unchanged=len(old_frozen),E0_R_R1_unchanged=len(registry),economic_attempts=1,economic_reruns=0));print(dict(controls=controls,prefix=counts))
if __name__=='__main__':main()
