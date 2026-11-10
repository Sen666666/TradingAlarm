"""One frozen priority-source substitution, with original native trading methods."""
from pathlib import Path
import argparse,hashlib,json,sys,time,traceback
P=Path(__file__).resolve().parent;S=P.parent;E=S.parent;T=E/'trend_exit_controls_v1'
sys.path.insert(0,str(T));import load_inputs as V
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,z):IO.write_json(p,J.W.canon(z))
def execute(window,seconds):
 gate=json.loads((P/'EXECUTION_GATE.json').read_text());assert gate['status']=='PASS_FROZEN_ETA_SOURCE_AND_NATIVE_WIRING'
 for p,h in gate['source_sha256'].items():assert sha(p)==h,('changed gate source',p)
 manifest=Path(gate['eta_score_manifest']);assert sha(manifest)==gate['eta_score_manifest_sha256']
 out=P/'runs'/window;assert not out.exists(),'No overwrite/replay of a completed or partial path';out.mkdir(parents=True);started=time.monotonic()
 try:
  shared,receipts,cp,states,ir,old_identity=V.inputs(window)
  original_score_sha=N.SCORES.manifest_sha256
  N.configure_scores(manifest);selected=N.SCORES.manifest_sha256;assert selected==gate['eta_score_manifest_sha256']
  r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
  assert r.rank_mode=='PVR_SLOT1' and r.rank_scores_manifest_sha256==selected
  assert r.planning.__func__ is N.Runner.planning and r.opening.__func__ is J.Runner.opening and r.route.__func__ is A.P.ROUTES[True]
  a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  sources=A.source_freeze()
  for p in [Path(__file__),Path(V.__file__),P/'HYPOTHESIS_FREEZE.json',P/'EXECUTION_GATE.json',manifest]:sources[str(p.resolve())]=sha(p)
  sources.update(gate['source_sha256']);r.source_freeze=sources
  save(out/'RUN_METADATA.json',dict(policy='PVR_ETA_ORIGINAL_E21_MASS_SHARE_SLOT_ONLY_V1',window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,rank_mode_compatibility_alias='PVR_SLOT1',rank_log_PVR_field_semantics='Raw eta replaces original score only for this pre-registered run; no display transform; round12/H1 ties and UNKNOWN slots native',selected_eta_manifest=str(manifest),selected_eta_manifest_sha256=selected,original_priority_manifest_sha256=original_score_sha,original_shared_input_identity=old_identity,source_freeze=sources,load_seconds=time.monotonic()-started,original_baseline_reused=str(T/'runs/BASELINE'/window),baseline_equality_sha256=sha(T/'runs/BASELINE'/window/'FULL_BASELINE_EQUALITY.json'),no_signal_or_capital_exit_rule_change=True))
  assert N.SCORES.manifest_sha256==selected
  print('ETA_ACCOUNT_STARTED',window,round(time.monotonic()-started,2),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
  assert N.SCORES.manifest_sha256==selected and r.rank_scores_manifest_sha256==selected
  assert all(sha(p)==h for p,h in sources.items()),'source changed during eta account'
  save(out/'TIMING.json',dict(completed=done,total_seconds=time.monotonic()-started,event_seconds=getattr(r,'run_seconds',None),ending_NAV=str(a.current_nav),new_complete_account=bool(done)))
  print('ETA_ACCOUNT_SAVED',window,done,str(a.current_nav),round(time.monotonic()-started,2),flush=True)
 except BaseException as e:
  save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022_2024','strong'],required=True);p.add_argument('--seconds',type=float,default=3600);z=p.parse_args();execute(z.window,z.seconds)
