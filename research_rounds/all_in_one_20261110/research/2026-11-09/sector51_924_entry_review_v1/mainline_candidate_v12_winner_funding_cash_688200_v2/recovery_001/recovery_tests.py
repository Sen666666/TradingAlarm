"""Recovery-only synthetics; no real Data or post-checkpoint history execution."""
from pathlib import Path
from types import SimpleNamespace
import contextlib,copy,hashlib,importlib.util,io,json,os,sys,time
R=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('recovery_under_test',R/'recover.py');r=importlib.util.module_from_spec(sp);sys.modules[sp.name]=r;sp.loader.exec_module(r)
checks=[]
def check(name,v=True):assert v,name;checks.append(name)
def rejects(name,fn):
    try:fn()
    except (AssertionError,FileNotFoundError):check(name)
    else:raise AssertionError(name)
def main():
    out=R/'qa_runs'/str(time.time_ns());out.mkdir(parents=True)
    original=r.module('recovery_test_original_runner',r.O/'run_approved_once.py');m,cp,prefix,_=original.prepare();original.approved(m)
    fn,tail=r.continuation_function(original)
    check('original_runner_tail_exact_single_initialization_removal',tail=='2e73cc4473f0fb117b11a0ec6c0076295b4f785f8beaff2f0ad7a5a138a88b88')
    rejects('recovery_approval_absent',r.recovery_approved)
    ps=' PID TTY STAT TIME COMMAND\n 101 ?? S 0:01 /python -B '+str(r.O/'run_approved_once.py')+' --mode run\n 102 ?? S 0:01 /python -B '+str(R/'recover.py')+' --mode run\n 103 ?? S 0:01 /bin/zsh -lc "python '+str(R/'recover.py')+' --mode run"\n'
    matches=r.process_matches(ps,102)
    check('detect_original_full_command_exclude_self_shell',len(matches)==1 and matches[0]['pid']==101)
    check('detect_competing_recovery',len(r.process_matches(ps,999))==2)
    uv='104 ?? S 0:01 /usr/local/bin/uv run python -B '+str(R/'recover.py')+' --mode run\n'
    check('detect_uv_full_command',r.process_matches(uv,999)[0]['pid']==104)
    check('uv_self_pid_excluded',not r.process_matches(uv,104))
    old=r.R;r.R=out/'mutex';r.R.mkdir()
    try:
        with r.ExclusiveRecovery():rejects('second_recovery_lock_rejected',lambda:r.ExclusiveRecovery().__enter__())
        (r.R/'RECOVERY_STARTED.json').write_text('{}');rejects('duplicate_recovery_start_rejected',r.assert_recovery_not_started)
    finally:r.R=old
    h=r.MANIFEST
    try:r.MANIFEST='0'*64;rejects('wrong_old_source_rejected_before_Data',r.verify_origin)
    finally:r.MANIFEST=h
    h=r.RECEIPT
    try:r.RECEIPT='0'*64;rejects('wrong_origin_receipt_rejected_before_Data',r.verify_origin)
    finally:r.RECEIPT=h
    # Complete native-account continuity with original checkpoint implementation.
    t=m.frozen.module('recovery_native_fixture',m.FROZEN/'synthetic_tests.py')
    x=t.setup(cls=m.Engine);a=t.hold(x,qty=110000);x.cash=m.D(20000);x.d.main_rows[('old',t.dt)]={'M':0,'E':0,'W':True}
    x.d.end=t.CAL[-1];x.d.meta={('old','fixture'):(m.D(1),'immutable')}
    a['cp']=dict(id='recovery_cp',date=m.day(t.dt),floor=m.D(7),origin=t.ORIGIN,consumed=False,invalid=False)
    x.d.events[('old',t.later)]=dict(record_date=m.day(t.nxt),ex_date=m.day(t.later),pay_date=m.day(t.later),factor_old='1',factor_new='1',d_cash='.23',d_source='.23',economic_event_id_candidate='old|SYNTHETIC')
    rows=t.planned(x);pending=x.atomic_step(t.nxt,rows,t.dt)
    check('native_runtime_does_not_add_pending','pending' not in vars(x))
    binding=cp.make_binding(x.d);receipt=cp.save_checkpoint(x,pending,t.nxt,out/'native_state',binding)
    fresh=copy.deepcopy(x.d);fresh.meta={}
    restored,p2,prev=cp.load_checkpoint(out/'native_state',receipt['receipt_sha256'],fresh,m.Engine,binding)
    snapshot=lambda v:m.frozen.digest({k:z for k,z in vars(v).items() if k!='d'})
    check('native_complete_state_restore_exact',snapshot(restored)==snapshot(x))
    check('native_active_archive_CP_alias',restored.active['old'] is restored.archive[a['id']] and restored.active['old']['cp'] is restored.archive[a['id']]['cp'])
    check('native_latest_book_alias',restored.funding_book is restored.funding_books[-1])
    check('native_meta_pending_prev_preserved',restored.d.meta==x.d.meta and m.frozen.digest(p2)==m.frozen.digest(pending) and prev==t.nxt and 'pending' not in vars(restored))
    rejects('wrong_checkpoint_receipt_rejected',lambda:cp.load_checkpoint(out/'native_state','0'*64,fresh,m.Engine,binding))
    changed=copy.deepcopy(fresh);changed.hashes['unexpected']='0'*64
    rejects('wrong_Data_source_binding_rejected',lambda:cp.load_checkpoint(out/'native_state',receipt['receipt_sha256'],changed,m.Engine,binding))
    p1=x.atomic_step(t.later,pending,t.nxt);p2=restored.atomic_step(t.later,p2,prev)
    check('native_continuous_vs_resume_state_exact',snapshot(x)==snapshot(restored))
    for name in ['orders','cash','receivable','claims','tickets','cp_log','events','funding_books']:
        check('native_continuity_'+name,m.frozen.digest(getattr(x,name))==m.frozen.digest(getattr(restored,name)))
    check('native_post_restore_dividend_real_method',any(z['event']=='PAY_CLOSE_NET80' for z in restored.equity))
    # Fake original-tail control flow: start at day17, not day1; finite 77 sessions.
    days=m.pd.bdate_range('2024-09-02','2025-01-20');omit=m.pd.to_datetime(['2024-09-16','2024-09-17','2024-10-01','2024-10-02','2024-10-03','2024-10-04','2024-10-07','2025-01-01']);days=days[~days.isin(omit)]
    data=SimpleNamespace(days=days,cal=m.pd.DatetimeIndex([m.pd.Timestamp('2024-08-30'),*days]),hashes={})
    future=r.continuation_days(data,days[15],16,m.day)
    check('calendar_16_plus_77_no_replay',len(future)==77 and m.day(future[0])=='2024-09-26' and m.day(future[-1])=='2025-01-20')
    rejects('wrong_frontier_count_rejected',lambda:r.continuation_days(data,days[15],15,m.day))
    rejects('wrong_frontier_date_rejected',lambda:r.continuation_days(data,days[14],16,m.day))
    for mode in ['complete','atomic_block','prefix_difference']:
        root=out/mode;root.mkdir();(root/'PREFIX_REFERENCE.json').write_text('{}')
        called=[];saved=[]
        class FakeEngine:
            def __init__(self):self.orders=[];self.ledger=[{'day':m.day(d),'NAV':'1200000','stocks':0} for d in days[:16]];self.blockers=[];self.funding_book={'branches':[]}
            def atomic_step(self,d,pending,previous):
                assert 'pending' not in vars(self)
                if mode=='atomic_block':raise m.Blocked('SYNTHETIC_ATOMIC_BLOCK')
                assert previous==data.cal[data.cal.get_loc(d)-1];called.append(m.day(d));self.ledger.append({'day':m.day(d),'NAV':'1200000','stocks':0});return pending
            def scan_restored_targets(self,*a):return []
            def export(self,p):p.mkdir();(p/'FAKE_ONLY.json').write_text('{}')
        class FakeVerifier:
            def __init__(self):self.rows=[{'day':m.day(d)} for d in days[:16]];self.ref={'exact_allowed_difference':{}}
            def check_day(self,e,p,d):
                if mode=='prefix_difference':raise AssertionError('SYNTHETIC_PREFIX_DIFF')
                if d<='2024-10-10':self.rows.append({'day':d})
        def save_latest(e,p,d,path,b,log):
            saved.append(m.day(d));path.mkdir(exist_ok=True);(path/'STATE.pickle.gz').write_bytes(b'fake');return {'path':str(path)}
        fake=SimpleNamespace(day=m.day,pd=m.pd,Blocked=m.Blocked,save=m.save,stream=m.stream)
        execute,_=r.continuation_function(original);execute.__globals__['O']=root
        with contextlib.redirect_stdout(io.StringIO()):
            try:execute(fake,SimpleNamespace(save_latest=save_latest),data,FakeEngine(),[],future,{},FakeVerifier())
            except SystemExit as ex:assert mode=='prefix_difference' and ex.code==2
        status=r.read(root/'RUN_STATUS.json')
        if mode=='complete':check('unchanged_tail_resumes_77_to_total93',len(called)==77 and status['days']==93 and status['prefix_22_certified'] and called[0]=='2024-09-26' and called[-1]=='2025-01-20')
        elif mode=='atomic_block':check('unchanged_atomic_block_no_advance',not called and not saved and status['days']==16 and status['atomic_block']['atomic_rollback'])
        else:check('prefix_difference_stops_before_checkpoint',len(called)==1 and not saved and status['result']=='PREFIX_MISMATCH' and not status['usable_bounded_result'])
    check('old_START_and_all_sources_preserved',r.sha(r.O/'RUN_STARTED.json')==r.OLD_RUN_STARTED and r.sha(r.O/'SOURCE_HASHES.json')==r.MANIFEST)
    check('new_recovery_not_started',not (R/'RECOVERY_STARTED.json').exists())
    validation=r.read(R/'STATE_VALIDATION.json');state=validation['state']
    check('real_saved16_validation_source_matches_frozen_driver',validation['driver_sha256']==r.sha(R/'recover.py') and validation['same_binding_id']==r.BINDING and not validation['history_advanced'])
    check('real_saved16_prefix_graph_unchanged',state['full_pickle_graph_before']==state['full_pickle_graph_after'] and len(state['prefix_days'])==16 and state['no_pending_attribute'])
    check('recovery_source_absent_from_original_Data_binding',not any(str(R) in p for p in r.read(r.O/'FROZEN_INPUTS.json')['hashes']))
    result=dict(result='PASS',assertions=len(checks),checks=checks,history_advanced=False,real_Data_constructed=False,synthetic_only=True,
                driver_sha256=r.sha(R/'recover.py'),tests_sha256=r.sha(R/'recovery_tests.py'),original_tail_sha256=tail,output_directory=str(out))
    r.save(Path(os.environ.get('QA_RESULT_PATH',R/'SYNTHETIC_QA.json')),result);print(json.dumps(result))
if __name__=='__main__':main()
