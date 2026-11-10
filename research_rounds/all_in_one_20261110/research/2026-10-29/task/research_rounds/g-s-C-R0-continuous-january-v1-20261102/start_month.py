"""Continue ONLY already gated Jan5 formal account, no new initialization."""
import sys,subprocess
import jan_r0 as X
P=X.HERE;E=X.E
mode=sys.argv[1];E.require(mode in ['C10','C_BATCH20'],'only two research modes');gate=X.read(P/'TWO_DAY_GATE.json');E.require(gate['passed'] and gate['runtime_sha256']==X.sha(P/'jan_r0.py') and gate['entry_sha256']==X.sha(P/'run_january.py'),'same-runner prefix source/gate required');z=X.read(P/'runs'/mode/'PROGRESS.json');E.require(str(z['cursor']).startswith('2022-01-05 15:10'),'reuse actual formal prefix without replay')
g=dict(scope='JAN2022_TWO_R0_MONTHS',parent_approved=True,financial_events_authorized=True,start='2022-01-04',end='2022-01-28',modes=['C10','C_BATCH20'],technical_ceiling=250000,runtime_sha256=X.sha(P/'jan_r0.py'),entry_sha256=X.sha(P/'run_january.py'),risk_core_sha256=X.RISK_SHA,input_identity_sha256=X.sha(P/'INPUT_IDENTITY.json'),two_day_gate_sha256=X.sha(P/'TWO_DAY_GATE.json'),parent_scope='exactly original1m C10+R0/C20+R0 Jan4-Jan28 continuous, original warmup, audited rights no-subscription; no old financial account import/reset; noFeb or additionalpolicy',root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b')
f=P/'MONTH_AUTHORIZATION.json'
if f.exists():E.require(X.read(f)==g,'existing January grant differs')
else:X.save(f,g)
with (P/(mode+'-MONTH.out')).open('w') as out,(P/(mode+'-MONTH.err')).open('w') as err:subprocess.run([sys.executable,'-B',str(P/'run_january.py'),'--mode',mode,'--authorization',str(f)],stdout=out,stderr=err,check=True)
print('JANUARY_COMPLETE',mode,flush=True)
