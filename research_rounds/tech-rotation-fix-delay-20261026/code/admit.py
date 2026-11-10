from study_common import *
CONFIG=import_path('execution_fix_runner',HERE/'code/run_study.py').CONFIG
from datetime import date
CONTROLS=['I__S0_base','I__S0_delay1','AMT15__S0_base']
def at(r):return r.get('at') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at')
def identity(folder,cut):
 counts={}
 for k in ['daily','decisions']:
  a=[x for x in rows(folder/(k+'.jsonl.gz')) if x['account'] in CONTROLS];b=[x for x in rows(BASE/'accounts-v2'/(k+'.jsonl.gz')) if x['account'] in CONTROLS and x['at'][:10]<=cut];assert a==b,k;counts[k]=len(a)
 for k in ['fills','audit_log']:
  n=0
  for aid in CONTROLS:
   x=read(folder/(aid+'.json'))[k];y=[r for r in read(BASE/'accounts-v2'/(aid+'.json'))[k] if at(r)[:10]<=cut];assert x==y,(aid,k);n+=len(x)
  counts[k]=n
 return counts
if __name__=='__main__':
 assert read(HERE/'technical/synthetic.json')['passed'];assert read(HERE/'technical/short-analysis/accounting.json')['passed'];assert read(HERE/'technical/short-analysis/funding.json')['passed']
 checks=identity(HERE/'technical/short-v2','2024-03-29');write(HERE/'technical/admission.json',dict(passed=True,recorded_at=now(),control_identity=checks,unique_paths=len(CONFIG),original_signal_and_input_reused=True));print(checks)
