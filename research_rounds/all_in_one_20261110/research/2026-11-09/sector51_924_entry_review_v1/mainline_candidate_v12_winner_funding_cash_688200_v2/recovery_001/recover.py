"""Recover the SAME interrupted v2 account; validation never advances a session.

Old Data/economics/checkpoint/prefix/runner are imported without modifying sources.
--run requires separately sealed recovery approval and acquires an exclusive lock.
"""
from pathlib import Path
import argparse,copy,datetime,fcntl,hashlib,importlib.util,inspect,json,os,pickle,shutil,shlex,subprocess,sys,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
O=R.parent
ROOT=O.parent
ORIGIN=O/'runtime_checkpoint/state_20240925'
RECEIPT='1defa15d1bb38c6b05878fb770c8b127f16213207f996fe34ac459536351ea16'
STATE='1274a577f61286c1a56103ed6028cddedfcda640bd496858e8c3bb24b2e46a1e'
BINDING='f7107d9505b335a6bafb9d91cb1237c1b5e86462bc8c25e576b739441a0bc356'
MANIFEST='067f29b7900e13f1925a5e3dafdad914d328079ea8ce39d4ea8f987fa9e1e9d9'
APPROVAL='9590f559c39ea0e2c2fe5a16e8144009e9ea800264691f9b08bf03fe2b34ce21'
OLD_RUN_STARTED='43e5fe56a5847c87a4b60839753df76bc70ba06672cacdf0ff898b59d71ce5f9'
FROZEN_INPUTS='ffde857719d1de60c0d7c91f30c4020a7d0dcf458d37ad3ad10e3ad9409c03ed'
RECEIPT_LOG='805763263ad49bdca58567bc0e4e90b4b633e67234e0e294e94e4fc837903e2a'
LATEST='601ec171220cfa0a1e69774bc43510d820c1dba7288aec3f3c4b44ffa17684ae'
RUNNER='7938e513383f786c9c9becd943852d7556869c1cc7aa3a7536a1a1bed62df218'
INTERFACE='bc54dbaaee7f81e2004b909c46be4971dd02d2e2a6a4f11a63e9ce5a01a130f7'


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v,exclusive=False):
    with Path(p).open('x' if exclusive else 'w') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n');f.flush();os.fsync(f.fileno())
