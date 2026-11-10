"""Corrected plugin loader; baseline v1 remains immutable while running; no financial logic change."""
from pathlib import Path
import argparse,json,hashlib,time,traceback,sys
import load_inputs as V
O=Path(__file__).resolve().parent
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):IO.write_json(p,J.W.canon(x))
def execute(arm,window,seconds):
 freeze=json.loads((O/'STATE_MACHINE_FREEZE.json').read_text());assert arm in freeze['active_arms'];out=O/'runs'/arm/window
 assert not out.exists(),'Never overwrite or silently replay completed/partial/failed path'
 out.mkdir(parents=True);started=time.monotonic()
 try:
  shared,receipts,cp,states,ir,identity=V.inputs(window)
  sources=A.source_freeze();sources.update({str(p):sha(p) for p in [Path(__file__),O/'load_inputs.py',O/'PROTOCOL.txt',O/'STATE_MACHINE_FREEZE.json']})
  if arm=='BASELINE':cls=A.Runner;tool_manifest=None
  else:
   from indicator_provider import IndicatorProvider
   M=J.W.load('trend_exit_v1_frozen_adapter',O/'native_adapter/trend_exit_adapter.py')
   build_runner_class=M.build_runner_class
   provider=IndicatorProvider();cls=build_runner_class(A,provider,arm);tool_manifest=provider.manifest_sha256
   for p in [O/'indicator_provider.py',O/'native_adapter/trend_exit_adapter.py',O/'indicators/MANIFEST.json']:sources[str(p)]=sha(p)
  r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources
  a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  save(out/'RUN_METADATA.json',dict(arm=arm,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,tool_manifest_sha256=tool_manifest,load_seconds=time.monotonic()-started,authorization='parent delegated explicit local complete-account tests; all frozen arms reported; no live trading'))
  print('NATIVE_ACCOUNT_STARTED',arm,window,'load',round(time.monotonic()-started,2),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
  assert all(sha(p)==h for p,h in sources.items()),'sources changed during path'
  save(out/'TIMING.json',dict(completed=done,total_seconds=time.monotonic()-started,event_seconds=getattr(r,'run_seconds',None),ending_NAV=str(a.current_nav),new_complete_account=bool(done)))
  print('NATIVE_ACCOUNT_SAVED',arm,window,done,str(a.current_nav),round(time.monotonic()-started,2),flush=True)
 except BaseException as e:
  save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arm',required=True);p.add_argument('--window',choices=['2022_2024','strong'],required=True);p.add_argument('--seconds',type=float,default=1800);z=p.parse_args();execute(z.arm,z.window,z.seconds)
