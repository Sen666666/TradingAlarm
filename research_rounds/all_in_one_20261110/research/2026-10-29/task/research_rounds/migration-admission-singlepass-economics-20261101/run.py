"""Exactly one SD per approved fixed window. Never replay the SC baseline."""
from pathlib import Path
import sys,json,gzip,time,gc,argparse,importlib.util,hashlib
import runner as R
O=R.O;W=R.W;N=R.N;J=R.J;L=R.L;IO=R.IO
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
sys.path.insert(0,str(W/'migration-admission-native-readiness-20261101'))
from check_identity import observable

def load_year():
    p=W/'2022-normal-reference-20261031/adapter.py';s=importlib.util.spec_from_file_location('SD_original_2022_inputs',p)
    a=importlib.util.module_from_spec(s);sys.modules[s.name]=a;s.loader.exec_module(a);return a

def quick(out):
    with gzip.open(out/'pair/daily.jsonl.gz','rt') as f:ds=[json.loads(x) for x in f]
    with gzip.open(out/'pair/B.json.gz','rt') as f:b=json.load(f)
    D=J.D;peak=D(1000000);dd=D(0)
    for row in ds:peak=max(peak,D(row['nav']));dd=max(dd,1-D(row['nav'])/peak)
    result=dict(ending_NAV=b['ending_NAV'],return_pct=str((D(b['ending_NAV'])/D(1000000)-1)*100),DD_pct=str(dd*100),
                mean_exposure_pct=str(sum((D(x['inventory'])/D(x['nav'])*100 for x in ds),D(0))/len(ds)),
                peak_exposure_pct=str(max(D(x['inventory'])/D(x['nav'])*100 for x in ds)),
                fees=str(sum((D(t['fees_cny']) for t in b['trades']),D(0))),
                buy_fills=sum(t['side']=='buy' for t in b['trades']),sell_fills=sum(t['side']=='sell' for t in b['trades']),
                paused_closes=sum(not x['on'] for x in ds),closes=len(ds))
    IO.write_json(out/'QUICK_RESULT.json',result);print('SD_RESULT',json.dumps(result),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);args=p.parse_args()
    out=O/'runs'/args.window
    assert not (out/'DONE.json').exists(),'completed SD path must not rerun'
    assert L.read(N.O/'NATIVE_GATE.json')['passed'] and L.read(N.O/'IDENTITY_GATE.json')['passed']
    assert L.read(O/'LOGGING_GATE.json')['passed']
    extra=[]
    if args.window=='2022':
        Y=R.initialize(load_year,out,'original_2022_input_module');start='2022-01-01';end='2022-12-30';cut='2022-01-10'
        def inputs():
            old=Y.save
            try:Y.save=lambda path,value:IO.write_json(out/'input-readiness'/Path(path).name,J.W.canon(value));return Y.inputs()
            finally:Y.save=old
        extra=[Path(Y.__file__),W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'2022-normal-reference-20261031/inputs/COMPLETION.json']
    else:start='2025-07-01';end='2026-06-30';cut='2025-07-07';inputs=lambda:E.inputs('universe')
    J.START=start;J.END=end;begin=time.monotonic()
    shared,receipts,cp,states,ir,identity=R.initialize(inputs,out,'read_original_frozen_inputs_only')
    loaded=time.monotonic();print('INPUTS_READY',args.window,round(loaded-begin,3),flush=True)
    freeze=N.source_freeze()
    for path in [Path(__file__),Path(R.__file__),Path(E.__file__),O/'LOGGING_GATE.json',N.O/'CONTRACT.txt',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',L.U/'FREEZE.json',J.M.O/'recovery.csv',J.M.P/'h1.npz']+extra:
        freeze[str(path.resolve())]=L.sha(path)
    IO.write_json(out/'FREEZE.json',dict(before_events=True,window=[start,end],initial_cash=1000000,identity=identity,
        sources=freeze,only_economic_difference='reviewed route/request migration-success dependency removed',
        baseline_not_rerun=True,normal=True,two_pass=False,R1=False,C1=False,new_stage=False))
    kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
    r=R.initialize(lambda:R.Runner(shared,receipts,**kw),out,'SD_fresh1m_fullwarm');r.source_freeze=dict(freeze)
    a=r.accounts['B'];assert a.available==a.current_nav==a.initial_cash==J.D(1000000)
    assert not a.positions and not a.buys and not a.exits and not a.trades and not a.core_epoch and not a.budget.losses
    g=time.monotonic();cut_at=J.M.N.iso(cut+'T15:10:00+08:00')
    # Prefix is the first segment of this SAME SD path; subsequently resumed.
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'prefix-full-source',120,end=cut)
    short=r.run_seconds
    restarted=R.initialize(lambda:R.Runner(shared,receipts,**kw),out,'same_SD_restart');restarted.source_freeze=dict(freeze)
    with IO.atomic_runner_outputs(restarted,L,out,canonicalize=J.W.canon):assert restarted.restore(out/'prefix-full-source/checkpoint.pkl')==cut_at
    assert observable(r)==observable(restarted) and r.sd_route_log==restarted.sd_route_log and r.sd_migration_closes==restarted.sd_migration_closes
    physical=J.W.physical(shared,cut)
    pk=dict(stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
    pr=R.initialize(lambda:R.Runner(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},**pk),out,'SD_physical_prefix');pr.source_freeze=dict(freeze)
    with IO.atomic_runner_outputs(pr,L,out/'prefix-physical-source',canonicalize=J.W.canon):assert pr.run_prepared(out/'prefix-physical-source',120,end=cut)
    assert observable(r)==observable(pr) and r.sd_route_log==pr.sd_route_log and r.sd_migration_closes==pr.sd_migration_closes
    estimate=short*242/len(r.daily)
    IO.write_json(out/'GATES.json',dict(passed=True,physical_prefix_exact=True,both_sides_persisted=True,all_native_restart_equal=True,
                source_checkpoint_identity=True,scope=[start,cut],short_seconds=short,linear_242_closes_estimate_seconds=estimate,
                gate_seconds=time.monotonic()-g,baseline_replayed=False))
    print('GATES_PASS',args.window,'short',round(short,3),'estimated_full',round(estimate,2),flush=True)
    del r,pr;gc.collect();r=restarted;continued=time.monotonic()
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,600,resume_after=cut_at,end=end)
    IO.write_json(out/'TIMING.json',dict(completed=done,input_seconds=loaded-begin,gate_seconds=continued-g,
                continuation_seconds=time.monotonic()-continued,total_seconds=time.monotonic()-begin,first_prefix_continued_not_rerun=True))
    assert all(L.sha(path)==h for path,h in freeze.items()),'frozen source/input drift during SD'
    if not done:print('SAVED_AT_BUDGET',args.window,flush=True);return
    assert len(r.daily)==242 and len(r.balance_audit)==242
    quick(out);print('SD_COMPLETE',args.window,round(time.monotonic()-begin,2),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        IO.write_json(O/'failure/ENTRY_ERROR.json',dict(action='exactly approved SD windows, no baseline replay',type=type(e).__name__,reason=str(e)));raise
