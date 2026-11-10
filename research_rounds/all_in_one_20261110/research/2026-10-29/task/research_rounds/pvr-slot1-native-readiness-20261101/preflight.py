"""Only original H1 identity and two-day native PVR causal/restore checks.

This does not continue either exploratory full-window financial path.
"""
from pathlib import Path
from types import SimpleNamespace
import sys, json, gzip, time, gc, shutil
import execution_support as S
N, J, L, IO, O, W = S.N, S.J, S.L, S.IO, S.O, S.W
sys.path.insert(0, str(W/'migration-admission-native-readiness-20261101'))
from check_identity import observable, event_day

OLD = W/'account-risk-ablation-20261031/run/prefix-full-source/pair'

def rows(p):
    with gzip.open(p,'rt') as f: return [json.loads(x) for x in f]

def compare_original(r, cut):
    checks = {}; counts = {}
    for field, name in [('daily','daily'),('funding','funding'),('opportunities','opportunities'),
                        ('stage_events','industry'),('balance_audit','balances')]:
        old = [x for x in rows(OLD/(name+'.jsonl.gz')) if event_day(x)<=cut]
        checks[name] = J.W.canon(getattr(r,field)) == old; counts[name] = len(old)
        assert checks[name], ('original saved event mismatch', name)
    with gzip.open(OLD/'B.json.gz','rt') as f: book=json.load(f)
    a=r.accounts['B']
    for field,name in [('trades','trades'),('journal','journal'),('audit_log','audit'),('decisions','decisions')]:
        old=[x for x in book[name] if event_day(x)<=cut]
        checks[field]=J.W.canon(getattr(a,field))==old;counts[field]=len(old)
        assert checks[field], ('original native stream mismatch', field)
    return checks,counts

