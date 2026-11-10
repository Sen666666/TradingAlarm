"""Frozen full-window preparation; bounded technical/restart or explicit full grant."""
from pathlib import Path
import argparse, json, time, traceback, sys
import trend_size_plugin as T
I,A,N,J,L,IO=T.I,T.A,T.N,T.J,T.L,T.IO
O=Path(__file__).resolve().parent
WINDOWS={'long':('2022-01-01','2024-12-31','2022-01-14'),
         'strong':('2025-07-01','2026-06-30','2025-07-11')}
def save(p,v):IO.write_json(p,J.W.canon(v))
def read(p):return json.loads(Path(p).read_text())
def source_manifest(window):
    start,end,technical_end=WINDOWS[window]
    files=[O/'trend_size_plugin.py',Path(__file__),O/'frozen_capacity_inputs.py',
           O/'FROZEN_INPUT_ORIGIN.json',O/'FULL_PREPARATION_CARD.txt',T.FEATURE_SOURCE,
           O.parent/'trend_confirmation_dedup_v1/FORMULA_AND_ABLATION_CARD.txt',
           Path(N.SCORES.path),Path(I.C.__file__),Path(I.C.G.__file__)]
    years=('2022','2023','2024')if window=='long'else('strong',)
    for y in years:
        files.append(I.SCORE_PATHS[y])
        if y in I.YEARS:files.append(I.YEARS[y][0])
    src=A.source_freeze();src.update({str(p.resolve()):T.sha(p)for p in files})
    return dict(window=window,full_scope=['2022-01-04'if window=='long'else start,end],
         native_clock_start=start,expected_closes=726 if window=='long'else 242,
         fixed_feature_end=end,technical_max_end=technical_end,arms=list(T.ARMS),
         fresh_initial_cash=1000000,own_continuous_state_no_annual_reset=True,
         cost_guard=False,original_ACT20_BREAK63=True,
         score_binding=dict(path=N.SCORES.path,SHA256=N.SCORES.manifest_sha256),sources=src)

def configure(window,out):
    # Immutable private copy of the existing reviewed wrapper; no new loader.
    I.configure_scores(window,out)
    return source_manifest(window)

def prepare(window):
    root=O/'full-preparation'/window
    root.mkdir(parents=True,exist_ok=True)
    manifest=configure(window,root)
    p=root/'FULL_SOURCE_MANIFEST.json'
    if p.exists():assert read(p)==manifest,'prepared full source changed; preserve old preparation'
    else:save(p,manifest)
    proposal=dict(approved=False,scope='FULL_TREND_SIZE_WINDOW',window=window,
                  source_manifest=str(p.resolve()),source_manifest_SHA256=T.sha(p),
                  technical_gate_path=None,technical_gate_SHA256=None,
                  execution_not_authorized_by_preparation=True)
    q=root/'PROPOSED_FULL_AUTHORIZATION.json'
    if not q.exists():save(q,proposal)
    print('TREND_PREPARED_ONLY',window,T.sha(p),flush=True)

def execute(args):
    start,full_end,technical_max=WINDOWS[args.window]
    out=args.out.resolve();assert str(out).startswith(str(O.resolve())+'/')
    assert not(out/'STARTED.json').exists(),'existing attempt requires separate reviewed continuation'
    end=args.end or(technical_max if args.technical else full_end)
    if args.technical:assert start<=end<=technical_max,'technical entry cannot execute full history'
    else:assert end==full_end,'full end is a frozen parameter'
    out.mkdir(parents=True,exist_ok=True)
    current=configure(args.window,out)
    manifest_path=O/'full-preparation'/args.window/'FULL_SOURCE_MANIFEST.json'
    expected=read(manifest_path);assert current==expected,'prepared sources or fixed full schema differ'
    if not args.technical:
        assert args.authorization is not None,'root full authorization required'
        auth=read(args.authorization)
        assert auth['approved']is True and auth['scope']=='FULL_TREND_SIZE_WINDOW'
        assert auth['window']==args.window and auth['source_manifest_SHA256']==T.sha(manifest_path)
        gate=Path(auth['technical_gate_path'])
        assert gate.is_file()and T.sha(gate)==auth['technical_gate_SHA256']
        g=read(gate);assert g['passed']is True and g['full_source_manifest_SHA256'][args.window]==T.sha(manifest_path)
    save(out/'STARTED.json',dict(mode='technical'if args.technical else'full',
         full_schema=expected,actual_end=end,physical_inputs=bool(args.technical),
         resume=str(args.resume)if args.resume else None,full_authorization=str(args.authorization)if args.authorization else None))
    begin=time.monotonic()
    shared,receipts,cp,states,ir,identity=I.load_long(out)if args.window=='long'else I.load_strong(out)
    if args.technical:
        shared,receipts,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,end)
    else:kw=A.S.kwargs(cp,states,ir)
    J.START,J.END=start,full_end
    runner=T.Runner(shared,receipts,feature_end=full_end,
                    feature_input_limit=end if args.technical else full_end,**kw)
    runner.source_freeze=dict(expected['sources'])
    save(out/'INPUT_IDENTITY.json',identity)
    loaded=time.monotonic()
    with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
        cursor=runner.restore(args.resume)if args.resume else None
        if args.resume:
            save(out/'DERIVED_CACHE_RESTART.json',dict(fixed_end=runner.feature_cache.end,
                  available_through=runner.feature_cache.input_limit,
                  derived_cache_empty=not runner.feature_cache.values,
                  original_history_rebuild_not_restart_seed=True,
                  resume_after=str(cursor),real_accounts_and_pending_preserved=True))
        done=runner.run_prepared(out,args.seconds,resume_after=cursor,end=end)
    for p,h in expected['sources'].items():assert T.sha(p)==h,('frozen source changed',p)
    for p,h in runner.feature_cache.sources.items():assert T.sha(p)==h,('lazy feature source changed',p)
    save(out/'TIMING.json',dict(completed=done,input_seconds=loaded-begin,
          total_seconds=time.monotonic()-begin,event_loop_seconds=getattr(runner,'run_seconds',None)))
    save(out/'FEATURE_CACHE_CONTRACT.json',dict(fixed_end=runner.feature_cache.end,
         available_through=runner.feature_cache.input_limit,loaded_sids=len(runner.feature_cache.values),
         source_SHA256=runner.feature_cache.sources,checkpoint_derived_values_omitted=True))
    if not done:
        print('CHECKPOINTED_NO_AUTOMATIC_RESUME',args.window,flush=True);return
    save(out/'WINDOW_RESULT.json',dict(passed=True,technical=args.technical,actual_end=end,
        fixed_full_end=full_end,days=len(runner.daily)//len(runner.accounts),
        NAV={k:str(a.current_nav)for k,a in runner.accounts.items()},source_post_exact=True))
    print('TREND_WINDOW_SAVED',args.window,end,{k:str(a.current_nav)for k,a in runner.accounts.items()},flush=True)

def main():
    p=argparse.ArgumentParser();mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--technical',action='store_true')
    mode.add_argument('--execute',action='store_true')
    p.add_argument('--window',choices=WINDOWS,required=True);p.add_argument('--out',type=Path)
    p.add_argument('--end');p.add_argument('--resume',type=Path)
    p.add_argument('--authorization',type=Path);p.add_argument('--seconds',type=int,default=360)
    args=p.parse_args()
    if args.prepare:prepare(args.window)
    else:
        assert args.out is not None
        execute(args)

if __name__=='__main__':
    try:main()
    except BaseException:
        print(traceback.format_exc(),file=sys.stderr);raise
