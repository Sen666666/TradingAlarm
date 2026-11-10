"""Only the two unblocked frozen cost2 arms; delay stays explicitly gated."""
from pathlib import Path
import importlib.util,sys,time,inspect
O=Path(__file__).resolve().parent
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
G=load('pressure_outer_initialization_guard',O/'initialization_guard.py');IO=G.IO
def observable(r):
 J=r._audit_J if hasattr(r,'_audit_J') else R.J
 return J.W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,balances=r.balance_audit,
  accounts={k:dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,audit=a.audit_log,journal=a.journal,available=a.available,positions=a.positions,buys=a.buys,exits=a.exits,decisions=a.decisions,budget=dict(sectors=a.budget.sectors,orders=a.budget.orders,lots=a.budget.lots,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))
def main():
 global R
 R=G.initialize(lambda:load('pressure_fixed_reference_engines',O/'pressure_runner.py'),O/'cost2-runs','load_reference_engines');L=R.L;J=R.J
 assert L.read(O/'COST_ADAPTER_GATE.json')['passed']
 started=time.monotonic();shared,receipts,cp,states,ir,identity=G.initialize(lambda:L.inputs('universe'),O/'cost2-runs','input_load');prepared=time.monotonic()
 IO.write_json(O/'cost2-runs/INPUT_PREPARATION.json',dict(seconds=prepared-started,identity=identity,cache_reused=True,normal_and_R1_not_replayed=True))
 print('COST2_INPUTS_PREPARED',round(prepared-started,3),flush=True)
 for ref,cls,baseline in [('B3',R.B3CostRunner,J.O/'run-universe/pair/B.json.gz'),('B_diag',R.DiagCostRunner,R.BASE.O/'run/pair/B.json.gz')]:
  out=O/'cost2-runs'/ref
  if (out/'DONE.json').exists():print('SKIP_COMPLETED',ref,flush=True);continue
  arm_started=time.monotonic();r=G.initialize(lambda:cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir),out,'runner_construct')
  assert Path(inspect.getfile(cls)).resolve()==(O/'pressure_runner.py').resolve();R.assert_identity(r,ref)
  IO.write_json(out/'REFERENCE_SPEC.json',dict(reference=ref,cost=2,delay=0,dates=[J.START,J.END],cash=1000000,R1=False,new_stage_rule=False,baseline=str(baseline)))
  source=[O/'pressure_runner.py',Path(__file__),O/'initialization_guard.py',O.parent/'_shared/research_output_io.py',out/'REFERENCE_SPEC.json',baseline,J.O/'joint_v3.py',R.BASE.O/'adapter.py',R.BASE.O/'model_without_account_check.py',R.BASE.O/'route_without_account_check.py',J.BASE/'budget_v3/model.py',Path(J.C.__file__),J.M.O/'recovery.csv',J.M.P/'h1.npz',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json']
  r.source_freeze={str(p):L.sha(p) for p in source}
  IO.write_json(out/'FREEZE.json',dict(before_run=True,reference=ref,mode='existing cost2',identity=identity,sources=r.source_freeze,actual_runner_module=cls.__module__,actual_runner_class=cls.__qualname__,actual_runner_file=inspect.getfile(cls),normal_baseline_not_replayed=True,delay_independent_mobile_unresolved=True))
  cut='2025-07-07'
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'prefix-full-source',90,end=cut)
  physical=J.W.physical(shared,cut)
  prefix=G.initialize(lambda:cls(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}),out,'physical_prefix_construct')
  prefix.source_freeze=dict(r.source_freeze)
  with IO.atomic_runner_outputs(prefix,L,out/'prefix-physical-source',canonicalize=J.W.canon):assert prefix.run_prepared(out/'prefix-physical-source',90,end=cut)
  assert observable(r)==observable(prefix);del prefix
  # Exercise actual new provenance restore without repeating the completed prefix.
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):after=r.restore(out/'prefix-full-source/checkpoint.pkl')
  R.assert_identity(r,ref)
  IO.write_json(out/'PREFIX_AND_IDENTITY_GATE.json',dict(passed=True,cut=cut,both_sides_persisted=True,actual_restore_identity_passed=True,whole_account_prefix_not_reinitialized=True))
  print('COST2_PREFIX_PASS',ref,'fills',len(r.accounts['B'].trades),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,360,resume_after=after)
  IO.write_json(out/'TIMING.json',dict(arm_seconds=time.monotonic()-arm_started,completed=done,shared_input_load_excluded=True))
  if not done:print('COST2_CHECKPOINT_SAVED',ref,flush=True);return
  print('COST2_ARM_DONE',ref,str(r.accounts['B'].current_nav),flush=True);del r
 IO.write_json(O/'cost2-runs/COMPLETION.json',dict(cost2_paths_complete=2,delay_paths_started=0,normal_paths_replayed=0,total_seconds=time.monotonic()-started,delay_blocker='independent mobile wait-credit contract pending'))
if __name__=='__main__':
 try:main()
 except BaseException as error:
  try:IO.write_json(O/'cost2-runs/failure/ENTRY_ERROR.json',dict(action='cost2 entry/input/construct/gate/run',error_type=type(error).__name__,reason=str(error)))
  except BaseException as report:error.add_note('Entry failure report failed: '+str(report))
  raise
