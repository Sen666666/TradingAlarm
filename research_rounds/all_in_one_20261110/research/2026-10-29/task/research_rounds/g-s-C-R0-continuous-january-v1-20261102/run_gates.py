"""Authorized six two-day technical prefixes, same formal January runner."""
import sys,subprocess
from pathlib import Path
import jan_r0 as X
P=X.HERE;E=X.E

def main():
 a=X.read(P/'INITIAL_CHECKPOINTS.json');g=dict(scope='JAN2022_TWO_DAY_GATES',parent_approved=True,financial_events_authorized=True,start='2022-01-04',end='2022-01-05',technical_ceiling=250000,runtime_sha256=X.sha(P/'jan_r0.py'),entry_sha256=X.sha(P/'run_january.py'),risk_core_sha256=X.RISK_SHA,input_identity_sha256=X.sha(P/'INPUT_IDENTITY.json'),cells=list(a['gate_initials']),root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',authorization='parent: actual off identity/physical prefix/restart then independently continue original Jan1m R0 C10/C20 throughJan28 only; no original account copied')
 X.save(P/'PREFIX_AUTHORIZATION.json',g)
 for mode in ['C10','C_BATCH20']:
  for branch,on in [('full',True),('full',False),('physical',True)]:
   key=mode+'|'+branch+'|'+('on' if on else 'off');out=P/'runs'/mode if branch=='full' and on else P/'gates'/('off' if not on else 'physical')/mode
   for day in ['2022-01-04','2022-01-05']:
    # Distinct subprocess after Jan4 CLOSE: actual cross-process native restore.
    subprocess.run([sys.executable,'-B',str(P/'run_january.py'),'--mode',mode,'--authorization',str(P/'PREFIX_AUTHORIZATION.json'),'--initial',a['gate_initials'][key]['path'],'--out',str(out),'--until',day],check=True)
 print('SIX_PREFIX_RUNS_COMPLETE',flush=True)
if __name__=='__main__':main()
