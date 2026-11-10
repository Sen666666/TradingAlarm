"""One explicitly requested fresh full account, fixed mobile-authority ablation."""
from pathlib import Path
import argparse,json,hashlib,time,traceback,sys
O=Path(__file__).resolve().parent;R=O.parent/'trend_exit_controls_v1'
sys.path.insert(0,str(R));import load_inputs as V
sys.path.insert(0,str(O));from context_provider import ContextProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):IO.write_json(p,J.W.canon(x))
def execute(arm,window,seconds):
 f=json.loads((O/'H2_POLICY_FREEZE.json').read_text());assert arm in f['arms'] and arm!='BASELINE';assert arm in ['R_ONLY','P_ONLY','JOINT']
 out=O/'runs'/arm/window;assert not out.exists(),'No overwrite/automatic replay of a partial or completed path';out.mkdir(parents=True);t=time.monotonic()
 try:
  shared,receipts,cp,states,ir,identity=V.inputs(window);provider=ContextProvider();M=J.W.load('I_mobile_authorization_frozen_v1',O/'native_adapter/mobile_authorization_adapter.py');cls=M.build_runner_class(A,provider,arm)
  sources=M.source_freeze(A)
  for p in [Path(__file__),Path(V.__file__),O/'H2_POLICY_FREEZE.json',O/'context_provider.py',O/'relative_context/MANIFEST.json']:sources[str(p)]=sha(p)
  r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources;a=r.accounts['B']
  assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  save(out/'RUN_METADATA.json',dict(policy='I_mobile_authority_H2_v1',arm=arm,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,context_manifest_sha256=provider.manifest_sha256,load_seconds=time.monotonic()-t,baseline_reused=str(R/'runs/BASELINE'/window),baseline_full_equality_sha256=sha(R/'runs/BASELINE'/window/'FULL_BASELINE_EQUALITY.json'),authorization='parent explicit local cross-year complete-account and ablation request, original hard risk and native execution retained, no live trading'))
  print('H2_ACCOUNT_STARTED',arm,window,'load',round(time.monotonic()-t,2),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
  assert all(sha(p)==h for p,h in sources.items()),'source changed during account'
  save(out/'TIMING.json',dict(completed=done,total_seconds=time.monotonic()-t,event_seconds=getattr(r,'run_seconds',None),ending_NAV=str(a.current_nav),new_complete_account=bool(done)))
  print('H2_ACCOUNT_SAVED',arm,window,done,str(a.current_nav),round(time.monotonic()-t,2),flush=True)
 except BaseException as e:save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=['R_ONLY','P_ONLY','JOINT'],required=True);p.add_argument('--window',choices=['2022_2024','strong'],required=True);p.add_argument('--seconds',type=float,default=2400);z=p.parse_args();execute(z.arm,z.window,z.seconds)
