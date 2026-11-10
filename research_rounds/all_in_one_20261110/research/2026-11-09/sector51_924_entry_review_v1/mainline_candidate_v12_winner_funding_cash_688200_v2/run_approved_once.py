"""Prepared one-shot offline runner. --check is read-only; --run requires parent seal.

Never manufactures approval. No resume/migration or alternate economic path.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
import traceback
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def prepare():
    m=module('approved_v12_cash688200',O/'engine.py')
    cp=module('approved_v12_checkpoint',O/'checkpoint.py')
    prefix=module('approved_v12_prefix',O/'prefix_check.py')
    manifest=m.read(O/'SOURCE_HASHES.json')
    for p,h in manifest['files'].items():assert m.stream.file_sha(p)==h,('SOURCE_DRIFT',p)
    assert m.self_check()['result']=='PASS'
    for name in ['SYNTHETIC_QA','CHECKPOINT_QA','BRIDGE_BRANCH_QA','RUNNER_QA']:
        assert m.read(O/(name+'.json'))['result']=='PASS',('QA_NOT_PASS',name)
    return m,cp,prefix,manifest

def approved(m):
    a=m.read(O/'EXPERIMENT_APPROVAL.json')
    assert a['approved'] is True and a['one_shot'] is True and a['research_only'] is True
    assert (a['start'],a['end'],a['days'],a['initial_cash'])==('2024-09-02','2025-01-20',93,'1200000')
    assert a['source_manifest_sha256']==m.stream.file_sha(O/'SOURCE_HASHES.json')
    required={str(O/n) for n in ['engine.py','stream_output.py','checkpoint.py','prefix_check.py','run_approved_once.py','synthetic_tests.py','checkpoint_tests.py','bridge_branch_tests.py','runner_tests.py','CONTRACT.md','ADMISSION_LOCK.json','PREFIX_REFERENCE.json','SYNTHETIC_QA.json','CHECKPOINT_QA.json','BRIDGE_BRANCH_QA.json','RUNNER_QA.json']}
    assert set(a['code_and_qa_hashes'])==required,'APPROVAL_EXACT_CODE_AND_QA_SCOPE'
    for p,h in a['code_and_qa_hashes'].items():assert m.stream.file_sha(p)==h,('APPROVAL_SOURCE_DRIFT',p)
    review=Path(a['independent_review_path']);assert review.is_relative_to(O.parent/'mainline_winner_funding_review_v1')
    assert m.stream.file_sha(review)==a['independent_review_sha256']
    r=m.read(review);assert r['result']=='PASS_V12_CASH688200_CONTINUATION_INTERFACE' and not r['remaining_blockers']
    assert r['source_manifest_sha256']==a['source_manifest_sha256']
    assert a['original_v1_outputs_preserved'] and a['same_manifest_checkpoint_only'] and a['no_new_strategy_factor']
    return a

def run_once():
    m,cp,prefix,manifest=prepare();a=approved(m)
    assert not (O/'RUN_STARTED.json').exists(),'ONE_SHOT_ALREADY_STARTED'
    assert not (O/'once_20250120').exists() and not (O/'runtime_checkpoint').exists(),'RUN_OUTPUT_ALREADY_EXISTS'
    verifier=prefix.PrefixVerifier(m)
    print('DATA_INITIALIZATION_START',flush=True)
    data=m.Data() # Preserve frozen default end=2026-06-30. Only loop is bounded below.
    run_days=[d for d in data.days if '2024-09-02'<=m.day(d)<='2025-01-20']
    assert len(run_days)==93 and m.day(run_days[0])=='2024-09-02' and m.day(run_days[-1])=='2025-01-20'
    for p,h in a['code_and_qa_hashes'].items():data.hashes[p]=h
    data.hashes[a['independent_review_path']]=a['independent_review_sha256']
    data.hashes[str(O/'EXPERIMENT_APPROVAL.json')]=m.stream.file_sha(O/'EXPERIMENT_APPROVAL.json')
    binding=cp.make_binding(data)
    m.save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,execution_days=93,start='2024-09-02',end='2025-01-20',sealed_loaded_end=m.day(data.cal[-1]),checkpoint_binding=binding,not_PIT=True))
    e=m.Engine(data);assert e.cash==m.D('1200000')
    with (O/'RUN_STARTED.json').open('x') as f:
        json.dump(dict(started_at=str(m.pd.Timestamp.now(tz='UTC')),end='2025-01-20',source_manifest_sha256=a['source_manifest_sha256']),f,indent=2)
    pending=[];blocked=None;runtime_error=None;storage_error=None;prefix_error=None;latest=None
    for d in run_days:
        prev=data.cal[data.cal.get_loc(d)-1]
        try:pending=e.atomic_step(d,pending,prev)
        except m.Blocked as ex:
            blocked=dict(day=m.day(d),reason=str(ex),atomic_rollback=True);e.blockers.append(str(ex));e.uncertified_day=blocked
            try:e.all_blockers=e.scan_restored_targets(d,pending)
            except Exception as scan:e.all_blockers=[dict(scan_error=str(scan))]
            print('ATOMIC_BLOCK '+json.dumps(blocked),flush=True);break
        except Exception as ex:
            runtime_error=dict(day=m.day(d),type=type(ex).__name__,reason=str(ex),traceback=traceback.format_exc(),atomic_rollback=True)
            print('RUNTIME_ERROR '+json.dumps(runtime_error),flush=True);break
        try:verifier.check_day(e,pending,m.day(d))
        except Exception as ex:
            prefix_error=dict(day=m.day(d),reason=str(ex),traceback=traceback.format_exc(),economic_day_completed=True,usable_result=False)
            print('PREFIX_MISMATCH '+json.dumps(prefix_error),flush=True);break
        print('DAY '+m.day(d)+' '+json.dumps(dict(orders=len(e.orders),NAV=e.ledger[-1]['NAV'],stocks=e.ledger[-1]['stocks'],branches=len(e.funding_book['branches']),prefix_days_checked=len(verifier.rows))),flush=True)
        # Do not add e.pending during execution: original state fingerprints omit it.
        try:
            latest=cp.save_latest(e,pending,d,O/'runtime_checkpoint',binding,O/'CHECKPOINT_RECEIPTS.jsonl')
            print('CHECKPOINT '+m.day(d)+' bytes='+str((Path(latest['path'])/'STATE.pickle.gz').stat().st_size),flush=True)
        except Exception as ex:
            storage_error=dict(day=m.day(d),reason=str(ex),traceback=traceback.format_exc(),economic_day_certified=True)
            print('CHECKPOINT_STOP '+json.dumps(storage_error),flush=True);break
    e.pending=pending
    prefix_pass=len(verifier.rows)==22 and prefix_error is None
    m.save(O/'PREFIX_QA.json',dict(result='PASS' if prefix_pass else 'INCOMPLETE_OR_FAILED',days=verifier.rows,error=prefix_error,reference_sha256=m.stream.file_sha(O/'PREFIX_REFERENCE.json'),exact_allowed_difference=verifier.ref['exact_allowed_difference']))
    print('EXPORT_START',flush=True);out=O/'once_20250120';e.export(out)
    source_verified=all(m.stream.file_sha(p)==h for p,h in data.hashes.items())
    status=dict(result='PREFIX_MISMATCH' if prefix_error else 'RUNTIME_ERROR' if runtime_error else 'CHECKPOINT_STOP' if storage_error else 'ATOMIC_BLOCK' if blocked else 'COMPLETED',
                days=len(e.ledger),orders=len(e.orders),last=e.ledger[-1] if e.ledger else None,blockers=e.blockers,atomic_block=blocked,runtime_error=runtime_error,storage_error=storage_error,
                prefix_22_certified=prefix_pass,usable_bounded_result=prefix_pass and prefix_error is None and runtime_error is None and source_verified,
                output=str(out),latest_checkpoint=latest,source_hashes_verified=source_verified,finished_at=str(m.pd.Timestamp.now(tz='UTC')))
    m.save(O/'RUN_STATUS.json',status);print('FINAL '+json.dumps(status,ensure_ascii=False,default=str),flush=True)
    if runtime_error or prefix_error or storage_error:raise SystemExit(2)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],default='check');args=ap.parse_args()
    if args.mode=='run':run_once()
    else:
        m,cp,prefix,manifest=prepare();print(json.dumps(dict(result='STATIC_CHECK_PASS_NO_HISTORY',approval_present=(O/'EXPERIMENT_APPROVAL.json').exists(),source_manifest_sha256=m.stream.file_sha(O/'SOURCE_HASHES.json'))))
if __name__=='__main__':main()
