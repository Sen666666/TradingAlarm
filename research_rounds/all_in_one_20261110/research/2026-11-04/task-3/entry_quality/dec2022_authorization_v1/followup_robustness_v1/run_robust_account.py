"""One frozen robustness path; fresh native account, no overwrites or replay."""
from pathlib import Path
import argparse,hashlib,json,sys,time,traceback
F=Path(__file__).resolve().parent;D=F.parent;T=D.parent/'trend_exit_controls_v1'
sys.path.insert(0,str(T));import load_inputs as V
sys.path.insert(0,str(F));from variant_provider import VariantProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,z):IO.write_json(p,J.W.canon(z))
def execute(label,window,seconds):
 freeze=json.loads((F/'ROBUSTNESS_FREEZE.json').read_text());specs={v['label']:v for v in freeze['parameter_variants']+freeze['cost_variants']};assert label in specs
 spec=specs[label];out=F/'runs'/label/window;assert not out.exists(),'No overwrite or automatic replay of prior outcome';out.mkdir(parents=True);started=time.monotonic()
 try:
  shared,receipts,cp,states,ir,identity=V.inputs(window);provider=VariantProvider(spec['R'],spec['EMA']);extra={};cost=None
  if spec['cost_multiplier']!=1:
   cost=J.W.load('h2_frozen_cost_stress150',F/'cost_adapter/cost_stress.py');extra=cost.apply_cost_stress(V)
  M=J.W.load('I_mobile_authorization_frozen_v1',D/'native_adapter/mobile_authorization_adapter.py');cls=M.build_runner_class(A,provider,spec['mode'])
  r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
  if cost is not None:cost.configure_runner(r);cost.assert_cost_stress_runner(r)
  a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
  sources=M.source_freeze(A)
  if cost is not None:sources.update(extra['source_freeze'])
  for p in [Path(__file__),Path(V.__file__),F/'ROBUSTNESS_FREEZE.json',F/'variant_provider.py',F/'prepare_context_variants.py',F/'contexts/MANIFEST.json',D/'H2_POLICY_FREEZE.json']:
   sources[str(p)]=sha(p)
  if cost is not None:sources[str(F/'cost_adapter/cost_stress.py')]=sha(F/'cost_adapter/cost_stress.py')
  r.source_freeze=sources
  save(out/'RUN_METADATA.json',dict(policy='H2_JOINT_one_factor_and_cost_robustness_v1',label=label,spec=spec,window=window,start=J.START,end=J.END,fresh_cash=1000000,no_checkpoint_import=True,yearly_reset=False,source_freeze=sources,input_identity=identity,context_provider_parameter_sha256=provider.manifest_sha256,context_data_manifest_sha256=provider.data_manifest_sha256,cost_stress=extra,load_seconds=time.monotonic()-started,original_frozen_policy_sha256=sha(D/'H2_POLICY_FREEZE.json'),authorization='Parent requested limited parameter and cost perturbations; no new entry mechanism full account'))
  print('ROBUST_ACCOUNT_STARTED',label,window,round(time.monotonic()-started,2),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,seconds,end=J.END)
  assert all(sha(p)==h for p,h in sources.items()),'Frozen source changed during execution'
  save(out/'TIMING.json',dict(completed=done,total_seconds=time.monotonic()-started,event_seconds=getattr(r,'run_seconds',None),ending_NAV=str(a.current_nav),new_complete_account=bool(done)))
  print('ROBUST_ACCOUNT_SAVED',label,window,done,str(a.current_nav),round(time.monotonic()-started,2),flush=True)
 except BaseException as e:
  save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--window',choices=['2022_2024','strong'],required=True);p.add_argument('--seconds',type=float,default=3600);z=p.parse_args();execute(z.label,z.window,z.seconds)
