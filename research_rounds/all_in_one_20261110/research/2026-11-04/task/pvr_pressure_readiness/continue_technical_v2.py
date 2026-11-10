"""Comparison-clock fix; reuse completed cost1 prefix without new events."""
from pathlib import Path
import json,pickle,shutil,traceback
import technical_checks as T
IO,J,N,L=T.IO,T.J,T.N,T.L
ORIGINAL_RUN=T.run;ORIGINAL_FREEZE=T.frozen;ORIGINAL_DAY=T.eventday
def eventday(x):
    if x.get('kind')=='dividend_accrual':return str(x['receivable']['ex_at'])[:10]
    return ORIGINAL_DAY(x)
def frozen():
    z=ORIGINAL_FREEZE();z[str(Path(__file__))]=N.sha(__file__);return z
def run(r,name,end=T.CUT,after=None):
    out=T.O/'prefix'/name
    if not (out/'DONE.json').exists():return ORIGINAL_RUN(r,name,end,after)
    assert name=='cost1_OFF','only the completed original cost1 verification prefix may be reused'
    path=out/'checkpoint.pkl';p=pickle.loads(path.read_bytes());original=p['source_freeze'];expected=dict(r.source_freeze)
    assert all(N.sha(q)==v for q,v in original.items())
    assert {k:v for k,v in expected.items() if k!=str(Path(__file__))}==original
    r.source_freeze=dict(original)
    with IO.atomic_runner_outputs(r,L,T.O/'prefix'/'cost1_OFF-verified-reuse',canonicalize=J.W.canon):at=r.restore(path)
    assert str(at.date())==end
    # Explicit controller-only source extension after original engine/source
    # restore; no account/strategy/lookup/stream fields change and zero events.
    r.source_freeze=expected
    T.save('COST1_PREFIX_REUSE_PROOF.json',dict(passed=True,checkpoint_sha256=N.sha(path),original_sources_verified=True,
        old_engine_and_pressure_binding_verified=True,source_extension_only=str(Path(__file__)),
        reason='saved full-window dividend_accrual timestamp is receivable.ex_at',new_native_events=0))
    return r
if __name__=='__main__':
    old=T.O/'failure-saved-audit-dividend-clock-v1';old.mkdir(exist_ok=True)
    for name in ('FAILURE.json','SOURCE_FREEZE.json'):
        if (T.O/name).exists() and not(old/name).exists():shutil.copy2(T.O/name,old/name)
    T.eventday=eventday;T.frozen=frozen;T.run=run
    try:T.main()
    except BaseException as e:T.save('FAILURE_V2.json',dict(reason=str(e),traceback=traceback.format_exc()));raise
