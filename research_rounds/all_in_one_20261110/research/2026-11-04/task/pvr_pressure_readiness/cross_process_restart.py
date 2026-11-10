"""New Python process restores own short pressure checkpoint, one OPEN only."""
import json,time,traceback
import technical_checks as T
A,N,L,IO,J=T.A,T.N,T.L,T.IO,T.J
def main():
    begin=time.monotonic();assert not (T.O/'CROSS_PROCESS_RESTART.json').exists()
    gate=json.loads((T.O/'PREFIX_GATE.json').read_text());assert gate['passed']
    freeze=json.loads((T.O/'SOURCE_FREEZE.json').read_text());z=freeze['sources']
    assert all(N.sha(p)==v for p,v in z.items())
    N.configure_scores();shared,receipts,cp,states,ir,identity=A.read_inputs('2025_26')
    assert A.S.canonical_identity(identity)==freeze['input_identity'];kw=A.S.kwargs(cp,states,ir);h=freeze['binding'];result={}
    for mode in ('cost2_ON','D1_ON'):
        path=T.O/'prefix'/(mode+'-split/checkpoint.pkl');before=N.sha(path)
        r=T.construct(mode,shared,receipts,kw,h);r.source_freeze=dict(z)
        with IO.atomic_runner_outputs(r,L,T.O/'prefix'/(mode+'-cross-process'),canonicalize=J.W.canon):at=r.restore(path)
        assert str(at.date())==T.SPLIT
        T.run(r,mode+'-cross-process',after=at)
        expected=json.loads((T.O/'prefix'/mode/'OBSERVABLE.json').read_text());assert T.observable(r)==expected
        assert N.sha(path)==before
        result[mode]=dict(passed=True,checkpoint_sha256=before,cursor=str(at),all_mutable_native_state_exact=True,
            new_OPEN=1,new_CLOSE=1,total_fills_inherited_and_new=len(r.accounts['B'].trades))
    T.save('CROSS_PROCESS_RESTART.json',dict(passed=True,details=result,seconds=time.monotonic()-begin,full_economic_paths=0))
if __name__=='__main__':
    try:main()
    except BaseException as e:T.save('CROSS_PROCESS_FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc()));raise
