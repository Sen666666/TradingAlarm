"""Future invocation only: requires separate full-path authorization JSON.

No authorization file is created by readiness/preflight. Never reruns SC.
"""
from pathlib import Path
import argparse, json, gc, time
import execution_support as S
N,J,L,IO,O=S.N,S.J,S.L,S.IO,S.O

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--windows',choices=['both'],default='both')
    parser.add_argument('--authorization-file',type=Path,required=True)
    parser.add_argument('--seconds-per-window',type=float,default=600)
    args=parser.parse_args()
    assert args.execute,'full financial paths are not authorized by preflight'
    auth=json.loads(args.authorization_file.read_text())
    assert auth['scope']=='full_financial_paths' and auth['policy']=='PVR_SLOT1'
    assert auth['windows']==['2022','2025_26'] and auth['native_rank_sha256']==N.sha(N.__file__)
    assert auth['contract_sha256']==N.sha(O/'CONTRACT.txt')
    gate=json.loads((O/'PREFLIGHT_GATE.json').read_text());assert gate['passed']
    frozen=json.loads((O/'RUN_SOURCE_FREEZE.json').read_text())['sources']
    assert S.freeze()==frozen
    N.configure_scores()
    for window in ['2022','2025_26']:
        root=O/'runs'/window
        assert not (root/'DONE.json').exists(),'completed policy path must never rerun'
        begin=time.monotonic()
        shared,receipts,cp,states,ir,identity=S.initialize(lambda:S.inputs(window),root,'original fixed input load')
        assert S.canonical_identity(identity)==gate['input_identities'][window]
        r=S.initialize(lambda:N.Runner(shared,receipts,**S.kwargs(cp,states,ir)),root,'PVR_SLOT1 empty1m fullwarm construct')
        r.source_freeze=dict(frozen);a=r.accounts['B']
        assert a.available==a.current_nav==a.initial_cash==J.D(1000000) and not a.positions and not a.trades
        # Prefer exact current checkpoint, then the already-completed technical prefix.
        checkpoint=root/'checkpoint.pkl'
        if not checkpoint.exists():checkpoint=root/'prefix-full-source/checkpoint.pkl'
        resumed=None
        if checkpoint.exists():
            with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):resumed=r.restore(checkpoint)
        IO.write_json(root/'FROZEN_RUN_METADATA.json',dict(policy='PVR_SLOT1',window=S.WINDOWS[window][:2],
            initial_cash=1000000,rank_mode='PVR_SLOT1',only_change='frozen PVR-ready unique-stock priority with NA slots preserved',
            authorization_file=str(args.authorization_file),authorization_sha256=N.sha(args.authorization_file),
            sources=frozen,resume_after=str(resumed) if resumed else None,SC_not_rerun=True,
            coupled=True,SD=False,C1=False,R1=False,two_pass=False,cost=1,D1=False))
        with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):
            completed=r.run_prepared(root,args.seconds_per_window,resume_after=resumed,end=S.WINDOWS[window][1])
        assert S.freeze()==frozen
        IO.write_json(root/'TIMING.json',dict(completed=completed,seconds=time.monotonic()-begin))
        print('PVR_SLOT1_PATH_SAVED',window,'completed',completed,'seconds',round(time.monotonic()-begin,2),flush=True)
        if not completed:return
        del r,shared,receipts,cp,states,ir;gc.collect()

if __name__=='__main__':
    try:main()
    except BaseException as e:
        IO.write_json(O/'failure/FULL_ENTRY_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