def module(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m

def process_matches(output,current_pid):
    matches=[]
    for line in output.splitlines():
        parts=line.split(None,4)
        if len(parts)<5 or not parts[0].isdigit():continue
        pid=int(parts[0]);command=parts[4]
        if pid==current_pid:continue
        try:args=shlex.split(command)
        except ValueError:
            if O.name in command and ('.py' in command):raise AssertionError('PROCESS_COMMAND_PARSE_UNCERTAIN')
            continue
        if not args:continue
        executable=Path(args[0]).name.lower()
        if not (executable.startswith('python') or executable in ('uv','pypy','pypy3')):continue
        for arg in args[1:]:
            name=Path(arg).name
            target=(name=='run_approved_once.py' and (O.name in arg or arg=='run_approved_once.py')) or (name=='recover.py' and (O.name in arg or 'recovery_' in arg or arg=='recover.py'))
            if target:matches.append(dict(pid=pid,command=command));break
    return matches

def check_no_running_account():
    result=subprocess.run(['/bin/ps','-axww'],capture_output=True,text=True,check=False)
    assert result.returncode==0,('PROCESS_CHECK_FAILED',result.returncode,result.stderr)
    matches=process_matches(result.stdout,os.getpid())
    assert not matches,('ACCOUNT_PROCESS_ALREADY_RUNNING',matches)
    return dict(command='/bin/ps -axww',returncode=0,current_pid=os.getpid(),matching_processes=[],original_account_process_absent=True)

class ExclusiveRecovery:
    def __enter__(self):
        self.file=(R/'RECOVERY_PROCESS.lock').open('a+')
        try:fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.file.close();raise AssertionError('RECOVERY_PROCESS_LOCK_HELD')
        self.file.seek(0);self.file.truncate();self.file.write(json.dumps(dict(pid=os.getpid(),started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=sys.argv))+'\n');self.file.flush();os.fsync(self.file.fileno());return self
    def __exit__(self,*args):fcntl.flock(self.file.fileno(),fcntl.LOCK_UN);self.file.close()

def assert_recovery_not_started():
    assert not (R/'RECOVERY_STARTED.json').exists(),'RECOVERY_ONE_SHOT_ALREADY_STARTED'
    assert not (O/'RUN_STATUS.json').exists() and not (O/'once_20250120').exists(),'ORIGINAL_ACCOUNT_ALREADY_HAS_RESULT'

def verify_origin():
    assert_recovery_not_started()
    paths={O/'SOURCE_HASHES.json':MANIFEST,O/'EXPERIMENT_APPROVAL.json':APPROVAL,O/'RUN_STARTED.json':OLD_RUN_STARTED,
           O/'FROZEN_INPUTS.json':FROZEN_INPUTS,O/'CHECKPOINT_RECEIPTS.jsonl':RECEIPT_LOG,O/'runtime_checkpoint/LATEST.json':LATEST,
           ORIGIN/'COMMIT.json':RECEIPT,ORIGIN/'STATE.pickle.gz':STATE,O/'run_approved_once.py':RUNNER,
           ROOT/'mainline_winner_funding_review_v1/V12_CASH688200_INTERFACE_QA.json':INTERFACE}
    for p,h in paths.items():assert sha(p)==h,('RECOVERY_ORIGIN_DRIFT',str(p))
    external=[json.loads(line) for line in (O/'CHECKPOINT_RECEIPTS.jsonl').read_text().splitlines() if line.strip()]
    latest=read(O/'runtime_checkpoint/LATEST.json')
    assert len(external)==16 and external[-1]==latest and latest['path']==str(ORIGIN)
    assert latest['receipt_sha256']==RECEIPT and latest['state_sha256']==STATE and latest['binding_id']==BINDING and latest['certified_day']=='2024-09-25'
    receipt=read(ORIGIN/'COMMIT.json');binding=receipt['binding']
    assert receipt['status']=='CERTIFIED_COMMITTED' and receipt['state_sha256']==STATE and receipt['certified_day']=='2024-09-25'
    assert binding['binding_id']==BINDING and binding==read(O/'FROZEN_INPUTS.json')['checkpoint_binding']
    assert {p.name for p in (O/'runtime_checkpoint').iterdir()}=={'LATEST.json','state_20240925'},'UNCERTAIN_CHECKPOINT_LEFTOVERS'
    return receipt,{str(p):h for p,h in paths.items()}

def archive_origin():
    archive=R/'origin_checkpoint';archive.mkdir(exist_ok=True)
    files={'COMMIT.json':(ORIGIN/'COMMIT.json',RECEIPT),'STATE.pickle.gz':(ORIGIN/'STATE.pickle.gz',STATE),
           'CHECKPOINT_RECEIPTS.jsonl':(O/'CHECKPOINT_RECEIPTS.jsonl',RECEIPT_LOG),'LATEST.json':(O/'runtime_checkpoint/LATEST.json',LATEST)}
    for name,(source,expected) in files.items():
        target=archive/name
        if not target.exists():
            with source.open('rb') as inp,target.open('xb') as out:
                shutil.copyfileobj(inp,out,1024*1024);out.flush();os.fsync(out.fileno())
        assert sha(target)==expected,('RECOVERY_ARCHIVE_DRIFT',name)
    fd=os.open(archive,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return archive

def continuation_days(data,last_day,count,day):
    days=[d for d in data.days if '2024-09-02'<=day(d)<='2025-01-20']
    assert len(days)==93 and count==16 and day(last_day)=='2024-09-25'
    assert days[count-1]==last_day and day(days[count])=='2024-09-26'
    remaining=days[count:];assert len(remaining)==77 and day(remaining[-1])=='2025-01-20'
    return remaining

def graph_digest(engine,pending,prev):
    class Sink:
        def __init__(self):self.h=hashlib.sha256();self.size=0
        def write(self,b):self.h.update(b);self.size+=len(b);return len(b)
    sink=Sink();pickle.dump(dict(engine_state={k:v for k,v in vars(engine).items() if k!='d'},pending=pending,prev=prev,data_cache={'meta':engine.d.meta}),sink,protocol=5)
    return dict(sha256=sink.h.hexdigest(),bytes=sink.size)

def verify_saved_prefix(engine,pending,prev,m,verifier):
    assert 'pending' not in vars(engine),'RESTORE_MUST_NOT_ADD_PENDING_ATTRIBUTE'
    assert len(engine.ledger)==16 and len(engine.orders)==395 and m.day(prev)=='2024-09-25'
    assert engine.ledger[-1]['NAV']=='1237652.3522767729405' and engine.ledger[-1]['stocks']==81
    assert len(engine.funding_books)==16 and engine.funding_book is engine.funding_books[-1]
    assert all(engine.archive[a['id']] is a for a in engine.active.values()),'ACTIVE_ARCHIVE_ALIAS_LOST'
    assert not engine.blockers and not getattr(engine,'uncertified_day',None)
    before=graph_digest(engine,pending,prev)
    books={b['close_day']:b for b in engine.funding_books}
    assert len(books)==16 and set(books)=={r['day'] for r in engine.ledger}
    for row in engine.ledger:
        view=copy.copy(engine);view.funding_book=books[row['day']]
        verifier.check_day(view,pending,row['day'])
    after=graph_digest(engine,pending,prev)
    assert before==after,'RECOVERY_PREFIX_VERIFICATION_MUTATED_STATE'
    assert len(verifier.rows)==16
    return dict(result='PASS',certified_days=16,orders=395,last=engine.ledger[-1],active_archive_aliases=True,
                latest_book_alias=True,no_pending_attribute=True,full_pickle_graph_before=before,full_pickle_graph_after=after,
                graph_digest_scope='In-process read-only comparison; trusted raw checkpoint SHA binds full serialized state across processes.',
                complete_state_fields=sorted(k for k in vars(engine) if k!='d'),data_cache_entries=len(engine.d.meta),prefix_days=verifier.rows)

def prepare_saved_account():
    process_before=check_no_running_account();receipt,origins=verify_origin();archive=archive_origin()
    original=module('recovery_original_runner',O/'run_approved_once.py')
    m,cp,prefix,manifest=original.prepare();a=original.approved(m)
    print('RECOVERY_DATA_INITIALIZATION_START_NO_HISTORY',flush=True)
    data=m.Data()
    for p,h in a['code_and_qa_hashes'].items():data.hashes[p]=h
    data.hashes[a['independent_review_path']]=a['independent_review_sha256']
    data.hashes[str(O/'EXPERIMENT_APPROVAL.json')]=sha(O/'EXPERIMENT_APPROVAL.json')
    binding=cp.make_binding(data)
    assert binding==receipt['binding'] and binding['binding_id']==BINDING,'RECOVERY_SAME_MANIFEST_REQUIRED'
    assert data.hashes==read(O/'FROZEN_INPUTS.json')['hashes'] and not any(str(R) in p for p in data.hashes),'RECOVERY_DRIVER_NOT_IN_OLD_BINDING'
    engine,pending,prev=cp.load_checkpoint(archive,RECEIPT,data,m.Engine,binding)
    verifier=prefix.PrefixVerifier(m)
    audit=verify_saved_prefix(engine,pending,prev,m,verifier)
    remaining=continuation_days(data,prev,len(engine.ledger),m.day)
    process_after=check_no_running_account();verify_origin()
    report=dict(result='PASS_SAME_ACCOUNT_RECOVERY_STATE_VALIDATION',history_advanced=False,real_Data_constructed=True,
                next_day=m.day(remaining[0]),remaining_days=len(remaining),final_day=m.day(remaining[-1]),same_binding_id=BINDING,
                origin_hashes=origins,immutable_origin_copy=str(archive),archive_state_sha256=sha(archive/'STATE.pickle.gz'),process_before=process_before,process_after=process_after,state=audit,
                driver_sha256=sha(R/'recover.py'),old_run_started_preserved=sha(O/'RUN_STARTED.json')==OLD_RUN_STARTED)
    return original,m,cp,data,engine,pending,remaining,binding,verifier,report

def continuation_function(original):
    source=inspect.getsource(original.run_once)
    start='    pending=[];blocked=None;runtime_error=None;storage_error=None;prefix_error=None;latest=None\n'
    assert source.count(start)==1
    tail=source[source.index(start):]
    adjusted=tail.replace('    pending=[];','    ',1)
    assert adjusted.replace('    blocked=None;','    pending=[];blocked=None;',1)==tail
    ns=dict(Path=Path,json=json,traceback=traceback,O=O)
    exec(compile('def continue_saved(m,cp,data,e,pending,run_days,binding,verifier):\n'+adjusted,'RECOVERY_IDENTICAL_ORIGINAL_ATOMIC_PREFIX_CHECKPOINT_EXPORT_TAIL','exec'),ns)
    return ns['continue_saved'],hashlib.sha256(tail.encode()).hexdigest()

def recovery_approved():
    a=read(R/'RECOVERY_APPROVAL.json')
    assert a['approved'] is True and a['same_account'] is True and a['restart_experiment'] is False
    assert a['source_manifest_sha256']==MANIFEST and a['experiment_approval_sha256']==APPROVAL and a['origin_receipt_sha256']==RECEIPT and a['origin_state_sha256']==STATE and a['binding_id']==BINDING
    assert (a['certified_day'],a['next_day'],a['remaining_days'],a['end'])==('2024-09-25','2024-09-26',77,'2025-01-20')
    required={str(R/n) for n in ['recover.py','recovery_tests.py','CONTRACT.md','SYNTHETIC_QA.json','STATE_VALIDATION.json','origin_checkpoint/COMMIT.json','origin_checkpoint/STATE.pickle.gz']}
    assert set(a['recovery_hashes'])==required
    for p,h in a['recovery_hashes'].items():assert sha(p)==h,('RECOVERY_APPROVAL_DRIFT',p)
    review=Path(a['independent_review_path']);assert review.is_relative_to(ROOT/'mainline_winner_funding_review_v1') and sha(review)==a['independent_review_sha256']
    qa=read(review);assert qa['result']=='PASS_V12_RECOVERY_001_SAME_ACCOUNT' and not qa['remaining_blockers'] and qa['driver_sha256']==sha(R/'recover.py')
    assert read(R/'SYNTHETIC_QA.json')['result']=='PASS' and read(R/'STATE_VALIDATION.json')['result']=='PASS_SAME_ACCOUNT_RECOVERY_STATE_VALIDATION'
    return a

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','validate','run'],default='check');args=ap.parse_args()
    with ExclusiveRecovery():
        if args.mode=='check':
            check_no_running_account();verify_origin();original=module('recovery_original_runner_check',O/'run_approved_once.py');m,_,_,_=original.prepare();original.approved(m)
            _,tail_hash=continuation_function(original);print(json.dumps(dict(result='PASS_STATIC_NO_DATA_NO_HISTORY',tail_sha256=tail_hash)));return
        if args.mode=='run':recovery_approved()
        original,m,cp,data,engine,pending,remaining,binding,verifier,report=prepare_saved_account()
        if args.mode=='validate':save(R/'STATE_VALIDATION.json',report);print(json.dumps(report,ensure_ascii=False));return
        recovery_approved();assert_recovery_not_started();process=check_no_running_account()
        continuation,tail_hash=continuation_function(original)
        save(R/'PRESTART_STATE_VALIDATION.json',report,exclusive=True)
        save(R/'RECOVERY_STARTED.json',dict(pid=os.getpid(),started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=sys.argv,same_account=True,restart_experiment=False,origin_receipt_sha256=RECEIPT,origin_state_sha256=STATE,
             binding_id=BINDING,driver_sha256=sha(R/'recover.py'),recovery_approval_sha256=sha(R/'RECOVERY_APPROVAL.json'),certified_day='2024-09-25',
             first_resumed_day='2024-09-26',remaining_days=77,process_check=process,original_loop_tail_sha256=tail_hash),exclusive=True)
        print('RECOVERY_START '+json.dumps(dict(pid=os.getpid(),next_day='2024-09-26',remaining_days=77,origin_receipt_sha256=RECEIPT)),flush=True)
        try:continuation(m,cp,data,engine,pending,remaining,binding,verifier)
        finally:
            save(R/'RECOVERY_END.json',dict(original_run_started_unchanged=sha(O/'RUN_STARTED.json')==OLD_RUN_STARTED,
                  original_status=read(O/'RUN_STATUS.json') if (O/'RUN_STATUS.json').exists() else None,recovery_provenance_only=True))
if __name__=='__main__':main()
