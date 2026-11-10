"""Runner control flow on a deliberately fake 93-day account; no real Data/history."""
from pathlib import Path
from types import SimpleNamespace
import contextlib,copy,hashlib,importlib.util,io,json,os,sys,time
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('runner_test_engine',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
r=e.module('runner_under_test',P/'run_approved_once.py');c=e.module('prefix_under_test',P/'prefix_check.py')
checks=[]
def check(n,v=True):assert v,n;checks.append(n)
def rejection(n,fn):
    try:fn()
    except (AssertionError,FileNotFoundError):check(n)
    else:raise AssertionError(n)
def main():
    out=P/'runner_qa_runs'/str(time.time_ns());out.mkdir(parents=True)
    rejection('real_approval_absent_no_Data',lambda:r.approved(e))
    check('runner_import_no_start',not (P/'RUN_STARTED.json').exists())
    # Exact 93 synthetic dates, same boundary condition but no market Data or engine.
    days=e.pd.bdate_range('2024-09-02','2025-01-20')
    omit=e.pd.to_datetime(['2024-09-16','2024-09-17','2024-10-01','2024-10-02','2024-10-03','2024-10-04','2024-10-07','2025-01-01'])
    days=days[~days.isin(omit)];check('fake_calendar_has_93',len(days)==93)
    original=(r.O,r.prepare,r.approved)
    for mode in ['complete','block_after_prefix','prefix_mismatch']:
        root=out/mode;root.mkdir();(root/'review.json').write_text('{}');(root/'EXPERIMENT_APPROVAL.json').write_text('{}');(root/'PREFIX_REFERENCE.json').write_text('{}')
        seen=[]
        class FakeData:
            def __init__(self):
                self.days=days;self.cal=e.pd.DatetimeIndex([e.pd.Timestamp('2024-08-30'),*days]);self.hashes={}
        class FakeEngine:
            def __init__(self,d):self.d=d;self.cash=e.D(1200000);self.ledger=[];self.orders=[];self.blockers=[];self.funding_book={'branches':[]}
            def atomic_step(self,d,pending,prev):
                if mode=='block_after_prefix' and len(self.ledger)==22:raise e.Blocked('SYNTHETIC_ORIGINAL_GUARD')
                seen.append(e.day(d));self.ledger.append(dict(day=e.day(d),NAV='1200000',stocks=0));return pending
            def scan_restored_targets(self,*a):return []
            def export(self,p):p.mkdir();(p/'FAKE_ONLY.json').write_text('{}')
        class FakeVerifier:
            def __init__(self,m):self.rows=[];self.ref={'exact_allowed_difference':{}}
            def check_day(self,x,pending,day):
                if mode=='prefix_mismatch':raise AssertionError('SYNTHETIC_PREFIX_DIFF')
                if day<='2024-10-10':self.rows.append({'day':day})
        def checkpoint(x,pending,d,path,binding,receipt_log):
            path.mkdir(exist_ok=True);(path/'STATE.pickle.gz').write_bytes(b'fake');return {'path':str(path),'certified_day':e.day(d),'receipt_sha256':'fake'}
        fake=SimpleNamespace(Data=FakeData,Engine=FakeEngine,Blocked=e.Blocked,D=e.D,pd=e.pd,day=e.day,save=e.save,stream=e.stream)
        approval=dict(source_manifest_sha256='fake',code_and_qa_hashes={},independent_review_path=str(root/'review.json'),independent_review_sha256=e.stream.file_sha(root/'review.json'))
        r.O=root;r.prepare=lambda:(fake,SimpleNamespace(make_binding=lambda d:{},save_latest=checkpoint),SimpleNamespace(PrefixVerifier=FakeVerifier),{});r.approved=lambda m:approval
        with contextlib.redirect_stdout(io.StringIO()):
            try:r.run_once()
            except SystemExit as ex:assert mode=='prefix_mismatch' and ex.code==2
        status=e.read(root/'RUN_STATUS.json')
        if mode=='complete':check('fake_93_days_exact_horizon',len(seen)==93 and seen[-1]=='2025-01-20' and status['result']=='COMPLETED' and status['prefix_22_certified'])
        elif mode=='block_after_prefix':check('fake_original_atomic_guard_stops',len(seen)==22 and status['result']=='ATOMIC_BLOCK' and status['atomic_block']['atomic_rollback'])
        else:check('fake_prefix_failure_stops_before_checkpoint',len(seen)==1 and status['result']=='PREFIX_MISMATCH' and not status['usable_bounded_result'] and not (root/'runtime_checkpoint').exists())
        rejection('fake_second_launch_blocked_'+mode,r.run_once)
    r.O,r.prepare,r.approved=original
    # Prefix normalization is exactly limited to three checksum fields on one day.
    book={'close_day':'2024-10-10','book_id':'old','scratch_integrity':{'passed':True,'before':'old','after':'old'},'selected_close_index':0,'H':{'lot':{'H':True}},'branches':[]}
    old=c.book_descriptor(book,['full_branch_hash']);changed=copy.deepcopy(book);changed['book_id']='new';changed['scratch_integrity'].update(before='new',after='new')
    check('only_exact_snapshot_digest_difference_allowed',c.book_descriptor(changed,['full_branch_hash'])==old)
    changed['selected_close_index']=1;check('selected_branch_change_detectable',c.digest(c.book_descriptor(changed,['full_branch_hash']))!=c.digest(old))
    check('any_branch_field_change_detectable',c.digest(c.book_descriptor(book,['different_full_hash']))!=c.digest(old))
    changed=copy.deepcopy(book);changed['scratch_integrity']['after']='bad';rejection('scratch_side_effect_rejected',lambda:c.book_descriptor(changed,[]))
    changed=copy.deepcopy(book);changed['close_day']='2024-10-09';check('earlier_book_id_not_excluded','book_id' in c.book_descriptor(changed,[]))
    mixed={'z':[e.D('.230'),{('x',1),('y',2)},e.pd.Timestamp('2024-10-10')],'a':e.frozen.np.bool_(True)}
    original_hash=hashlib.sha256(''.join(e.stream.json_chunks(mixed)).encode()).hexdigest()
    check('per_branch_fast_hash_identical_stream_bytes',c.stream_hash(mixed,e.stream)==original_hash)
    check('equity_daily_family_not_excluded',c.DAILY['EQUITY_EVENTS']=='equity')
    check('order_and_ticket_and_CP_and_qy_families_present',all(k in c.DAILY for k in ['ORDERS','RETRY_TICKETS','CP_EVENTS','FUNDING_OPEN_DECISIONS','FUNDING_ACTUAL_DIAGNOSTICS']))
    check('no_real_run_or_approval_created',not (P/'RUN_STARTED.json').exists() and not (P/'EXPERIMENT_APPROVAL.json').exists())
    result=dict(result='PASS',assertions=len(checks),checks=checks,history_run=False,real_Data_constructed=False,fake_control_flow_only=True,runner_sha256=e.stream.file_sha(P/'run_approved_once.py'),prefix_sha256=e.stream.file_sha(P/'prefix_check.py'),tests_sha256=e.stream.file_sha(P/'runner_tests.py'))
    e.save(Path(os.environ.get('QA_RESULT_PATH',P/'RUNNER_QA.json')),result);print(json.dumps(result))
if __name__=='__main__':main()
