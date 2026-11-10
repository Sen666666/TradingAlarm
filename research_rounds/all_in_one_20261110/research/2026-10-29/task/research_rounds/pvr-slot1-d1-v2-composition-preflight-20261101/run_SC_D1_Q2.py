"""Prepared thin command only: SC-D1 own Apr1 -> Jun30, authorization absent.

No new restorer/importer: exact Composition.restore and original run_prepared.
Without a later root authorization file, --execute fails BEFORE input loading
or account construction. The default invocation prints readiness only.
"""
from pathlib import Path
import argparse, copy, json, pickle, time
from datetime import datetime, timezone
import composition as A
J,L,N,IO,Q,O=A.J,A.L,A.N,A.IO,A.Q,A.O
ROOT=O/'SC-D1-Q2-continuation'
AUTH=ROOT/'FULL_RUN_AUTHORIZATION.json'
PARENT=O/'SC-April1-first-session/full-input/checkpoint.pkl'
PARENT_SHA='b6e09b25e6145f3efd618cd42cf242303419514f28d3a8b11b361787cc3de5ff'
AT=J.M.N.iso('2026-04-01T15:10:00+08:00')
COMPOSITION_SHA='de4f050a01a3a0c54e86f3851b593decaf8077adb052dac5f97b2e9c7c91a861'
SCOPE='ONE_SC_Bdiag_D1_v2_Q2_continuation_after_April1'

def save(path,value):IO.write_json(path,J.W.canon(value))

def require_authorization():
    assert AUTH.is_file(), 'SC Apr2+ not authorized: FULL_RUN_AUTHORIZATION.json absent'
    auth=json.loads(AUTH.read_text())
    assert auth['scope']==SCOPE and auth['root_approved'] is True
    assert auth['parent_checkpoint_sha256']==PARENT_SHA==A.sha(PARENT)
    assert auth['composition_sha256']==COMPOSITION_SHA==A.sha(O/'composition.py')
    assert auth['controller_sha256']==A.sha(__file__)
    assert auth['resume_strictly_after']=='2026-04-01 15:10:00+08:00'
    assert auth['end']=='2026-06-30' and auth['only_one_SC_continuation'] is True
    assert auth['SC_April1_independent_audit_reviewed'] is True
    return auth

def main(execute=False):
    if not execute:
        print('READINESS ONLY: direct own Apr1 checkpoint resume. No new account events. Later root auth required.',flush=True)
        return
    auth=require_authorization()  # Before input/account work; never creates an authorization.
    assert not (ROOT/'DONE.json').exists(),'completed SC continuation must not be repeated'
    IO.prepare_targets(dict(checkpoint=ROOT/'checkpoint.pkl',final=ROOT/'pair',
        failure=ROOT/'failure/ERROR.json'),directory_keys={'final'})
    start=time.monotonic();save(ROOT/'ACTUAL_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),
        authorization_sha256=A.sha(AUTH),scope=SCOPE))
    N.configure_scores()
    t=time.monotonic();shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26');load=time.monotonic()-t
    parent=pickle.loads(PARENT.read_bytes());oldfreeze=parent['source_freeze']
    assert parent['last_completed_event']==AT
    assert all(A.sha(path)==h for path,h in oldfreeze.items()),'Apr1 source/input binding changed'
    binding=parent['runner']['composition_binding']['horizon']
    assert binding['input_identity']==A.S.canonical_identity(identity)
    r=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,
        **A.S.kwargs(cp,states,ir));r.source_freeze=copy.deepcopy(oldfreeze)
    with IO.atomic_runner_outputs(r,L,ROOT/'Apr1-parent-restore-only',canonicalize=J.W.canon):
        assert r.restore(PARENT)==AT
    assert all(Q.equal(v,r.accounts['B'].__dict__[k]) for k,v in parent['accounts']['B'].items())
    assert all(Q.equal(v,getattr(r,k)) for k,v in parent['runner'].items())
    assert len(r.accounts['B'].pending)==270 and len(r.accounts['B'].exits)==11 and not r.accounts['B'].buys
    assert sum(x.delay_remaining==0 for x in r.accounts['B'].exits.values())==10
    # NO configure_d1/reset/clearing of pending/exits/receipts/core/ACT/losses.
    # Only explicit new execution-control metadata is appended after old restore.
    frozen=dict(oldfreeze);frozen.update({str(Path(__file__).resolve()):A.sha(__file__),str(AUTH.resolve()):A.sha(AUTH)})
    r.source_freeze=dict(frozen)
    save(ROOT/'FROZEN_RUN_METADATA.json',dict(sources=frozen,parent_sha256=PARENT_SHA,
        controller_metadata_extension_after_original_identity_verified=True,
        preserved_all_account_and_runner_fields=True,input_identity=A.S.canonical_identity(identity),
        original_initial_cash=1000000,account_NAV_at_resume=str(r.accounts['B'].current_nav),
        resume_cursor=str(AT),full_dates=['2025-07-01','2026-06-30']))
    after=AT
    if (ROOT/'checkpoint.pkl').exists():
        with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):after=r.restore(ROOT/'checkpoint.pkl')
        assert after>AT
    begin=time.monotonic()
    with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):
        done=r.run_prepared(ROOT,600,resume_after=after,end='2026-06-30')
    assert all(A.sha(path)==h for path,h in frozen.items())
    assert A.sha(PARENT)==PARENT_SHA,'Apr1 parent checkpoint changed'
    for key in ('daily','opportunities','funding','stage_events','balance_audit','rank_log'):
        old=parent['runner'][key];assert Q.equal(old,getattr(r,key)[:len(old)])
    for key in ('trades','journal','audit_log','decisions','d1_audit'):
        old=parent['accounts']['B'][key];assert Q.equal(old,getattr(r.accounts['B'],key)[:len(old)])
    save(ROOT/'EXECUTION_STATUS.json',dict(completed=done,scope=SCOPE,
        input_seconds=load,remaining_path_and_export_seconds=time.monotonic()-begin,
        total_seconds=time.monotonic()-start,old183_days_append_only=True,
        original_initial_cash_not_repeated=True,Apr1_prefix_reexecuted=False,
        ending_NAV=str(r.accounts['B'].current_nav),daily_count=len(r.daily)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    try:main(args.execute)
    except BaseException as ex:
        save(ROOT/'failure/ERROR.json',dict(type=type(ex).__name__,reason=str(ex),
            scope='prepared single SC continuation; no authorization auto-created'));raise
