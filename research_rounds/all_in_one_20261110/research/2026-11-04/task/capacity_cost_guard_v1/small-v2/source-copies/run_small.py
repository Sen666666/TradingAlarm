"""Bounded native small-prefix execution; completed outputs never repeat."""
from pathlib import Path
import argparse, gzip, hashlib, json, sys, time, traceback
import capacity_adapter as C
A,N,J,L,IO = C.A,C.N,C.J,C.L,C.IO
O = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    IO.write_json(p, J.W.canon(value))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--end', default='2022-01-14')
    p.add_argument('--physical', action='store_true')
    p.add_argument('--resume', type=Path)
    args=p.parse_args(); out=args.out.resolve()
    assert str(out).startswith(str(O.resolve())+'/')
    assert not (out/'DONE.json').exists(), 'completed small prefix must not repeat'
    assert not (out/'STARTED.json').exists(), 'existing attempt needs a distinct reviewed output'
    out.mkdir(parents=True, exist_ok=True)
    rootcard=O.parent/'CAPACITY_COST_GUARD_EXPERIMENT_CARD.txt'
    N.configure_scores()
    sources={str(v.resolve()):sha(v) for v in [rootcard,Path(__file__),O/'guard.py',O/'capacity_adapter.py']}
    sources.update(A.source_freeze())
    save(out/'STARTED.json', dict(sources=sources,arms=C.ARMS,window=['2022-01-04',args.end],
                                 scope='NATIVE_SMALL_ACCOUNT_TRACE_ONLY',physical=args.physical,
                                 original_ACT20_BREAK63=True, new_indicators=0))
    # Exact old input loader; redirect its metadata into this new output only.
    original=A.S.O
    try:
        A.S.O=out/'input-readiness'
        value=A.S.inputs('2022')
    finally:
        A.S.O=original
    shared,receipts,cp,states,ir,identity=value
    if args.physical:
        shared,receipts,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,args.end)
    else:
        kw=A.S.kwargs(cp,states,ir)
    J.START='2022-01-01';J.END=args.end
    runner=C.Runner(shared,receipts,**kw)
    runner.source_freeze=dict(sources)
    save(out/'INPUT_IDENTITY.json', identity)
    IO.write_bytes(out/'derived_route.py',C.NEW_ROUTE.encode())
    started=time.monotonic()
    with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
        cursor=runner.restore(args.resume) if args.resume else None
        done=runner.run_prepared(out,360,resume_after=cursor,end=args.end)
    for path,h in sources.items():assert sha(path)==h,('source changed during small trace',path)
    assert done
    save(out/'COST_OBSERVER_FINAL.json', {
        k:dict(alpha=a.capacity_alpha,release=a.capacity_release,basis=a.capacity_basis,entry=a.capacity_entry,
               no_half_applied_callback=not a.capacity_in_callback)
        for k,a in runner.accounts.items() if type(a) is C.GuardAccount})
    save(out/'SMALL_RESULT.json',dict(passed=True,seconds=time.monotonic()-started,
          end=args.end,days=len(runner.daily)//len(runner.accounts),arms={k:dict(NAV=str(a.current_nav),
          trades=len(a.trades),buyfills=a.counts['buy_fills'],sellfills=a.counts['sell_fills']) for k,a in runner.accounts.items()},
          source_post_exact=True,new_signal_models=0))
    print('SMALL_COMPLETE', json.dumps({k:str(a.current_nav) for k,a in runner.accounts.items()}), flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException:
        print(traceback.format_exc(),file=sys.stderr)
        raise
