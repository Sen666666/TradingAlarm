"""Authorized short native gates and SC no-event horizon import ONLY."""
from pathlib import Path
from types import SimpleNamespace
import copy, gc, gzip, json, pickle, time
import composition as A
E,J,L,N,IO,Q,O,W=A.E,A.J,A.L,A.N,A.IO,A.Q,A.O,A.W
ROOT=O/'preflight'
CUT='2025-07-07'
STREAMS=[('daily','daily'),('funding','funding'),('opportunities','opportunities'),
         ('stage_events','industry'),('balance_audit','balances')]
IMMUTABLE={'market','facts'}

def initialize(factory,stage):
    try:return factory()
    except BaseException as ex:
        IO.write_json(ROOT/'failure/INITIALIZATION_ERROR.json',dict(stage=stage,
            type=type(ex).__name__,reason=str(ex),full_financial_paths=0))
        raise

def account_state(a, *, omit_calendar=False, omit_d1=False):
    return {k:v for k,v in a.__dict__.items() if k not in IMMUTABLE
        and not (omit_calendar and k=='d1_calendar') and not (omit_d1 and k.startswith('d1_'))}

def observable(r):
    # Calendar and industry lookup extension are source inputs, not live state.
    # Their past-prefix identity is checked separately.
    return dict(accounts={k:account_state(a,omit_calendar=True) for k,a in r.accounts.items()},
        streams={f:getattr(r,f) for f,_ in STREAMS},rank_log=r.rank_log)

def saved_identity(r, directory, *, off=False):
    directory=Path(directory);p=pickle.loads((directory/'checkpoint.pkl').read_bytes())
    checks={};counts={}
    for field,name in STREAMS:
        with gzip.open(directory/'pair'/(name+'.jsonl.gz'),'rt') as f:old=[json.loads(x) for x in f]
        actual=J.W.canon(getattr(r,field));checks[name]=actual==old;counts[name]=len(old)
        assert checks[name],('frozen saved stream mismatch',name)
    for key,a in r.accounts.items():
        old=p['accounts'][key]
        current=account_state(a,omit_calendar=True,omit_d1=off)
        old={k:v for k,v in old.items() if k!='d1_calendar' and not(off and k.startswith('d1_'))}
        assert current.keys()==old.keys(),('frozen account field mismatch',set(current)^set(old))
        failures=[k for k,v in current.items() if not Q.equal(v,old[k])]
        assert not failures,('frozen complete account mismatch',failures)
        checks[key+'_all_native_account_fields']=len(current)
        if not off:
            oldcal=p['accounts'][key]['d1_calendar'];newcal=a.d1_calendar
            assert [x for x in newcal if x<=oldcal[-1]]==list(oldcal)
            checks[key+'_old_calendar_prefix_exact']=True
    if off:
        assert Q.equal(r.rank_log,p['runner']['rank_log'])
        checks['PVR_frozen_priority_log_exact']=True
    return dict(passed=True,checks=checks,counts=counts,
        frozen_checkpoint_sha256=A.sha(directory/'checkpoint.pkl'))

def run_short(shared,receipts,kw,frozen,binding,name,rank_mode,enabled,end):
    out=ROOT/name
    r=initialize(lambda:A.Composition(shared,receipts,rank_mode=rank_mode,enabled=enabled,
        horizon_binding=binding,**kw),name+' construct')
    r.source_freeze=dict(frozen)
    # Never silently repeat a completed prefix after an export/report failure.
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
        if (out/'DONE.json').exists():
            assert r.restore(out/'checkpoint.pkl')==J.M.N.iso(end+'T15:10:00+08:00')
        else:assert r.run_prepared(out,120,end=end)
    return r

