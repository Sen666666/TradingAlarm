"""Wait for the fixed matrix, then independent audits and paired diagnosis."""
import subprocess,sys,time
from build_inputs import HERE,read

def wait_file(path):
 while not path.exists():
  p=HERE/'accounts-v2/summary.json'
  if p.exists() and read(p).get('status')=='failed_partial_run':raise RuntimeError('Main failed; preserve partials')
  time.sleep(5)
def run(name):
 with (HERE/'audit'/(name+'.log')).open('x') as f:
  p=subprocess.run([sys.executable,str(HERE/'code'/(name+'.py'))],stdout=f,stderr=f)
 assert p.returncode==0,name
 print({'analysis_finished':name},flush=True)
wait_file(HERE/'accounts-v2/summary.json');assert read(HERE/'accounts-v2/summary.json')['completed_accounts']==12
run('analyze_accounts');run('verify_orders')
for g in ['G0','G1']:wait_file(HERE/('funnel-v2-'+g)/'summary.json')
for name in ['merge_funnel','diagnose_misses','compare']:run(name)
