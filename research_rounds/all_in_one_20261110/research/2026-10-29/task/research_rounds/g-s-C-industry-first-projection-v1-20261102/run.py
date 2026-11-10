"""Two static snapshots; no execution/account advancement or return labels."""
from c_selector import *
import time, traceback

def main():
    freeze=read(HERE/'AUTHORIZATION_AND_FREEZE.json');guard()
    assert all(sha(HERE/n)==h for n,h in freeze['frozen_code'].items()),'code changed after freeze'
    assert read(HERE/'SYNTHETIC_RESULTS.json')['passed']
    for k in ('2025_26','2022'):
        ip=HERE/'inputs'/(k+'.json');assert sha(ip)==freeze['inputs'][k]
        out=HERE/'results'/k
        if (out/'C.json').exists():raise RuntimeError('completed static result exists; no silent rerun')
        x=read(ip);start=time.monotonic();history=[]
        try:
            def progress(row):
                history.append(row);save(out/'PROGRESS.json',dict(completed=history,seconds=time.monotonic()-start,financial_events=0))
                if row['q'] or len(history)%10==0:print('C_STEP',k,len(history),row['sid'],row['q'],len(row.get('D',{})),round(time.monotonic()-start,2),flush=True)
                if time.monotonic()-start>180:raise RuntimeError('static technical time bound exceeded; no approximate result')
            r=solve_C(x['snapshot'],x['B_demands'],x['industry_evidence'],progress=progress)
            save(out/'C.json',r);save(out/'RUN.json',dict(seconds=time.monotonic()-start,completed=True,financial_events=0,source_input_sha256=sha(ip),source_identity=freeze['frozen_code']))
            print('C_COMPLETE',k,sum(bool(q) for q in r['Q'].values()),len(r['D']),round(time.monotonic()-start,2),flush=True)
        except BaseException as exc:
            save(out/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),completed_prefix=history,financial_events=0));raise

if __name__=='__main__':main()
