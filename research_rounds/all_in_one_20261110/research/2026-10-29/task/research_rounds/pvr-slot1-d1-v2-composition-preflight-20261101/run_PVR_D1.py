"""Exactly ONE authorized PVR_SLOT1 x D1-v2 strong-window pressure path.

Resume the verified own July7 full-input checkpoint. Never replay SC, normal
PVR, or the completed technical prefix. No SC account events are run here.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, copy, json, pickle, time
import composition as A
J,L,N,IO,Q,O=A.J,A.L,A.N,A.IO,A.Q,A.O
ROOT=O/'run-PVR-D1'
AUTH=ROOT/'FULL_RUN_AUTHORIZATION.json'
PARENT=O/'preflight/PVR-D1-full-source/checkpoint.pkl'
END='2026-06-30';COMPOSITION_SHA='de4f050a01a3a0c54e86f3851b593decaf8077adb052dac5f97b2e9c7c91a861'

def save(path,value):IO.write_json(path,J.W.canon(value))

def authorization():
    value=dict(scope='ONE_PVR_SLOT1_x_D1_v2_2025July_2026June_original_1m',
        authority='Root explicit full-path authorization after independent native audit; SC remains April1 only',
        dates=['2025-07-01',END],initial_cash=1000000,
        policy='original singlepass coupled Bdiag with frozen PVR_SLOT1 plus D1-v2 only',
        composition_sha256=COMPOSITION_SHA,PVR_sha256=A.PVR_SHA,D1_v2_sha256=A.D1_SHA,
        own_full_input_prefix_checkpoint=str(PARENT),prefix_checkpoint_sha256=A.sha(PARENT),
        prefix_cursor='2025-07-07 15:10:00+08:00',resume_strictly_after_cursor=True,
        no_normal_PVR_or_SC_midaccount_import=True,technical_prefix_reexecuted=False,
        controller_sha256=A.sha(__file__),max_seconds=600,
        source_binding_extension='after old identity/source verified, add only this authorized controller and auth metadata',
        other_financial_paths_authorized=False,no_live_or_broker_or_cron=True)
    if AUTH.exists():
        old=json.loads(AUTH.read_text());assert {k:v for k,v in old.items() if k!='created_at_UTC'}==value
        return old
    value['created_at_UTC']=datetime.now(timezone.utc).isoformat()
    save(AUTH,value);return value

def main(execute=False):
    assert A.sha(O/'composition.py')==COMPOSITION_SHA
    assert json.loads((O/'PREFLIGHT_GATE.json').read_text())['passed']
    assert json.loads((O/'SC-April1-first-session/FIRST_SESSION_GATE.json').read_text())['passed'], 'complete and save April1 first'
    IO.prepare_targets(dict(auth=AUTH,final=ROOT/'pair',checkpoint=ROOT/'checkpoint.pkl',
        failure=ROOT/'failure/ERROR.json'),directory_keys={'final'})
    if not execute:
        print('ONE PVR-D1 path ready; requires --execute; SC events are never called',flush=True);return
    auth=authorization()
    assert not (ROOT/'DONE.json').exists(),'completed full path must never be silently repeated'
    start=time.monotonic();save(ROOT/'ACTUAL_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),
        authorization_sha256=A.sha(AUTH),controller_sha256=A.sha(__file__),scope=auth['scope']))
    N.configure_scores()
    loaded=time.monotonic();shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26');load=time.monotonic()-loaded
    parent=pickle.loads(PARENT.read_bytes());oldfreeze=parent['source_freeze']
    for name,h in oldfreeze.items():assert A.sha(name)==h,('original prefix source drift',name)
    binding=parent['runner']['composition_binding']['horizon']
    assert binding['input_identity']==A.S.canonical_identity(identity)
    r=A.Composition(shared,receipts,rank_mode='PVR_SLOT1',enabled=True,horizon_binding=binding,
        **A.S.kwargs(cp,states,ir))
    r.source_freeze=copy.deepcopy(oldfreeze)
    with IO.atomic_runner_outputs(r,L,ROOT/'verified-prefix-restore',canonicalize=J.W.canon):at=r.restore(PARENT)
    assert at==J.M.N.iso('2025-07-07T15:10:00+08:00')
    assert all(Q.equal(v,r.accounts['B'].__dict__[k]) for k,v in parent['accounts']['B'].items())
    assert all(Q.equal(v,getattr(r,k)) for k,v in parent['runner'].items())
    assert r.accounts['B'].initial_cash==J.D(1000000)
    streams={k:Q.record_digest(parent['runner'][k]) for k in
        ('daily','opportunities','funding','stage_events','balance_audit','rank_log')}
    account_streams={k:Q.record_digest(parent['accounts']['B'][k]) for k in
        ('trades','journal','audit_log','decisions','d1_audit')}
    save(ROOT/'PREFIX_REUSE_PROOF.json',dict(passed=True,parent_sha256=A.sha(PARENT),
        parent_provenance_sha256=A.sha(PARENT.with_suffix('.provenance.json')),
        all_live_account_and_runner_fields_exact=True,old_generation_identity_verified=True,
        old_source_freeze_exact=True,technical_prefix_reexecuted=False,
        prefix_streams=streams,prefix_account_streams=account_streams,
        inherited_pending_intents=len(r.accounts['B'].pending),inherited_active_buys=len(r.accounts['B'].buys),
        inherited_exits=len(r.accounts['B'].exits),cursor=str(at)))
    frozen=dict(oldfreeze);frozen.update({str(Path(__file__).resolve()):A.sha(__file__),str(AUTH.resolve()):A.sha(AUTH)})
    r.source_freeze=dict(frozen)
    save(ROOT/'FROZEN_RUN_METADATA.json',dict(before_remaining_account_events=True,
        sources=frozen,input_identity=A.S.canonical_identity(identity),binding=binding,
        original_prefix_sha256=A.sha(PARENT),initial_cash=1000000,dates=auth['dates'],
        actual_identity=IO.runner_identity(r),authorization_sha256=A.sha(AUTH)))
    if (ROOT/'checkpoint.pkl').exists():
        with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):at=r.restore(ROOT/'checkpoint.pkl')
        assert at>J.M.N.iso('2025-07-07T15:10:00+08:00')
        print('PVR_D1_CONTINUE_EXISTING_CHECKPOINT',str(at),flush=True)
    print('PVR_D1_AUTHORIZED_REMAINING_PATH_START',str(at),'input_seconds',round(load,3),flush=True)
    runstart=time.monotonic()
    with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):done=r.run_prepared(ROOT,600,resume_after=at,end=END)
    elapsed=time.monotonic()-runstart
    assert all(A.sha(p)==h for p,h in frozen.items()),'source/input changed during pressure path'
    assert A.sha(PARENT)==auth['prefix_checkpoint_sha256'],'old prefix was written'
    for key,proof in streams.items():assert Q.record_digest(getattr(r,key)[:proof['records']])==proof
    for key,proof in account_streams.items():assert Q.record_digest(getattr(r.accounts['B'],key)[:proof['records']])==proof
    save(ROOT/'EXECUTION_STATUS.json',dict(completed=done,scope=auth['scope'],
        stopped_or_completed_at_UTC=datetime.now(timezone.utc).isoformat(),
        input_seconds=load,remaining_native_replay_export_seconds=elapsed,total_seconds=time.monotonic()-start,
        old_prefix_all_history_exact=True,technical_prefix_reexecuted=False,
        SC_account_events=0,ending_NAV=str(r.accounts['B'].current_nav),
        daily_count=len(r.daily),fills=len(r.accounts['B'].trades)))
    print('PVR_D1_COMPLETE' if done else 'PVR_D1_CHECKPOINTED_AT_BUDGET',
        str(r.accounts['B'].current_nav),round(elapsed,3),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    try:main(args.execute)
    except BaseException as ex:
        save(ROOT/'failure/ERROR.json',dict(type=type(ex).__name__,reason=str(ex),
            scope='one PVR-D1 path; preserve completed checkpoints; SC April events not called'));raise
