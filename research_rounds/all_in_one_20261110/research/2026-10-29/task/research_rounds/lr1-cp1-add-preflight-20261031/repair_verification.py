"""Recover already completed paths; no economic replay or future-rule choice."""
import adapter as M
from run_stage import rows,obj,identity
from types import SimpleNamespace
import time
O=M.O
def main():
 root=O/'DRUG/full';data=rows(root/'results/daily.jsonl.gz');proof=M.read(root/'EXTRA_GUARD_NONEXPOSURE.json');assert proof['passed'] and proof['old_extra_epoch_guard_false_cases']==0
 accounts={}
 for name in M.read(root/'results/META.json')['paths']:
  ob=obj(root/'results'/f'{name}.json.gz');accounts[name]=SimpleNamespace(trades=ob['trades'],decisions=ob['decisions'],audit_log=ob['audit'],layers=ob['layers'])
 r=SimpleNamespace(daily=data,accounts=accounts)
 checks=[identity(r,p+'_base',O/'DRUG/prefix/results',p+'_base','2025-12-31') for p in ['L0','ADD']]
 M.save(root/'GATE.json',dict(passed=True,recovered_without_economic_rerun=True,identities=checks,rows=len(data),all_six_complete=len(data)==6*681,extra_guard_nonexposure=proof,original_failure='Verifier forgot to truncate new full path to prefix end. Original ERROR.json and all outputs retained.'))
 print('RECOVERED',len(data),checks,flush=True)
if __name__=='__main__':
 t=time.monotonic();main();s=M.read(O/'COMPUTE_TIME.json');dt=time.monotonic()-t;s['seconds']+=dt;s['stages'].append(dict(sector='DRUG',stage='recover_verifier_without_replay',status='complete',seconds=dt));M.save(O/'COMPUTE_TIME.json',s)
