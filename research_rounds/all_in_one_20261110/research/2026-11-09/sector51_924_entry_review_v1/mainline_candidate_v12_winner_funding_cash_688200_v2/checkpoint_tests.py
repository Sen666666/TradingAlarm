"""Synthetic native continuity and exact-manifest rejection; never real Data/history."""
from pathlib import Path
import copy
import importlib.util
import json
import shutil
import os
import sys
import time
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('checkpoint_test_engine',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
f=e.frozen;D=e.D;pd=e.pd
cp=f.module('checkpoint_storage',P/'checkpoint.py')
t=f.module('checkpoint_synthetic_fixture',e.FROZEN/'synthetic_tests.py')
CHECKS=[]
def check(n,v=True):assert v,n;CHECKS.append(n)
def reject(n,fn):
    try:fn()
    except (AssertionError,FileNotFoundError):check(n)
    else:raise AssertionError(n)
def snap(x):return f.digest({k:v for k,v in vars(x).items() if k!='d'})
def main():
    out=P/'checkpoint_qa_runs'/str(time.time_ns());out.mkdir(parents=True)
    x=t.setup(cls=e.Engine);a=t.hold(x,qty=110000);x.cash=D(20000)
    x.d.main_rows[('old',t.dt)]={'M':0,'E':0,'W':True}
    x.d.end=t.CAL[-1];x.d.meta={('old','fixture_cache'):('immutable_value',D(1))}
    a['cp']=dict(id='cp_for_alias',date=e.day(t.dt),floor=D(7),origin=t.ORIGIN,consumed=False,invalid=False)
    x.d.events[('old',t.later)]=dict(record_date=e.day(t.nxt),ex_date=e.day(t.later),pay_date=e.day(t.later),factor_old='1',factor_new='1',d_cash='.23',d_source='.23',economic_event_id_candidate='old|SYNTHETIC_CASH')
    rows=t.planned(x)
    pending=x.atomic_step(t.nxt,rows,t.dt)
    x.pending=pending
    check('native_first_certified_synthetic_day',x.ledger[-1]['day']==e.day(t.nxt))
    check('ticket_and_CP_fixture_present',bool(x.tickets) and x.active['old']['cp'] is x.archive[a['id']]['cp'])
    binding=cp.make_binding(x.d);before=snap(x)
    receipt=cp.save_checkpoint(x,pending,t.nxt,out/'certified',binding)
    check('save_no_account_mutation',snap(x)==before)
    data2=copy.deepcopy(x.d);data2.meta={}
    resumed,p2,prev=cp.load_checkpoint(out/'certified',receipt['receipt_sha256'],data2,e.Engine,binding)
    check('full_state_exact_after_restore',snap(resumed)==snap(x))
    check('pending_engine_alias_retained',resumed.pending is p2)
    check('active_archive_CP_alias_retained',all(resumed.archive[a['id']] is a for a in resumed.active.values()) and resumed.active['old']['cp'] is resumed.archive[x.active['old']['id']]['cp'])
    check('all_runtime_cache_preserved',resumed.d.meta==x.d.meta)
    check('prev_certified_day_preserved',prev==t.nxt)
    p1=x.atomic_step(t.later,pending,t.nxt);p2=resumed.atomic_step(t.later,p2,prev)
    check('native_continuous_vs_resumed_complete_state',snap(x)==snap(resumed))
    check('native_continuous_vs_resumed_pending',f.digest(p1)==f.digest(p2))
    for k in ['cash','receivable','claims','tickets','cp_log','orders','equity','funding_books','funding_waits','events']:
        check('resume_equal_'+k,f.digest(getattr(x,k))==f.digest(getattr(resumed,k)))
    check('actual_synthetic_dividend_was_paid',any(r['event']=='PAY_CLOSE_NET80' for r in resumed.equity))
    bounded=out/'bounded_cache'
    r1=cp.save_latest(x,p1,t.later,bounded,binding,out/'CHECKPOINT_RECEIPTS.jsonl')
    # A second complete native synthetic day replaces only this cache's old body.
    p3=x.atomic_step(t.CAL[10],p1,t.later)
    r2=cp.save_latest(x,p3,t.CAL[10],bounded,binding,out/'CHECKPOINT_RECEIPTS.jsonl')
    check('bounded_cache_only_latest_body',len(list(bounded.glob('state_*')))==1 and not Path(r1['path']).exists() and Path(r2['path']).exists())
    check('bounded_pointer_authenticates_latest',cp.sha(bounded/'LATEST.json')==r2['latest_pointer_sha256'])
    fresh=copy.deepcopy(x.d);fresh.meta={}
    latest,pending_latest,prev_latest=cp.load_checkpoint(r2['path'],r2['receipt_sha256'],fresh,e.Engine,binding)
    check('bounded_latest_restore_exact',snap(latest)==snap(x) and f.digest(pending_latest)==f.digest(p3) and prev_latest==t.CAL[10])
    pointer_before=cp.sha(bounded/'LATEST.json');log_before=cp.sha(out/'CHECKPOINT_RECEIPTS.jsonl')
    old_certified_state=snap(x);p4=x.atomic_step(t.CAL[11],p3,t.CAL[10]);append=cp.append_receipt
    def injected_failure(*a,**kw):raise OSError('SYNTHETIC_RECEIPT_FSYNC_FAILURE')
    try:
        cp.append_receipt=injected_failure
        try:cp.save_latest(x,p4,t.CAL[11],bounded,binding,out/'CHECKPOINT_RECEIPTS.jsonl')
        except OSError:check('receipt_failure_injected')
        else:raise AssertionError('FAILURE_NOT_TRIGGERED')
    finally:cp.append_receipt=append
    check('receipt_failure_keeps_previous_pointer_body',cp.sha(bounded/'LATEST.json')==pointer_before and Path(r2['path']).exists())
    check('receipt_failure_preserves_trust_anchor',cp.sha(out/'CHECKPOINT_RECEIPTS.jsonl')==log_before)
    old_again,_,_=cp.load_checkpoint(r2['path'],r2['receipt_sha256'],copy.deepcopy(x.d),e.Engine,binding)
    check('receipt_failure_previous_certified_state_restorable',snap(old_again)==old_certified_state)
    original=cp.sha(out/'certified/STATE.pickle.gz')
    reject('reject_receipt_wrong_hash',lambda:cp.load_checkpoint(out/'certified','0'*64,data2,e.Engine,binding))
    wrong=copy.deepcopy(binding);wrong['data_identity']['source_hashes']['unexpected']='0'*64;wrong['binding_id']=cp.digest({k:v for k,v in wrong.items() if k!='binding_id'})
    reject('reject_different_manifest',lambda:cp.load_checkpoint(out/'certified',receipt['receipt_sha256'],data2,e.Engine,wrong))
    changed=copy.deepcopy(data2);changed.events[('new',t.later)]={'ex_date':e.day(t.later)}
    reject('reject_event_migration',lambda:cp.load_checkpoint(out/'certified',receipt['receipt_sha256'],changed,e.Engine,binding))
    changed=copy.deepcopy(data2);changed.hashes['unexpected']='0'*64
    reject('reject_source_addition',lambda:cp.load_checkpoint(out/'certified',receipt['receipt_sha256'],changed,e.Engine,binding))
    reject('reject_different_Engine_class',lambda:cp.load_checkpoint(out/'certified',receipt['receipt_sha256'],data2,f.Engine,binding))
    reject('reject_uncertified_requested_day',lambda:cp.save_checkpoint(x,p1,t.nxt,out/'bad_date',binding))
    broken=copy.deepcopy(x);broken.d=x.d;broken.blockers=['SYNTHETIC_FAILURE']
    reject('reject_failed_day',lambda:cp.save_checkpoint(broken,p4,t.CAL[11],out/'blocked',binding))
    broken=copy.deepcopy(x);broken.d=x.d;broken.uncertified_day={'day':e.day(t.CAL[10])}
    reject('reject_uncertified_marker',lambda:cp.save_checkpoint(broken,p4,t.CAL[11],out/'uncertified',binding))
    reject('reject_incomplete_checkpoint',lambda:cp.load_checkpoint(out/'incomplete','0'*64,data2,e.Engine,binding))
    tampered=out/'tampered';shutil.copytree(out/'certified',tampered)
    with (tampered/'STATE.pickle.gz').open('ab') as output:output.write(b'tampered')
    called=[];loader=cp.pickle.load
    def forbidden_load(*a,**kw):called.append(True);raise AssertionError('UNPICKLE_CALLED')
    try:
        cp.pickle.load=forbidden_load
        reject('reject_payload_tamper',lambda:cp.load_checkpoint(tampered,receipt['receipt_sha256'],data2,e.Engine,binding))
    finally:cp.pickle.load=loader
    check('tamper_rejected_before_unpickle',not called)
    check('failure_tests_did_not_change_good_checkpoint',cp.sha(out/'certified/STATE.pickle.gz')==original)
    result=dict(result='PASS',assertions=len(CHECKS),checks=CHECKS,history_run=False,real_Data_constructed=False,output_directory=str(out),receipt=receipt,checkpoint_sha256=cp.sha(P/'checkpoint.py'),tests_sha256=cp.sha(P/'checkpoint_tests.py'))
    e.save(Path(os.environ.get('QA_RESULT_PATH',P/'CHECKPOINT_QA.json')),result);print(json.dumps(result))
if __name__=='__main__':main()