def main():
    begin=time.monotonic();root=O/'preflight'
    IO.prepare_targets(dict(checkpoint=root/'checkpoint.pkl',final=root/'pair',
        failure=root/'failure/ERROR.json'),directory_keys={'final'})
    assert json.loads((O/'RANK_NATIVE_GATE.json').read_text())['passed']
    # Reuse verified, unchanged native16/callback coverage; do not rerun it.
    prior=W/'migration-admission-native-readiness-20261101'
    oldfreeze=json.loads((prior/'FREEZE.json').read_text())
    assert json.loads((prior/'NATIVE_GATE.json').read_text())['passed']
    for p,h in oldfreeze['original_inputs_and_dependencies'].items(): assert N.sha(p)==h,('prior native dependency drift',p)
    reused=dict(prior_gate=str(prior/'NATIVE_GATE.json'),prior_gate_sha256=N.sha(prior/'NATIVE_GATE.json'),
                prior_audited_tests=16,rerun=False,unchanged_dependency_hashes=len(oldfreeze['original_inputs_and_dependencies']))
    S.initialize(N.configure_scores,root,'load original full-domain PVR export')
    # Readiness of the other fixed window; no 2022 account events.
    st=time.monotonic();v=S.initialize(lambda:S.inputs('2022'),root,'read original 2022 inputs only')
    identities={'2022':S.canonical_identity(v[-1])};load2022=time.monotonic()-st
    del v;gc.collect()
    shared,receipts,cp,states,ir,identity=S.initialize(lambda:S.inputs('2025_26'),root,'read original strong-window inputs')
    identities['2025_26']=S.canonical_identity(identity)
    frozen=S.freeze()
    IO.write_json(O/'RUN_SOURCE_FREEZE.json',dict(before_native_events=True,sources=frozen,input_identities=identities,
        source_rule='new policy source frozen; old source files untouched',new_full_financial_paths=0))
    kw=S.kwargs(cp,states,ir);cut='2025-07-02'
    h=S.initialize(lambda:N.Runner(shared,receipts,rank_mode='H1',**kw),root,'H1 off-mode native identity construct')
    h.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(h,L,root/'H1-identity',canonicalize=J.W.canon):
        assert h.run_prepared(root/'H1-identity',120,end=cut)
    checks,counts=compare_original(h,cut)
    h1_original=observable(h)
    # The original short identity run is a gate, not a new baseline financial result.
    p=S.initialize(lambda:N.Runner(shared,receipts,**kw),root,'two-day PVR native prefix construct')
    p.source_freeze=dict(frozen);out=O/'runs/2025_26/prefix-full-source'
    assert not (out/'DONE.json').exists(),'never silently repeat completed PVR prefix'
    with IO.atomic_runner_outputs(p,L,out,canonicalize=J.W.canon):assert p.run_prepared(out,120,end=cut)
    # At the first close before ANY changed fill, membership/targets are exact.
    old_intents=h.accounts['B'].decisions[0]['intents'];new_intents=p.accounts['B'].decisions[0]['intents']
    extras={'rank','original_H1_rank','priority_rank','PVR_score','PVR_ready','priority_policy'}
    strip=lambda rs:[{k:v for k,v in i.items() if k not in extras} for i in rs]
    assert strip(old_intents)==strip(new_intents),'first original targets/qualifications changed'
    phy,rr,pk=S.physical_inputs(shared,receipts,cp,states,ir,cut)
    fullscores=N.SCORES
    def past_only(sid,day):
        assert day<=cut,'physical prefix attempted future PVR access'
        return fullscores.at(sid,day)
    N.SCORES=SimpleNamespace(manifest_sha256=fullscores.manifest_sha256,at=past_only)
    try:
        q=S.initialize(lambda:N.Runner(phy,rr,**pk),root,'physically truncated PVR native prefix')
        q.source_freeze=dict(frozen)
        with IO.atomic_runner_outputs(q,L,root/'PVR-physical',canonicalize=J.W.canon):
            assert q.run_prepared(root/'PVR-physical',120,end=cut)
        assert observable(q)==observable(p) and q.rank_log==p.rank_log
    finally:N.SCORES=fullscores
    restarted=S.initialize(lambda:N.Runner(shared,receipts,**kw),root,'PVR restart identity construct')
    restarted.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(restarted,L,root/'PVR-restart',canonicalize=J.W.canon):
        last=restarted.restore(out/'checkpoint.pkl')
    assert observable(restarted)==observable(p) and restarted.rank_log==p.rank_log
    assert all(i['priority_rank']==i['rank'] and 'original_H1_rank' in i for i in restarted.accounts['B'].pending)
    assert S.freeze()==frozen,'frozen source/input changed during preflight'
    reused_root=O/'prior-native-evidence';reused_root.mkdir(exist_ok=True)
    for name in ['NATIVE_GATE.json','IDENTITY_GATE.json','FREEZE.json']:
        shutil.copy2(prior/name,reused_root/name)
    result=dict(passed=True,scope='native preflight only; no full-window financial comparison',
        H1_off_saved_original_full_event_streams=checks,original_counts=counts,
        physical_native_PVR_prefix_exact=True,score_reader_past_only_assertion=True,
        first_close_candidate_and_target_fields_exact=True,restored_pending_new_and_H1_keys_exact=True,
        PVR_checkpoint_restart_all_native_state_exact=True,both_native_prefix_sides_persisted=True,
        short_window=['2025-07-01',cut],last_completed_prefix_event=str(last),
        original_native_tests_reused=reused,input_identities=identities,
        seconds=dict(read_original_2022_inputs=load2022,total=time.monotonic()-begin,
                     H1_identity=h.run_seconds,PVR_prefix=p.run_seconds,physical_prefix=q.run_seconds),
        new_full_financial_paths=0,approved_to_run_full_windows=False,sources=frozen)
    IO.write_json(O/'PREFLIGHT_GATE.json',result)
    print('PREFLIGHT_PASS',counts,round(time.monotonic()-begin,2),'seconds; full paths 0',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        IO.write_json(O/'failure/PREFLIGHT_ERROR.json',dict(type=type(e).__name__,reason=str(e),new_full_financial_paths=0));raise