def check_restore(r,shared,receipts,kw,frozen,binding,path):
    clone=A.Composition(shared,receipts,rank_mode=r.rank_mode,enabled=r.d1_enabled,
        horizon_binding=binding,**kw);clone.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(clone,L,ROOT/'restart',canonicalize=J.W.canon):at=clone.restore(path)
    assert Q.equal(observable(r),observable(clone)),'complete composed restart mismatch'
    negatives={}
    for case,change in [('rank',lambda b:b.update(rank_mode='H1')),
                        ('horizon',lambda b:b['horizon'].update(unapproved_end='2099-01-01')),
                        ('scores',lambda b:b.update(PVR_scores_manifest_sha256='wrong')),
                        ('source',lambda b:b.update(D1_source_sha256='wrong'))]:
        wrong=A.Composition(shared,receipts,rank_mode=r.rank_mode,enabled=r.d1_enabled,
            horizon_binding=binding,**kw);wrong.source_freeze=dict(frozen)
        change(wrong.composition_binding)
        try:
            with IO.atomic_runner_outputs(wrong,L,ROOT/('wrong-'+case),canonicalize=J.W.canon):wrong.restore(path)
        except (AssertionError,ValueError) as ex:negatives[case]=str(ex)
        else:raise AssertionError('wrong binding accepted: '+case)
        del wrong
    return dict(passed=True,cursor=str(at),complete_economic_state_equal=True,
        negative_guards=negatives)

