"""Exactly two newly authorized C2 static targets; reuse C10 archives."""
from step_cap import *
import shutil,time,traceback

def main():
    guard();assert read(O/'SYNTHETIC_RESULTS.json')['passed']
    if (O/'AUTHORIZATION_AND_FREEZE.json').exists():raise RuntimeError('existing run freeze; inspect before any retry')
    original={}
    for root in (CROOT,C.BASE):
        ix=read(root/'ARTIFACT_SHA256.json');assert all(sha(root/n)==h for n,h in ix.items());original[str(root.resolve())]=dict(index_sha256=sha(root/'ARTIFACT_SHA256.json'),files=len(ix))
    for k in ('2025_26','2022'):
        ip=O/'inputs'/(k+'.json');ip.parent.mkdir(exist_ok=True);shutil.copyfile(CROOT/'inputs'/(k+'.json'),ip)
    freeze=dict(scope='C2 max_q transform + synthesis + only Jan6/Jul3 static projections; no account progression',
        parent='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',amendment_sha256=CONTRACT_SHA,source_C10_sha256=C_SHA,
        source_B_sha256=C.BASE_SHA,source_JF2_sha256=C.JOINT_SHA,
        code={p.name:sha(p) for p in sorted(O.glob('*.py'))},original_archives=original,
        inputs={k:sha(O/'inputs'/(k+'.json')) for k in ('2025_26','2022')},
        C10_results={k:sha(CROOT/'results'/k/'C.json') for k in ('2025_26','2022')},
        financial_events=0,C10_to_recompute=False,no_industry_day_gate=True)
    save(O/'AUTHORIZATION_AND_FREEZE.json',freeze)
    for k in ('2025_26','2022'):
        x=read(O/'inputs'/(k+'.json'));out=O/'results'/k;start=time.monotonic();history=[]
        try:
            def progress(row):
                history.append(row);save(out/'PROGRESS.json',dict(completed=history,seconds=time.monotonic()-start,financial_events=0))
                if row['q'] or len(history)%15==0:print('C2_STEP',k,len(history),row['sid'],row['q'],len(row.get('D',{})),round(time.monotonic()-start,2),flush=True)
                if time.monotonic()-start>180:raise RuntimeError('static technical time budget; no approximate target')
            r=solve_C2(x['snapshot'],x['B_demands'],x['industry_evidence'],progress=progress)
            save(out/'C2.json',r);save(out/'RUN.json',dict(seconds=time.monotonic()-start,completed=True,financial_events=0))
            print('C2_COMPLETE',k,sum(bool(q) for q in r['Q'].values()),len(r['D']),round(time.monotonic()-start,2),flush=True)
        except BaseException as exc:
            save(out/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),completed_prefix=history,financial_events=0));raise

if __name__=='__main__':main()
