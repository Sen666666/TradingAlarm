"""ONE explicitly approved remaining PVR_SLOT1 2023 path, no baseline replay."""
from pathlib import Path
from datetime import datetime,timezone
import time,json,pickle
import horizon_import as H
N,J,L,IO,O,P=H.N,H.J,H.L,H.IO,H.O,H.P
ROOT=O/'run-2023';AUTH=O/'FULL_2023_RUN_AUTHORIZATION.json'
PARENT=O/'first-session/full-input/checkpoint.pkl'
EXPECTED='27d1d3c21e76cbca42f97803ab0f21014769d7aea22ffd6e1d3cb1408d61f0cd'
CURSOR=J.M.N.iso('2023-01-03T15:10:00+08:00')
def save(p,x):IO.write_json(p,J.W.canon(x))
def main():
    begun=time.monotonic();a=H.read(AUTH)
    assert a['scope']=='ONE_PVR_SLOT1_2023_financial_continuation'
    assert a['launcher_sha256']==H.sha(__file__) and a['horizon_import_sha256']==H.sha(H.__file__)
    assert a['native_adapter_sha256']==H.ADAPTER_SHA==H.sha(N.__file__)
    assert a['binding_sha256']==H.sha(H.DEFAULT_BINDING)
    assert a['resume_checkpoint_sha256']==EXPECTED==H.sha(PARENT)
    assert a['resume_after']==str(CURSOR) and a['end']=='2023-12-29'
    assert not (ROOT/'DONE.json').exists(),'completed path must never rerun'
    assert not (ROOT/'checkpoint.pkl').exists(),'partial path exists: stop for explicit recovery, no silent restart'
    IO.prepare_targets(dict(final=ROOT/'pair',checkpoint=ROOT/'checkpoint.pkl',failure=ROOT/'failure/ERROR.json'),directory_keys={'final'})
    save(ROOT/'ACTUAL_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),authorization_sha256=H.sha(AUTH),
         launcher_sha256=H.sha(__file__),cursor=str(CURSOR),first_session_not_rerun=True,SC_not_rerun=True))
    N.configure_scores(O/'SCORES_MANIFEST.json')
    oldsave=H.save
    try:
        H.save=lambda path,value:save(ROOT/'input-readiness'/Path(path).name,value)
        shared,receipts,cp,states,ir,identity=H.inputs()
    finally:H.save=oldsave
    loaded=time.monotonic();frozen=H.read(O/'first-session/FIRST_SESSION_SOURCE_FREEZE.json')
    assert all(H.sha(p)==h for p,h in frozen.items())
    fullfreeze=dict(frozen,**{str(Path(__file__).resolve()):H.sha(__file__),str(AUTH.resolve()):H.sha(AUTH)})
    save(ROOT/'EXECUTION_FREEZE.json',dict(checkpoint_source_freeze_preserved=frozen,entry_sources=fullfreeze,identity=identity))
    r=H.Continuation(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
    r.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):assert r.restore(PARENT)==CURSOR
    assert len(r.accounts['B'].pending)==279
    from collections import Counter
    assert Counter(i['role'] for i in r.accounts['B'].pending)=={'core':184,'mobile':95}
    assert all(i['clock'].earliest_execution_at==J.M.N.iso('2023-01-04T09:30:00+08:00') for i in r.accounts['B'].pending)
    acc=r.accounts['B'];assert '603589.SH' in acc.exits
    assert sum(x['qty'] for x in acc.layers if x['id'] in acc.sell_layers['603589.SH'])==400
    save(ROOT/'RESTORED_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),cursor=str(CURSOR),
        NAV=str(r.accounts['B'].current_nav),cash=str(r.accounts['B'].available),pending_intents=279,pending_exit603589=400,
        source_freeze_preserved=True,all_old_streams_preserved=True,input_load_seconds=loaded-begun,
        parent_checkpoint_sha256=H.sha(PARENT),runtime_identity=IO.runner_identity(r)))
    print('PVR2023_RESTORED',r.accounts['B'].current_nav,'load',round(loaded-begun,2),flush=True)
    loop=time.monotonic()
    save(ROOT/'EVENT_LOOP_START.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),strictly_after=str(CURSOR),end=H.END))
    with IO.atomic_runner_outputs(r,L,ROOT,canonicalize=J.W.canon):
        done=r.run_prepared(ROOT,600,resume_after=CURSOR,end=H.END)
    assert all(H.sha(p)==h for p,h in fullfreeze.items())
    save(ROOT/'TIMING.json',dict(completed=done,at_UTC=datetime.now(timezone.utc).isoformat(),
        input_load_seconds=loaded-begun,event_loop_recorded_seconds=r.run_seconds,
        continuation_and_export_seconds=time.monotonic()-loop,total_seconds=time.monotonic()-begun,
        ending_NAV=str(r.accounts['B'].current_nav),only_remaining_2023_path=True,baseline_replays=0))
    print('PVR2023_COMPLETE' if done else 'PVR2023_CHECKPOINTED_LIMIT',r.accounts['B'].current_nav,
          'total',round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as e:
        save(ROOT/'failure/ENTRY_ERROR.json',dict(type=type(e).__name__,reason=str(e),
            completed_prefix_not_to_be_rerun=True,scope='ONE remaining2023 path only'));raise
