"""One explicitly selected native window; no automatic rerun or recovery."""
from pathlib import Path
import argparse, gzip, hashlib, inspect, json, sys, textwrap, time, traceback
import capacity_adapter as C
import capacity_inputs as I
A,N,J,L,IO=C.A,C.N,C.J,C.L,C.IO
O=Path(__file__).resolve().parent
WINDOWS={'long':('2022-01-01','2024-12-31'), 'strong':('2025-07-01','2026-06-30')}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,value):IO.write_json(path,J.W.canon(value))


OLD_LOOP=textwrap.dedent(inspect.getsource(L.PreparedRunner.run_prepared))
needle='if at in cutoffs:self.planning(at)'
assert OLD_LOOP.count(needle)==1
NEW_LOOP=OLD_LOOP.replace(needle,"if at in cutoffs:\n    self.planning(at)\n    IO.write_json(Path(out)/'PROGRESS.json',dict(last_completed_close=str(at),NAV={k:str(a.current_nav) for k,a in self.accounts.items()},elapsed_seconds=time.monotonic()-t))\n    if len(self.daily)//len(self.accounts)%10==0:print('PROGRESS',str(at),{k:str(a.current_nav) for k,a in self.accounts.items()},flush=True)")
env=dict(L.__dict__,IO=IO,save=save)
exec(compile(NEW_LOOP,str(O/'derived_event_loop.py'),'exec'),env)
run_loop=env['run_prepared']


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=WINDOWS,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--end')
    p.add_argument('--physical',action='store_true');p.add_argument('--resume',type=Path)
    p.add_argument('--authorization',type=Path);p.add_argument('--seconds',type=int,default=1800)
    args=p.parse_args();out=args.out.resolve();start,end=WINDOWS[args.window];end=args.end or end
    assert str(out).startswith(str(O.resolve())+'/')
    assert not(out/'STARTED.json').exists(), 'existing attempt cannot silently repeat'
    # Parent explicitly authorizes only the short technical prefix until its
    # separate small/account review has passed.
    full=(args.window=='long' and end>'2022-01-31')or(args.window=='strong' and end>'2025-07-11')
    if full:
        assert args.authorization is not None
        grant=json.loads(args.authorization.read_text())
        assert grant['approved']is True and args.window in grant['windows']
    out.mkdir(parents=True,exist_ok=True)
    I.configure_scores(args.window,out)
    files=[O/'guard.py',O/'capacity_adapter.py',O/'capacity_inputs.py',Path(__file__),O.parent/'CAPACITY_COST_GUARD_EXPERIMENT_CARD.txt']
    sources={str(q.resolve()):sha(q) for q in files};sources.update(A.source_freeze())
    for y in (('2022','2023','2024')if args.window=='long' else ('strong',)):
        path=I.SCORE_PATHS[y];sources[str(path.resolve())]=sha(path)
        if y in I.YEARS:
            path=I.YEARS[y][0];sources[str(path.resolve())]=sha(path)
    if full:
        assert grant['source_freeze']==sources, 'root full grant does not match this source'
    save(out/'STARTED.json',dict(window=args.window,start=start,end=end,arms=C.ARMS,sources=sources,
          full_financial_path=full,physical=args.physical,resume=str(args.resume)if args.resume else None))
    snaps=out/'source-copies';snaps.mkdir()
    for q in files:IO.write_bytes(snaps/q.name,q.read_bytes())
    IO.write_bytes(out/'derived_route.py',C.NEW_ROUTE.encode())
    IO.write_bytes(out/'derived_event_loop.py',NEW_LOOP.encode())
    begun=time.monotonic()
    value=I.load_long(out)if args.window=='long' else I.load_strong(out)
    shared,receipts,cp,states,ir,identity=value
    if args.physical:
        shared,receipts,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,end)
    else:kw=A.S.kwargs(cp,states,ir)
    J.START,J.END=start,end
    runner=C.Runner(shared,receipts,**kw);runner.source_freeze=sources
    save(out/'INPUT_IDENTITY.json',identity)
    loaded=time.monotonic()
    with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
        cursor=runner.restore(args.resume) if args.resume else None
        done=run_loop(runner,out,args.seconds,resume_after=cursor,end=end)
    assert all(sha(k)==v for k,v in sources.items()), 'frozen source changed during execution'
    save(out/'TIMING.json',dict(completed=done,input_seconds=loaded-begun,
          total_seconds=time.monotonic()-begun,event_loop_seconds=getattr(runner,'run_seconds',None)))
    if not done:
        print('CHECKPOINTED_LIMIT_NO_AUTOMATIC_RESUME',flush=True);return
    save(out/'COST_OBSERVER_FINAL.json',{k:dict(alpha=a.capacity_alpha,release=a.capacity_release,
         basis=a.capacity_basis,entry=a.capacity_entry,legacy_ids=a.capacity_legacy_ids)
         for k,a in runner.accounts.items() if type(a)is C.GuardAccount})
    print('WINDOW_COMPLETE',args.window,{k:str(a.current_nav) for k,a in runner.accounts.items()},flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        print(traceback.format_exc(),file=sys.stderr);raise
