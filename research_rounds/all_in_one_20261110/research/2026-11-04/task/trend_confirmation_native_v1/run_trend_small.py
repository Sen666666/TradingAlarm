"""Only two authorized 9-CLOSE technical windows; no full-history switch."""
from pathlib import Path
import argparse, gzip, json, sys, time, traceback
import trend_size_plugin as T
I,A,N,J,L,IO=T.I,T.A,T.N,T.J,T.L,T.IO
O=Path(__file__).resolve().parent
WINDOWS={'2022':('2022-01-01','2022-01-14'), 'strong':('2025-07-01','2025-07-11')}
def save(p,v):IO.write_json(p,J.W.canon(v))

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=WINDOWS,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve();start,end=WINDOWS[args.window]
    assert str(out).startswith(str(O.resolve())+'/')
    assert not(out/'STARTED.json').exists(), 'never silently repeat a small attempt'
    out.mkdir(parents=True,exist_ok=True)
    N.configure_scores(I.SCORE_PATHS['2022' if args.window=='2022' else 'strong'])
    files=[O/'trend_size_plugin.py',Path(__file__),O/'TECHNICAL_SMALL_CARD.txt',
           T.FEATURE_SOURCE,Path(I.__file__),Path(I.C.__file__),
           O.parent/'trend_confirmation_dedup_v1/FORMULA_AND_ABLATION_CARD.txt',
           O.parent/'trend_confirmation_dedup_v1/FEATURE_COVERAGE_AND_SOURCE_SHA.json',
           I.SCORE_PATHS['2022' if args.window=='2022' else 'strong']]
    frozen={str(x.resolve()):T.sha(x) for x in files};frozen.update(A.source_freeze())
    save(out/'STARTED.json',dict(arms=T.ARMS,window=[start,end],sources=frozen,
          scope='TECHNICAL_NINE_CLOSES_ONLY',cost_guard=False,ACT20_BREAK63_unchanged=True,
          multiplier_on_original_licensed_intent=True,physical_feature_and_market_prefix=True))
    begin=time.monotonic()
    value=I.one_year('2022',out) if args.window=='2022' else I.load_strong(out)
    shared,receipts,cp,states,ir,identity=value
    shared,receipts,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,end)
    J.START,J.END=start,end
    runner=T.Runner(shared,receipts,feature_end=end,**kw);runner.source_freeze=frozen
    save(out/'INPUT_IDENTITY.json',identity)
    for a in runner.accounts.values():
        assert a.current_nav==a.available==a.initial_cash==J.D(1000000)
        assert not a.positions and not a.trades and not a.buys and not a.exits
    loaded=time.monotonic()
    with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
        done=runner.run_prepared(out,360,end=end)
    for path,h in frozen.items():assert T.sha(path)==h,('frozen source changed',path)
    for path,h in runner.feature_cache.sources.items():assert T.sha(path)==h,('feature source changed',path)
    assert done
    save(out/'LAZY_FEATURE_SOURCES.json',dict(source_SHA256=runner.feature_cache.sources,
         loaded_sids=len(runner.feature_cache.values),no_full_universe_export=True,
         feature_max_input_date=end))
    save(out/'SMALL_RESULT.json',dict(passed=True,window=args.window,start=start,end=end,
         days=len(runner.daily)//len(runner.accounts),input_seconds=loaded-begin,
         total_seconds=time.monotonic()-begin,arms={k:dict(NAV=str(a.current_nav),
         buyfills=a.counts['buy_fills'],sellfills=a.counts['sell_fills'],trades=len(a.trades),
         fees_CNY=str(a.balance(runner.daily[-1]['at'],a.market.marks(runner.daily[-1]['at'],a.positions))['fees_cny']))
         for k,a in runner.accounts.items()},source_post_exact=True,no_new_signals=True,
         confirmation_events=len(runner.confirmation_events),cost_guard=False))
    print('TREND_SMALL_COMPLETE',args.window,{k:str(a.current_nav)for k,a in runner.accounts.items()},flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        print(traceback.format_exc(),file=sys.stderr)
        # The invoked output remains a visible failed attempt; no automatic retry.
        if '--out' in sys.argv:
            target=Path(sys.argv[sys.argv.index('--out')+1]);target.mkdir(parents=True,exist_ok=True)
            save(target/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False))
        raise
