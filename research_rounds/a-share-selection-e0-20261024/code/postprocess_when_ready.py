"""Finish authorized accounting/attribution as soon as the13 accounts close."""
import time,subprocess,sys
from build_inputs import HERE,read,write,ref,now

def main():
 write(HERE/'audit/postprocess-protocol.json',dict(recorded_at=now(),new_accounts=0,ordered_read_only_steps=['analyze_accounts.py','merge_funnel.py','diagnose_misses.py'],
  sources=[ref(HERE/'code'/x) for x in ['analyze_accounts.py','merge_funnel.py','diagnose_misses.py','test_analysis_replay.py']],
  evaluator_test=ref(HERE/'audit/evaluator-test-04.log'),report_conclusion_requires_manual_evidence_review=True))
 while True:
  p=HERE/'accounts-v2/summary.json'
  if p.exists():
   s=read(p)
   if s.get('status')=='failed_partial_run':raise RuntimeError('Main run incomplete; no economic conclusion')
   if s.get('completed_accounts')==13:break
  time.sleep(5)
 for script in ['analyze_accounts.py','merge_funnel.py','diagnose_misses.py']:
  if script=='merge_funnel.py':
   while not all((HERE/('funnel-v2-'+g)/'summary.json').exists() for g in ['G0','G1']):time.sleep(2)
  with (HERE/'audit'/('post-'+script+'.log')).open('x') as log:
   p=subprocess.run([sys.executable,str(HERE/'code'/script)],stdout=log,stderr=log)
  if p.returncode:raise RuntimeError('Read-only postprocessing failed: '+script)
  print({'finished':script},flush=True)
 write(HERE/'audit/postprocess-complete.json',dict(recorded_at=now(),status='audited_and_attributed_pending_manual_conclusion',economic_accounts_added=0))

if __name__=='__main__':main()
