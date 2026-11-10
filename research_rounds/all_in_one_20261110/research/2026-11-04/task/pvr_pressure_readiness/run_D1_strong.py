"""One proposed No60 PVR D1v2 strong path. --prepare is zero-event only."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,json,pickle,time,traceback
import pressure_adapter as A
J,N,L,IO,Q,S=A.J,A.N,A.L,A.IO,A.Q,A.S
O=A.O;ROOT=O/'run-D1-strong';PARENT=O/'prefix/D1_ON/checkpoint.pkl'
AUDIT=O.parent/'independent_review/PVR_PRESSURE_TECHNICAL_AUDIT.json'
CARD=O/'D1_STRONG_SINGLE_CASE_CARD.txt';PROPOSAL=O/'D1_STRONG_EXECUTION_PROPOSAL.json'
GRANT=O/'D1_STRONG_ROOT_GRANT.json';EXTERNAL=ROOT/'EXECUTION_FREEZE.json'
SCOPE='ONE_No60_PVR_D1v2_strong_2025July_2026June_from_own_July3'
CURSOR='2025-07-03T15:10:00+08:00';END='2026-06-30'
CONTROL=A.A.O/'run-PVR-D1'
def save(path,value):IO.write_json(path,J.W.canon(value))
def read(path):return json.loads(Path(path).read_text())
def verify_sources(value):
    for path,h in value.items():assert N.sha(path)==h,('source drift',path)
def proposal():
    assert read(AUDIT)['status'].startswith('PASS')
    payload=pickle.loads(PARENT.read_bytes());verify_sources(payload['source_freeze'])
    assert payload['last_completed_event']==J.M.N.iso(CURSOR)
    b=payload['runner']['composition_binding']
    assert b['policy']=='PVR_PRESSURE_D1v2_NO60' and b['remove_confirmed60'] is True
    assert b['D1_enabled'] is True and b['rank_mode']=='PVR_SLOT1'
    assert b['horizon']['start']=='2025-07-01' and b['horizon']['end']==END
    assert payload['accounts']['B']['initial_cash']==J.D(1000000)
    assert read(CONTROL/'DONE.json')
    outer=[Path(__file__),CARD,AUDIT,O/'PREFIX_GATE.json',O/'CROSS_PROCESS_RESTART.json',
        O/'NEGATIVE_BINDING_GATE.json',CONTROL/'DONE.json',CONTROL/'EXECUTION_STATUS.json',
        CONTROL/'checkpoint.pkl',CONTROL/'pair/B.json.gz']
    value=dict(scope=SCOPE,full_path=['2025-07-01',END],initial_cash=1000000,
        original_parent=str(PARENT),parent_checkpoint_sha256=N.sha(PARENT),
        parent_provenance_sha256=N.sha(PARENT.with_suffix('.provenance.json')),
        parent_cursor=CURSOR,resume_strictly_after_parent=True,
        retained_native_source_freeze=payload['source_freeze'],retained_composition_binding=b,
        parent_source_and_horizon_must_not_be_relabelled=True,
        external_sources={str(p.resolve()):N.sha(p) for p in outer},
        independent_audit_sha256=N.sha(AUDIT),controller_sha256=N.sha(__file__),
        output=str(ROOT),control=str(CONTROL),new_full_paths=1,max_seconds=600,
        automatic_retry=False,other_stress_paths_authorized=False,no_live_or_publish=True)
    if PROPOSAL.exists():assert read(PROPOSAL)==J.W.canon(value),'proposal cannot silently change'
    else:save(PROPOSAL,value)
    return value
def check_grant(p):
    g=read(GRANT)
    expected=dict(approved=True,scope=SCOPE,proposal_sha256=N.sha(PROPOSAL),
        controller_sha256=N.sha(__file__),parent_checkpoint_sha256=p['parent_checkpoint_sha256'],
        independent_audit_sha256=p['independent_audit_sha256'])
    for k,v in expected.items():assert g.get(k)==v,('root grant mismatch',k)
    return g
def main(execute=False,resume=False):
    p=proposal()
    if not execute:
        print('ONE_D1_PATH_PROPOSED_NO_EVENTS',N.sha(PROPOSAL),flush=True);return
    check_grant(p);assert not(ROOT/'DONE.json').exists(),'completed path never repeated'
    if resume:assert (ROOT/'checkpoint.pkl').exists() and EXTERNAL.exists(),'resume needs own pressure checkpoint and external freeze'
    else:assert not (ROOT/'ACTUAL_START.json').exists(),'attempt already exists; inspect before explicit resume'
    expected=dict(p['external_sources']);expected.update({str(PROPOSAL):N.sha(PROPOSAL),str(GRANT):N.sha(GRANT)})
    verify_sources(expected);verify_sources(p['retained_native_source_freeze'])
    if EXTERNAL.exists():assert read(EXTERNAL)==dict(scope=SCOPE,sources=expected,parent_checkpoint_sha256=p['parent_checkpoint_sha256'])
    else:save(EXTERNAL,dict(scope=SCOPE,sources=expected,parent_checkpoint_sha256=p['parent_checkpoint_sha256']))
    started=time.monotonic();N.configure_scores()
    shared,receipts,cp,states,ir,identity=A.read_inputs('2025_26');load_seconds=time.monotonic()-started
    horizon=p['retained_composition_binding']['horizon']
    assert S.canonical_identity(identity)==horizon['input_identity']
    r=A.No60D1Runner(shared,receipts,horizon_binding=copy.deepcopy(horizon),**S.kwargs(cp,states,ir))
    r.source_freeze=copy.deepcopy(p['retained_native_source_freeze'])
    with IO.atomic_runner_outputs(r,L,ROOT/'verified-parent-restore',canonicalize=J.W.canon):at=r.restore(PARENT)
    payload=pickle.loads(PARENT.read_bytes());assert at==J.M.N.iso(CURSOR)
    assert all(Q.equal(v,r.accounts[k].__dict__[f]) for k,a in payload['accounts'].items() for f,v in a.items())
    assert all(Q.equal(v,getattr(r,k)) for k,v in payload['runner'].items())
    assert r.source_freeze==payload['source_freeze'] and r.composition_binding==payload['runner']['composition_binding']
    runner_streams={k:Q.record_digest(payload['runner'][k]) for k in ('daily','opportunities','funding','stage_events','balance_audit','rank_log')}
    account_streams={k:Q.record_digest(payload['accounts']['B'][k]) for k in ('trades','journal','audit_log','decisions','d1_audit')}
    save(ROOT/'PARENT_REUSE_PROOF.json',dict(passed=True,own_parent_sha256=N.sha(PARENT),
        cursor=str(at),source_engine_all_account_and_runner_state_exact=True,
        source_and_composition_binding_unchanged=True,prefix_replayed=False,
        pending_intents=len(r.accounts['B'].pending),active_buys=len(r.accounts['B'].buys),
        sell_obligations=len(r.accounts['B'].exits),runner_streams=runner_streams,account_streams=account_streams))
    if resume:
        with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):at=r.restore(ROOT/'checkpoint.pkl')
        assert at>J.M.N.iso(CURSOR)
    else:save(ROOT/'ACTUAL_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),scope=SCOPE,
        grant_sha256=N.sha(GRANT),external_freeze_sha256=N.sha(EXTERNAL),parent_cursor=str(at)))
    print('ONE_D1_FULL_CONTINUATION_START',str(at),'load_seconds',round(load_seconds,3),flush=True)
    runstart=time.monotonic()
    with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):done=r.run_prepared(ROOT,600,resume_after=at,end=END)
    verify_sources(expected);verify_sources(r.source_freeze);assert N.sha(PARENT)==p['parent_checkpoint_sha256']
    for k,d in runner_streams.items():assert Q.record_digest(getattr(r,k)[:d['records']])==d
    for k,d in account_streams.items():assert Q.record_digest(getattr(r.accounts['B'],k)[:d['records']])==d
    save(ROOT/'EXECUTION_STATUS.json',dict(completed=done,scope=SCOPE,full_path=['2025-07-01',END],
        retained_prefix_through=CURSOR,prefix_replayed=False,source_and_horizon_unchanged=True,
        input_seconds=load_seconds,remaining_run_seconds=time.monotonic()-runstart,total_seconds=time.monotonic()-started,
        ending_NAV=str(r.accounts['B'].current_nav),daily_count=len(r.daily),fills=len(r.accounts['B'].trades),
        old_control_replayed=False,other_full_paths=0))
    print('ONE_D1_COMPLETE' if done else 'ONE_D1_CHECKPOINTED_REQUIRES_EXPLICIT_RESUME',str(r.accounts['B'].current_nav),flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    try:main(args.execute,args.resume)
    except BaseException as e:save(O/'D1_STRONG_PREPARE_OR_RUN_FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc(),scope=SCOPE));raise
