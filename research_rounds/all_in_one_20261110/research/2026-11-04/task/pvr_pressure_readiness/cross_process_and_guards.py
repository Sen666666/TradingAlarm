"""One fresh process: original restart check plus no-event negative restores."""
import copy,traceback
from pathlib import Path
import cross_process_restart as C
T,A,IO,J=C.T,C.A,C.IO,C.J
original=T.construct;checks={}
def construct(mode,shared,receipts,kw,horizon):
    correct=original(mode,shared,receipts,kw,horizon)
    import json
    z=json.loads((T.O/'SOURCE_FREEZE.json').read_text())['sources']
    path=T.O/'prefix'/(mode+'-split/checkpoint.pkl')
    cases=['source']+(['cost'] if mode=='cost2_ON' else ['horizon','D1_mode'])
    for case in cases:
        h=copy.deepcopy(horizon)
        if case=='horizon':h['end']='2099-01-01'
        r=original(mode,shared,receipts,kw,h);r.source_freeze=dict(z)
        if case=='source':r.source_freeze[str(Path(A.__file__))]='deliberate-negative'
        if case=='cost':
            r.pressure_cost=1;r.pressure_binding['cost']=1
            for a in r.accounts.values():a.cost_multiplier=1
        if case=='D1_mode':r.d1_enabled=False;r.composition_binding['D1_enabled']=False
        try:
            with IO.atomic_runner_outputs(r,T.L,T.O/'negative-restores'/(mode+'-'+case),canonicalize=J.W.canon):r.restore(path)
        except (AssertionError,ValueError) as e:checks[mode+':'+case]=str(e)
        else:raise AssertionError('negative restore accepted: '+mode+':'+case)
    return correct
if __name__=='__main__':
    T.construct=construct
    try:
        C.main()
        T.save('NEGATIVE_BINDING_GATE.json',dict(passed=True,checks=checks,new_account_events=0,
            source_sha256=T.N.sha(__file__),full_economic_paths=0))
    except BaseException as e:T.save('CROSS_PROCESS_GUARD_FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc()));raise
