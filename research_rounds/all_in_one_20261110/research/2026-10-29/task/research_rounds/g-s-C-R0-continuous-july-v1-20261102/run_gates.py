"""Approved six technical prefixes. Formal ON/full prefixes continue, not replay."""
from pathlib import Path
import json,hashlib,subprocess,sys,time
import month_r0 as X
R=X.HERE
assert X.read(R/'MEMO_GATE.json')['passed']
initials=X.read(R/'INITIAL_CHECKPOINTS.json');cells=initials['gate_initials']
g=dict(scope='SAME_RUNNER_JULY_TWO_DAY_GATES_ONLY',parent_approved=True,financial_events_authorized=True,start='2025-07-01',end='2025-07-02',cells=list(cells),runtime_sha256=X.sha(R/'month_r0.py'),entry_sha256=X.sha(R/'run_july.py'),risk_core_sha256=X.RISK_SHA,input_identity_sha256=X.sha(R/'INPUT_IDENTITY.json'),root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',root_instruction='16-branch independent PASS; same formal runner two-day warm/registration/OFF identity/physical/restart gates, then continue two formal R0 accounts through Jul31; no ReplayRunner continuation',real_branch_audit='/tmp/R0-real-event-independent-wdet261c/FINAL_AUDIT.json',real_branch_audit_sha256='0527406c72f5758eb4a5693deba44b162da39ca2488edcd80b7769b12e7ec635')
X.save(R/'PREFIX_AUTHORIZATION.json',g)
for until in ['2025-07-01','2025-07-02']:
 for key,rec in cells.items():
  mode,branch,flag=key.split('|');out=R/'runs'/mode if branch=='full' and flag=='on' else R/'gates'/('off' if flag=='off' else 'physical')/mode
  stdout=R/(key.replace('|','-')+'-'+until+'.out');stderr=stdout.with_suffix('.err')
  with stdout.open('w') as so,stderr.open('w') as se:
   subprocess.run([sys.executable,'-B',str(R/'run_july.py'),'--mode',mode,'--authorization',str(R/'PREFIX_AUTHORIZATION.json'),'--out',str(out),'--initial',rec['path'],'--until',until],stdout=so,stderr=se,check=True)
  print('PREFIX_FINISHED',key,until,flush=True)
subprocess.run([sys.executable,'-B',str(R/'compare_prefix.py')],check=True)
