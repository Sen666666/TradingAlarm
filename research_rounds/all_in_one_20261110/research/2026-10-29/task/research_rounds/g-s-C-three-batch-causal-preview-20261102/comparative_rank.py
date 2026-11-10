"""Fixed rank-position local diagnostic, no native account/event API."""
from pathlib import Path
import sys, copy, time, traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run as R
M=R.M; B=R.B; J=R.J

def main():
    started=time.perf_counter(); M.guard(); out=[]
    for day in R.DATES:
        label='C10-'+day
        a=M.read(HERE/('BASELINE-'+label+'.json'))
        s=a['transformed_snapshot']; ds=a['sorted_complete_demands']
        keys=a['rank_binding']['stock_priority']
        case={d['sid'] for d in ds if (d['sid']=='688425.SH' if day=='2025-07-29' else d['sector']=='URFI881268')}
        assert case
        ss=copy.deepcopy(s); dd=copy.deepcopy(ds)
        for z in ss['lots']:
            if z['sid'] in keys:z['rank_key']=[0 if z['sid'] in case else 1,*z['rank_key']]
        for d in dd:d['priority']=[0 if d['sid'] in case else 1,*d['priority']]
        rs=copy.deepcopy(ss); rd=copy.deepcopy(dd)
        for z in rs['lots']:
            if z['sid'] in keys:z['rank_key']=z['rank_key'][1:]
        for d in rd:d['priority']=d['priority'][1:]
        assert J.digest(rs)==J.digest(s) and J.digest(rd)==J.digest(ds)
        before=J.digest((s,ds)); t=time.perf_counter()
        result=B.solve_B(ss,dd)
        assert result['validation']['ok'] and before==J.digest((s,ds))
        orig=a['result']; changes=[dict(sid=sid,before=orig['Q'][sid],after=result['Q'][sid]) for sid in orig['Q'] if orig['Q'][sid]!=result['Q'][sid]]
        donors=sorted(set(orig['D'])|set(result['D']))
        dc=[dict(sid=sid,before=orig['D'].get(sid,0),after=result['D'].get(sid,0)) for sid in donors if orig['D'].get(sid,0)!=result['D'].get(sid,0)]
        item=dict(day=day,mode='C10',targets=sorted(case),contract_sha256=R.sha(HERE/'CONTRACT.txt'),addendum_sha256=R.sha(HERE/'ADDENDUM_QUEUE_VS_COMPARATIVE_RANK.txt'),
            source_sha256=R.sha(__file__),original_input_sha256=J.digest((s,ds)),rank_only_recovery_exact=True,
            original_full_order=[d['sid'] for d in ds],diagnostic_full_order=[d['sid'] for d in sorted(dd,key=lambda d:(d['priority'],d['sid']))],
            original_positive_Q={sid:q for sid,q in orig['Q'].items() if q},all_Q_changes=changes,all_D_changes=dc,
            original_D=orig['D'],result=result,seconds=time.perf_counter()-t,financial_events=0,analysis_only=True,submit_allowed=False)
        R.save('COMPARATIVE_RANK-'+label+'.json',item)
        out.append({k:item[k] for k in ('day','targets','all_Q_changes','all_D_changes','seconds','rank_only_recovery_exact')})
        print('COMPARATIVE_DONE',day,'Qchanges',len(changes),'Dchanges',len(dc),'seconds',round(item['seconds'],3),flush=True)
    R.save('COMPARATIVE_SUMMARY.json',dict(rows=out,seconds=time.perf_counter()-started,financial_events=0,analysis_only=True,submit_allowed=False))

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        R.save('COMPARATIVE_ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),financial_events=0)); raise
