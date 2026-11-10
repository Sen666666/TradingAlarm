"""Analysis-only timestamp repair; frozen Apr1 execution controller unchanged.

The successful full-input Apr1 is restored by its existing DONE/checkpoint
branch. Only the as-yet unexecuted physical side is run by the same bounded
controller. No account/planning/opening/route/callback or source guard changes.
"""
from pathlib import Path
import shutil
import first_session as F
A,J,Q,IO=F.A,F.J,F.Q,F.IO
TIME=A.load('shared_native_record_time',A.W/'_shared/native_record_time.py')

def event_day(row):
    return TIME.event_day(row,canonicalize=J.W.canon)

def append_proof(r,parent):
    result={}
    for key in ('daily','opportunities','funding','stage_events','balance_audit','rank_log'):
        old=parent['runner'][key];new=getattr(r,key)
        assert Q.equal(old,new[:len(old)]),('old history overwritten',key)
        appended=new[len(old):]
        assert all(event_day(x)==F.CUT for x in appended)
        result[key]=dict(before=len(old),after=len(new),appended=len(appended),old_prefix_exact=True)
    for key in ('trades','journal','audit_log','decisions','d1_audit'):
        old=parent['accounts']['B'][key];new=getattr(r.accounts['B'],key)
        assert Q.equal(old,new[:len(old)]),('old account history overwritten',key)
        assert all(event_day(x)==F.CUT for x in new[len(old):])
        result['account_'+key]=dict(before=len(old),after=len(new),appended=len(new)-len(old),old_prefix_exact=True)
    assert result['daily']['appended']==1
    return result

def main():
    error=F.ROOT/'failure/ERROR.json';archive=F.ROOT/'analysis-timestamp-errata-v1'
    archive.mkdir(parents=True,exist_ok=True)
    if error.exists() and not (archive/'ERROR.json').exists():shutil.copy2(error,archive/'ERROR.json')
    full=F.ROOT/'full-input/checkpoint.pkl';before=A.sha(full)
    assert (F.ROOT/'full-input/DONE.json').exists(),'this recovery must reuse the completed full-input session'
    # Report helper only. The authorized controller, auth/source freeze,
    # actual native trading methods and its two fixed branch bounds stay exact.
    F.append_proof=append_proof
    F.main()
    assert A.sha(full)==before,'completed full-input checkpoint was rewritten'
    F.save(F.ROOT/'ANALYSIS_TIMESTAMP_ERRATA.json',dict(passed=True,
        bug='first_session.append_proof read only outer at/day; native fill audit has receipt.at',
        fix='analysis-only helper resolves outer at/day then actual FillReceipt.at, unknown fails',
        original_controller_unchanged_sha256=A.sha(F.__file__),
        report_helper_sha256=A.sha(__file__),original_failure=str(archive/'ERROR.json'),
        full_input_checkpoint_SHA_before_and_after=before,
        successful_full_input_session_restored_not_reexecuted=True,
        unchanged_economic_controller_used_for_physical_branch=True,
        no_April2_or_later_events=True))

if __name__=='__main__':
    try:main()
    except BaseException as ex:
        F.save(F.ROOT/'failure/RECOVERY_ERROR.json',dict(type=type(ex).__name__,reason=str(ex),
            scope='analysis recovery plus already-authorized physical Apr1 branch only'));raise
