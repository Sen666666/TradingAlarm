"""Read original failed/previous bytes; never retry or advance the account."""
import json,pickle
from pathlib import Path
import month_r0 as X
E=X.E;P=X.HERE;root=P/'runs/C_BATCH20'
def load(p):
 side=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==side['checkpoint_sha256'],'failed bytes changed');r=pickle.loads(p.read_bytes());E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'failed actual engine/source changed');r.account.owner=r;r.assert_observers();return r
r=load(root/'FAILED_WORKING_STATE.pkl');before=load(root/'BEFORE_EVENT.pkl');at=r.last_completed_event
E.require(at.isoformat()=='2025-07-22T15:10:00+08:00' and r.close_stages[at.isoformat()]['optional_status']=='failed_exception','specific failed stage only')
E.require(E.digest(r.authority.__dict__)==E.digest(before.authority.__dict__),'failed optional accepted new authority');E.require(E.digest(r.account.fills)==E.digest(before.account.fills) and E.digest(r.account.trades)==E.digest(before.account.trades),'failed optional executed transactions')
x=r.observable(at);X.save(P/'C20_FAILED_NECESSARY_OBSERVABLE.json',x)
import sys
sys.path.insert(0,str(X.M.C.OLD));from verify_saved import check_json
checks=check_json(P/'C20_FAILED_NECESSARY_OBSERVABLE.json')
X.save(P/'C20_BLOCKED_STAGE_VERIFICATION.json',dict(financial_events=0,failed_checkpoint_sha256=X.sha(root/'FAILED_WORKING_STATE.pkl'),previous_checkpoint_sha256=X.sha(root/'BEFORE_EVENT.pkl'),actual_cursor=at,optional_status='failed_exception',new_authority_accepted=False,new_fill_or_trade=False,source_engine_unchanged=True,independent_financial_differences=checks,stage=r.close_stages[at.isoformat()],actual_balance=x['account']['balance'],resume_requires='explicit technical-source retry at committed necessary stage, not replay CLOSE/F1 or use approximate Q/D; same-evidence failed attempt must remain in history',full_month_completed=False))
print('BLOCKED_STATE_VERIFIED',at,checks,flush=True)
