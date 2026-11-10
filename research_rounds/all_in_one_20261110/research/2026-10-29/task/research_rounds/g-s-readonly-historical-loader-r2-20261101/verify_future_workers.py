"""Independent-process read of the already built future-derived counterexamples."""
from verify_amendment import *

def main():
 out=O/'validation-future-workers';out.mkdir(exist_ok=False);checks=[]
 for k in ('2022','2025_26'):
  baseline=packet_hashes(ROOT/k/'MANIFEST.json')
  branch=O/'validation-001'/(k+'-future-derived-metadata')
  target=out/(k+'.json')
  subprocess.run([sys.executable,'-B',str(O/'verify_amendment.py'),'worker',str(branch/'MANIFEST.json'),str(target)],check=True)
  actual=read(target)
  assert actual['pid']!=baseline['pid']
  assert actual['events'][2]==baseline['events'][2] # first OPEN; future E0 changed afterward
  assert actual['priority']==baseline['priority'] and actual['bootstrap']==baseline['bootstrap']
  checks.append(dict(window=k,whole_first_OPEN_exact=True,priorities_bootstrap_exact=True,pid=actual['pid']))
 write(out/'VERIFICATION.json',dict(passed=True,checks=checks,accounts_created=0,financial_events=0,intents_created=0))
 print(canonical(read(out/'VERIFICATION.json')))
if __name__=='__main__':main()
