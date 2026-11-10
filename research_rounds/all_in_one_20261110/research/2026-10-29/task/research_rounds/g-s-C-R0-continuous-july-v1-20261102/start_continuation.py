"""Only after the explicit parent-allowed same-runner gates. No new account."""
from pathlib import Path
import sys,json,subprocess
import month_r0 as X
R=X.HERE;E=X.E
gate=X.read(R/'TWO_DAY_GATE.json');E.require(gate['passed'] and gate['runtime_sha256']==X.sha(R/'month_r0.py') and gate['entry_sha256']==X.sha(R/'run_july.py'),'gates/source required')
a=X.read(R/'INITIAL_CHECKPOINTS.json')
g=dict(scope='TWO_NEW1M_R0_JULY_PATHS_ONLY',parent_approved=True,independent_audit_PASS=True,financial_events_authorized=True,modes=['C10','C_BATCH20'],start='2025-07-01',end='2025-07-31',runtime_sha256=X.sha(R/'month_r0.py'),entry_sha256=X.sha(R/'run_july.py'),risk_core_sha256=X.RISK_SHA,input_identity_sha256=X.sha(R/'INPUT_IDENTITY.json'),initial_checkpoints=a['accounts'],two_day_gate_sha256=X.sha(R/'TWO_DAY_GATE.json'),root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',independent_real_event_audit=dict(path='/tmp/R0-real-event-independent-wdet261c/FINAL_AUDIT.json',sha256='0527406c72f5758eb4a5693deba44b162da39ca2488edcd80b7769b12e7ec635'),parent_scope='Original1m C10+R0 and C20+R0 Jul1-Jul31; after same-runner two-day gates continue existing formal checkpoints, no daily further approval, no ReplayRunner/2022/new parameter')
mode=sys.argv[1];E.require(mode in g['modes'],'only original modes')
p=R/'runs'/mode/'PROGRESS.json';z=X.read(p);E.require(str(z['cursor']).startswith('2025-07-02 15:10'),'formal two-day prefix must be reused, not rerun')
auth=R/'CONTINUATION_AUTHORIZATION.json'
if auth.exists():E.require(X.read(auth)==g,'existing monthly authorization differs')
else:X.save(auth,g)
with (R/(mode+'-MONTH.out')).open('w') as so,(R/(mode+'-MONTH.err')).open('w') as se:
 subprocess.run([sys.executable,'-B',str(R/'run_july.py'),'--mode',mode,'--authorization',str(R/'CONTINUATION_AUTHORIZATION.json')],stdout=so,stderr=se,check=True)
print('MONTH_COMPLETE',mode,flush=True)
