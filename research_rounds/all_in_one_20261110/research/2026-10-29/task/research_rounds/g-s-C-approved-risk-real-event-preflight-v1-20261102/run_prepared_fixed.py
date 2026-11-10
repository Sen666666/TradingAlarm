"""Reuse a source-bound, financial-event-free import. No completed OPEN replay."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
import argparse,traceback,time
import replay_runtime as X
from event_comparison import comparison
E=X.E

def main():
    p=argparse.ArgumentParser();p.add_argument('--import-checkpoint',type=Path,required=True);p.add_argument('--risk',choices=['off','on'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--authorization',type=Path,required=True);p.add_argument('--off-result',type=Path)
    a=p.parse_args();g=X.read(a.authorization)
    E.require(g.get('parent_approved') is True and g.get('financial_events_authorized') is True,'no actual financial authorization')
    E.require(g['resume_driver_sha256']==X.sha(__file__),'actual resume-driver identity changed')
    E.require(g['analysis_helper_sha256']==X.sha(X.HERE/'event_comparison.py'),'actual analysis helper changed')
    gate=X.read(X.HERE/'EXECUTION_GATE.json');E.require(gate['passed'] and gate['runtime_sha256']==X.sha(X.HERE/'replay_runtime.py') and gate['risk_adapter_sha256']==X.RISK_SHA,'identity/import/restart gate required')
    E.require(not a.out.exists(),'new diagnostic branch only; never rerun a completed path')
    r=None;t=time.perf_counter();a.out.mkdir(parents=True)
    try:
        r=X.ReplayRunner.restore(a.import_checkpoint)
        E.require(str(r.last_completed_event)==r.replay_import['old_cursor'],'import-only cursor required, no prior financial event allowed')
        E.require(E.digest(X.snapshot(r))==r.replay_import['old_snapshot_hash'],'original economic prefix differs')
        E.require(not r.risk.orders and not r.risk.fills and all(not v['attempted'] and not v['spent'] for v in r.risk.approvals.values()),'cannot change switch after actual risk activation')
        # The selection is explicit and only before this first diagnostic event.
        before=E.digest(X.snapshot(r));r.keep_approved_risk=a.risk=='on'
        if r.keep_approved_risk and r.active and not r.risk.approvals:r.risk.register(r,r.active['certificate_id'])
        E.require(before==E.digest(X.snapshot(r)),'switch activation changed financial/strategy prefix')
        if r.keep_approved_risk:
            E.require(a.off_result is not None,'same-case actual OFF identity must pass before ON')
            off=X.read(a.off_result)
            E.require(off['off_complete_original_state_identity'] is True and off['origin_checkpoint_sha256']==r.replay_import['parent_checkpoint_sha256'],'OFF case/state identity not proved')
        r.bind_execution(a.authorization);r.checkpoint(a.out/'AUTHORIZED_IMPORT.pkl')
        day=r.replay_import['next_day'];started=datetime.now(timezone.utc).isoformat();oldfill=len(r.account.fills)
        X.save(a.out/'STARTED.json',dict(at=started,case=r.replay_import['case'],risk=a.risk,cursor=r.last_completed_event,authorization=r.replay_authorization))
        print('STARTED_FIXED_OPEN',r.replay_import['case'],a.risk,started,flush=True)
        if r.inputs.actions(day):
            r.corporate_actions(day);r.checkpoint(a.out/(day+'-ACTION.pkl'));X.save(a.out/(day+'-ACTION.json'),r.observable(r.last_completed_event))
        r.step(day,'OPEN')
        r.checkpoint(a.out/(day+'-OPEN.pkl'));X.save(a.out/(day+'-OPEN.json'),r.observable(r.last_completed_event))
        comp=comparison(r,a.out/(day+'-OPEN.pkl'));X.save(a.out/'ACTUAL_OPEN_COMPARISON.json',comp)
        X.save(a.out/'COMPLETED.json',dict(actual_start=started,actual_complete=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-t,origin_checkpoint_sha256=r.replay_import['parent_checkpoint_sha256'],case=r.replay_import['case'],risk=a.risk,cursor=r.last_completed_event,new_fills=[asdict(f) for f in r.account.fills[oldfill:]],bridge=r.account.bridge(r.last_completed_event),no_CLOSE_no_later_day=True))
        print('COMPLETED_FIXED_OPEN',r.replay_import['case'],a.risk,'seconds',round(time.perf_counter()-t,3),flush=True)
    except BaseException as err:
        X.save(a.out/'ERROR.json',dict(error=repr(err),traceback=traceback.format_exc(),cursor=r.last_completed_event if r else None,no_auto_replay=True))
        if r:r.checkpoint(a.out/'FAILED_WORKING_STATE.pkl')
        raise
if __name__=='__main__':main()
