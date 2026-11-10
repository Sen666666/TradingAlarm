"""Non-financial source/import/switch guards. No event/step/window call."""
from pathlib import Path
import pickle,copy,os
import replay_runtime as X
E=X.E;root=X.HERE;cp=root/'import-smoke/import/IMPORT.pkl'
a=X.read(root/'import-smoke/import/IMPORT.json');b=X.read(root/'RESTORE_SMOKE.json');side=X.read(cp.with_suffix('.provenance.json'))
E.require(a['exact_original_prefix'] and a['old_snapshot_hash']==a['new_original_view_snapshot_hash']==b['original_view_snapshot_hash'],'complete old prefix/restart differs')
E.require(X.sha(cp)==side['checkpoint_sha256'],'import checkpoint changed')
r=pickle.loads(cp.read_bytes());E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'actual imported source/engine mismatch')
before=E.digest(X.snapshot(r));E.require(len(r.risk.approvals)==8 and not r.risk.orders and not r.risk.fills,'wrong activation boundary')
r.assert_observers();r.keep_approved_risk=False;r.assert_observers();E.require(E.digest(X.snapshot(r))==before,'OFF selection changed original state')
r.keep_approved_risk=True;r.assert_observers();E.require(E.digest(X.snapshot(r))==before,'ON selection changed original state')
try:r.execution_guard(r.replay_import['next_day'])
except ValueError as e:E.require('NO financial execution authorization' in str(e),'wrong no-grant guard');no_grant=True
else:raise AssertionError('financial gate did not reject')
bad=root/'guard-fixtures/bad-source.pkl';bad.parent.mkdir(parents=True,exist_ok=True)
if not bad.exists():os.link(cp,bad)
s=copy.deepcopy(side);s['binding']['source'][str(X.RISK/'native_risk.py')]='0'*64;X.save(bad.with_suffix('.provenance.json'),s)
try:X.ReplayRunner.restore(bad)
except ValueError as e:E.require('identity mismatch' in str(e),'wrong source guard');wrong_source=True
else:raise AssertionError('changed source accepted')
E.require(not (root/'MUST_NOT_EXIST').exists(),'false financial grant created a branch')
X.save(root/'EXECUTION_GATE.json',dict(passed=True,financial_events=0,new_inputs_or_signals=False,runtime_sha256=X.sha(root/'replay_runtime.py'),entry_sha256=X.sha(root/'run_open.py'),risk_adapter_sha256=X.RISK_SHA,input_binding_sha256=X.sha(root/'REPLAY_INPUT_BINDING.json'),import_checkpoint=str(cp),import_checkpoint_sha256=X.sha(cp),old_snapshot_hash=before,old_new_prefix_exact=True,cross_process_restore_exact=True,switch_off_on_no_financial_change=True,only_active_stock_authorizations=8,legacy_completed_orders_preserved=True,wrong_source_rejected=wrong_source,no_grant_rejected=no_grant,physical_source_truncation='existing frozen loader/input prefix audits reused; no new physical truncation claimed',next_gate='each actual OFF whole OPEN must equal saved original before corresponding ON'))
print('IMPORT_SWITCH_RESTORE_GATE_PASS',flush=True)
