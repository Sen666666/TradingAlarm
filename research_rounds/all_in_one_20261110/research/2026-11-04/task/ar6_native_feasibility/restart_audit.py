"""Independent-process read-only complete-observable checkpoint audit."""
from pathlib import Path
import argparse,json,gzip
import adapter_v2 as A
from bounded_run import restore,norm
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2025_26']);ap.add_argument('--prefixes',action='store_true');a=ap.parse_args();rows=[]
    if a.prefixes:
        for window in ['2022','2025_26']:
            for mode in ['OFF','ON']:
                for branch in ['physical','full']:
                    root=A.HERE/'gates'/window/(mode+'-'+branch);p=root/'FINAL.pkl'
                    r=A.V1.Runner.restore(p);expected=A.read(root/'RESULT.json')['final']
                    A.E.require(norm(r.observable(r.last_completed_event))==expected,'cross-process complete prefix observable changed')
                    rows.append(dict(window=window,on=mode=='ON',branch=branch,checkpoint_sha256=A.sha(p),cursor=str(r.last_completed_event),complete_observable_exact=True))
        A.save(A.HERE/'PREFIX_CROSS_PROCESS_RESTART.json',dict(passed=True,records=rows,account_events=0,created_in_separate_process=True))
    elif a.window:
        root=A.HERE/'runs'/a.window;r=restore(A.read(root/'PROGRESS.json'))
        with gzip.open(root/'FINAL.json.gz','rt',encoding='utf-8') as f:expected=json.load(f)
        A.E.require(norm(r.observable(r.last_completed_event))==expected,'cross-process complete final observable changed')
        A.save(root/'CROSS_PROCESS_RESTART.json',dict(passed=True,checkpoint=A.read(root/'PROGRESS.json'),cursor=str(r.last_completed_event),complete_observable_exact=True,account_events=0,created_in_separate_process=True))
    else:raise ValueError('explicit prefix or terminal window required')
if __name__=='__main__':main()
