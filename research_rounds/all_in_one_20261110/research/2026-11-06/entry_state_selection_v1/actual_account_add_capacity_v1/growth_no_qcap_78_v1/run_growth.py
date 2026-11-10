"""Authorized single 78-session no-quantity-cap arm. Refuses to run before explicit audit gate."""
from pathlib import Path
from decimal import Decimal as D
import argparse,gzip,json,sys,time,traceback
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'growth_continuous_78_v1'
sys.path.insert(0,str(OLD/'baseline'))
import resume_baseline as B
from growth_adapter import install_growth,observe
S=B.S

def verify_gate():
    baseline=OLD/'baseline/run/BASELINE_VALIDATION.json'
    assert baseline.exists() and S.read(baseline)['passed'],'Original continuation not exactly reproduced'
    gate_path=HERE/'AUDIT_GATE.json'
    assert gate_path.exists(),'New independent review must complete before no-cap execution'
    gate=S.read(gate_path)
    assert gate['passed'] and gate['growth_execution_cleared']
    assert gate['scope']=='Single no-qcap 78-session run; no other economic change'
    assert gate['baseline_validation_sha256']==B.sha(baseline)
    required={str(HERE/p) for p in ('CONTRACT.md','growth_book.py','test_growth_book.py','growth_adapter.py','run_growth.py','UNIT_TESTS.json','UNIT_TESTS.log','ECONOMIC_DIFF.json','SOURCE_IDENTITY.json')}
    required.update([str(baseline),str(OLD/'baseline/resume_baseline.py'),str(OLD/'growth_book.py'),str(OLD/'growth_adapter.py'),str(OLD/'growth/run/DONE.json')])
    assert required<=set(gate['reviewed_sources']),('incomplete reviewed source/evidence set',required-set(gate['reviewed_sources']))
    for path,h in gate['reviewed_sources'].items():
        assert B.sha(path)==h,('reviewed source changed',path)
    identity=S.read(HERE/'SOURCE_IDENTITY.json')
    for path,h in identity['source_hashes'].items():
        assert B.sha(path)==h,('prior sealed source changed',path)
    assert str(Path(__file__).resolve()) in gate['reviewed_sources']
    return gate

def main():
    parser=argparse.ArgumentParser();parser.parse_args()
    gate=verify_gate();out=HERE/'growth/run'
    assert not (HERE/'growth').exists(),'Single-run contract: any growth directory blocks another run'
    marker=HERE/'EXECUTION_STARTED.json'
    with marker.open('x') as f:
        json.dump(dict(scope='Single no-qcap 78-session run; no other economic change',started_unix=time.time(),output=str(out),audit_gate_sha256=B.sha(HERE/'AUDIT_GATE.json'),automatic_retry_forbidden=True),f,indent=2)
    out.mkdir(parents=True);started=time.monotonic();last=None
    try:
        boot=B.bootstrap_original()
        with B.restored_original(boot,out/'original_restore') as (last,audit):
            S.save(out/'RESTORE_AUDIT.json',audit)
        r=install_growth(boot)
        for p in (Path(__file__),HERE/'AUDIT_GATE.json'):r.source_freeze[str(p)]=B.sha(p)
        S.save(out/'PREDECLARED.json',dict(start=B.EVENT_START,end=B.EVENT_END,sessions=78,
            mode='CONTINUOUS_SAME_CHECKPOINT_GROWTH_LAYER_COST_025_NO_QCAP',checkpoint=str(B.CHECKPOINT),
            checkpoint_sha256=B.CHECKPOINT_SHA256,first_trial_unchanged=True,original_profit_avg_gate_preserved=True,
            growth_budget_cost='ACTUAL_REMAINING_LAYER_ACQUISITION_COST',formula='H+L+P+D_new(q)<=0.25*R0+U_layer_post(q)',
            additional_conditions='U_layer_pre>0; U_layer_post>0; positive legal q; all original gates; NO q<=currentQ ceiling',
            H_scope='NEGATIVE_REALIZED_TRUE_ADD_PARTS_ONLY',H_all_diagnostic_only=True,original_sources_unchanged=True,
            no_parameter_scan=True,no_annual_reset=True,real_orders=False,input_identity=boot['input_identity'],
            source_freeze=r.source_freeze,independent_gate=gate,
            limitations='Fixed future 1709 pool; not PIT; actual tradability UNKNOWN; conditional protection is not locked cash; no 924 coverage in 78-day window.'))
        S.save(out/'INITIAL_GROWTH_STATES.json',{k:b.states for k,b in r.growth_books.items()})
        with S.IO.atomic_runner_outputs(r,S.L,out,canonicalize=S.canon):
            last,run=B.run_window(boot,last,after_event=observe)
            r.assert_growth_wiring()
            S.IO.write_gzip_jsonl(out/'EVENT_CLOCK.jsonl.gz',run.pop('event_rows'),encoder=S.J.C.encoded)
            r.checkpoint(out/'latest_checkpoint',last);r.dump_joint(out/'pair')
        B.verify_frozen_sources(r.source_freeze)
        assert B.sha(B.CHECKPOINT)==B.CHECKPOINT_SHA256
        for name,rows in [('PROFIT_GATE_EVENTS',r.profit_gate_events),('GROWTH_CANDIDATES',r.growth_candidates),('GROWTH_OBSERVATIONS',r.growth_observations),('OPEN_CASH_CHECKS',r.open_checks),('SHARED_WINDOW_AUDIT',boot['market'].exec_rows)]:
            S.IO.write_gzip_jsonl(out/(name+'.jsonl.gz'),rows,encoder=S.J.C.encoded)
        S.save(out/'GROWTH_STATES.json',{k:b.states for k,b in r.growth_books.items()})
        S.IO.write_gzip_jsonl(out/'REALIZED_LAYER_PARTS.jsonl.gz',[x for b in r.growth_books.values() for x in b.history],encoder=S.J.C.encoded)
        S.save(out/'REMAINING_AVERAGE_COST_BOOK.json',r.cost_books['PVR'].states)
        result=dict(completed=True,last_event=last,seconds=time.monotonic()-started,
            boot_seconds=boot['boot_seconds'],**run,holdings_count=len(r.accounts['PVR'].positions),
            ending_cash=str(r.accounts['PVR'].available),ending_nav=str(r.accounts['PVR'].current_nav),
            growth_candidates=len(r.growth_candidates),observations=len(r.growth_observations),
            source_files_unchanged=True,original_checkpoint_unchanged=True,real_orders=False)
        S.save(out/'DONE.json',result)
        S.save(out/'OUTPUT_HASHES.json',{str(p.relative_to(out)):B.sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
        print('DONE',json.dumps(S.canon(result)),flush=True)
    except BaseException as exc:
        S.save(out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),last_complete_event=last,partial_event_not_resumable=True,auto_retry=False))
        raise
if __name__=='__main__':main()