def main():
    begin=time.monotonic()
    IO.prepare_targets(dict(checkpoint=ROOT/'checkpoint.pkl',final=ROOT/'pair',
        physical=ROOT/'physical/pair',SC=ROOT/'SC-Q2-import/checkpoint.pkl',
        failure=ROOT/'failure/ERROR.json'),directory_keys={'final','physical'})
    gate=json.loads((O/'NATIVE_GATE.json').read_text())
    assert gate['passed'] and gate['composition_sha256']==A.sha(O/'composition.py')
    initialize(N.configure_scores,'load frozen full-domain PVR scores')
    started=time.monotonic()
    shared,receipts,cp,states,ir,identity=initialize(lambda:A.S.inputs('2025_26'),'read frozen full-horizon original inputs')
    load_seconds=time.monotonic()-started
    assert len(identity['account_ids'])==1709 and len(identity['sector_ids'])==90
    binding=dict(start='2025-07-01',end='2026-06-30',input_identity=A.S.canonical_identity(identity),
                 scores_manifest_sha256=N.SCORES.manifest_sha256)
    frozen=A.source_freeze()
    IO.write_json(O/'SOURCE_FREEZE.json',dict(sources=frozen,before_native_events=True,
        input_identity=A.S.canonical_identity(identity),binding=binding,full_financial_paths=0))
    kw=A.S.kwargs(cp,states,ir)
    print('COMPOSITION_INPUTS_READY',round(load_seconds,3),flush=True)

    r=run_short(shared,receipts,kw,frozen,binding,'D0-PVR-identity','PVR_SLOT1',False,'2025-07-02')
    d0=saved_identity(r,A.P/'runs/2025_26/prefix-full-source',off=True)
    IO.write_json(O/'D0_PVR_IDENTITY_GATE.json',d0)
    print('D0_PVR_SAVED_NORMAL_EXACT',d0['counts'],flush=True)
    del r;gc.collect()

    h=run_short(shared,receipts,kw,frozen,binding,'D1-H1-identity','H1',True,CUT)
    d1=saved_identity(h,A.D1/'runs/B_diag/prefix-full-source')
    IO.write_json(O/'D1_H1_IDENTITY_GATE.json',d1)
    print('D1_H1_SAVED_D1_EXACT',d1['counts'],flush=True)
    del h;gc.collect()

    r=run_short(shared,receipts,kw,frozen,binding,'PVR-D1-full-source','PVR_SLOT1',True,CUT)
    phy,rr,pk=A.S.physical_inputs(shared,receipts,cp,states,ir,CUT)
    fullscores=N.SCORES
    def past_only(sid,day):
        assert day<=CUT,'physical PVR source accessed a future date'
        return fullscores.at(sid,day)
    N.SCORES=SimpleNamespace(manifest_sha256=fullscores.manifest_sha256,at=past_only)
    try:
        physical=run_short(phy,rr,pk,frozen,binding,'PVR-D1-physical-source','PVR_SLOT1',True,CUT)
        assert Q.equal(observable(r),observable(physical)),'PVR-D1 physical prefix mismatch'
        calendar=r.accounts['B'].d1_calendar;pc=physical.accounts['B'].d1_calendar
        assert [x for x in calendar if x<=pc[-1]]==list(pc)
    finally:N.SCORES=fullscores
    restart=check_restore(r,shared,receipts,kw,frozen,binding,
        ROOT/'PVR-D1-full-source/checkpoint.pkl')
    IO.write_json(O/'COMPOSITION_PREFIX_RESTART_GATE.json',dict(passed=True,
        cut=CUT,physical_all_native_state_and_priority_exact=True,
        both_sides_saved=True,original_calendar_prefix_exact=True,
        future_score_access_guard=True,restart=restart,
        fills=len(r.accounts['B'].trades),retained_buys=len(r.accounts['B'].buys)))
    print('PVR_D1_PREFIX_RESTART_PASS',len(r.accounts['B'].trades),flush=True)
    del r,physical,phy,rr,pk;gc.collect()

    # Verify old provenance under OLD original module/class before importing.
    parent=A.D1/'runs/B_diag/checkpoint.pkl'
    parent_before=A.sha(parent);side_before=A.sha(parent.with_suffix('.provenance.json'))
    stager,payload,oldproof=A.verify_old_sc(shared,receipts,kw,parent)
    target=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,**kw)
    target.source_freeze=dict(frozen)
    at,proof=A.import_sc_horizon(target,stager,payload,oldproof,binding)
    import_out=ROOT/'SC-Q2-import'
    with IO.atomic_runner_outputs(target,L,import_out,canonicalize=J.W.canon):
        target.checkpoint(import_out,at)
    clone=A.Composition(shared,receipts,rank_mode='H1',enabled=True,horizon_binding=binding,**kw)
    clone.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(clone,L,ROOT/'SC-Q2-import-restart',canonicalize=J.W.canon):
        assert clone.restore(import_out/'checkpoint.pkl')==at
    assert Q.equal(observable(target),observable(clone))
    assert all(Q.equal(v,clone.accounts['B'].__dict__[k]) for k,v in payload['accounts']['B'].items())
    assert A.sha(parent)==parent_before and A.sha(parent.with_suffix('.provenance.json'))==side_before
    proof.update(new_checkpoint_sha256=A.sha(import_out/'checkpoint.pkl'),
        new_provenance_sha256=A.sha(import_out/'checkpoint.provenance.json'),
        full_state_restart_exact=True,all_119_frozen_pending_keys_unchanged=True,
        source_freeze=frozen,first_session_event_permission_needed=True,
        needed_event_scope='SC April1 full-input vs physically truncated first-session branch only; not executed')
    IO.write_json(O/'SC_Q2_HORIZON_IMPORT_MANIFEST.json',J.W.canon(proof))
    assert A.source_freeze()==frozen,'frozen dependency changed during preflight'
    result=dict(passed=True,scope='isolated composition and no-event horizon preflight only',
        native_tests=gate['tests'],D0_PVR_saved_normal_exact=True,D1_H1_saved_D1_exact=True,
        composition_July7_physical_prefix_restart=True,SC_original_identity_then_explicit_horizon_import=True,
        SC_119_intents_16_exits_preserved=True,SC_April_events=0,full_financial_paths=0,
        no_production_or_old_archive_edits=True,first_session_event_permission_needed=True,
        seconds=dict(original_input_load=load_seconds,total=time.monotonic()-begin),
        sources=frozen,source_adapter_sha256=A.sha(O/'composition.py'),
        future_full_runs_not_authorized=True)
    IO.write_json(O/'PREFLIGHT_GATE.json',result)
    print('ALL_PREFLIGHT_PASS',round(time.monotonic()-begin,3),'seconds; full paths 0; SC Apr events 0',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as ex:
        IO.write_json(ROOT/'failure/PREFLIGHT_ERROR.json',dict(type=type(ex).__name__,
            reason=str(ex),full_financial_paths=0,SC_April_events=0))
        raise
