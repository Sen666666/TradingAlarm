"""Exactly the two approved D1 pressure paths, with D0/prefix/restart gates."""
from pathlib import Path
import sys,importlib.util,time,inspect
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
from initialization_guard import initialize,IO
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def observable(r,extra=False):
 result=E.J.W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,balances=r.balance_audit,
 accounts={k:dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,audit=a.audit_log,journal=a.journal,available=a.available,positions=a.positions,buys=a.buys,exits=a.exits,decisions=a.decisions,budget=dict(sectors=a.budget.sectors,orders=a.budget.orders,lots=a.budget.lots,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))
 if extra:result['D1']=E.J.W.canon({k:dict(orders=a.d1_orders,exits=a.d1_exits,audit=a.d1_audit) for k,a in r.accounts.items()})
 return result
def main():
 global E
 root=O/'runs';E=initialize(lambda:load('frozen_D1_reference_engines',O/'d1_runner.py'),root,'load_D1_engines');L=E.L;J=E.J
 assert L.read(O/'REAL_PAIR_GATE.json')['passed'];assert L.sha(O/'d1_runner.py')==L.read(O/'REAL_PAIR_GATE.json')['source_sha256']
 begin=time.monotonic();shared,receipts,cp,states,ir,identity=initialize(lambda:L.inputs('universe'),root,'shared_verified_cache_load')
 prepared=time.monotonic();IO.write_json(root/'INPUT_PREPARATION.json',dict(seconds=prepared-begin,identity=identity,cache_only=True));print('D1_INPUTS_READY',round(prepared-begin,3),flush=True)
 specs=[('B3',E.B3D1,J.O/'run-universe/pair/B.json.gz'),('B_diag',E.DiagD1,E.BASE.O/'run/pair/B.json.gz')];ready=[];cut='2025-07-07'
 kwargs=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
 for ref,cls,baseline in specs:
  out=root/ref
  if (out/'DONE.json').exists():print('D1_SKIP_COMPLETE',ref,flush=True);continue
  IO.write_json(out/'SPEC.json',dict(reference=ref,execution='D1 bounded one market trading-day delay pressure',enabled=True,cost=1,dates=[J.START,J.END],initial_cash=1000000,no_R1=True,no_new_stage=True,normal_book_reused=str(baseline)))
  files=[Path(__file__),O/'d1_runner.py',O/'CONTRACT.txt',O/'test_real_pair.py',O/'REAL_PAIR_GATE.json',out/'SPEC.json',O.parent/'_shared/research_output_io.py',J.O/'joint_v3.py',E.BASE.O/'adapter.py',E.BASE.O/'model_without_account_check.py',E.BASE.O/'route_without_account_check.py',J.BASE/'budget_v3/model.py',Path(J.C.__file__),J.M.O/'recovery.csv',J.M.P/'h1.npz',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',baseline]
  freeze={str(p):L.sha(p) for p in files};IO.write_json(out/'FREEZE.json',dict(before_account_path=True,sources=freeze,identity=identity,engine_class=cls.__qualname__,engine_module=cls.__module__,engine_file=inspect.getfile(cls)))
  gt=time.monotonic();native_cls=L.PreparedRunner if ref=='B3' else E.BASE.Runner
  nk=dict(kwargs)
  if ref=='B3':nk['policies']=('B',)
  native=initialize(lambda:native_cls(shared,receipts,**nk),out,'D0_original_prefix_construct');native.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(native,L,out/'D0-original',canonicalize=J.W.canon):assert native.run_prepared(out/'D0-original',90,end=cut)
  off=initialize(lambda:cls(shared,receipts,enabled=False,**kwargs),out,'D0_disabled_prefix_construct');off.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(off,L,out/'D0-disabled',canonicalize=J.W.canon):assert off.run_prepared(out/'D0-disabled',90,end=cut)
  assert observable(native)==observable(off),'D0 original normal event mismatch';del native,off
  r=initialize(lambda:cls(shared,receipts,enabled=True,**kwargs),out,'D1_prefix_construct');r.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'prefix-full-source',90,end=cut)
  physical=J.W.physical(shared,cut)
  prefix=initialize(lambda:cls(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},enabled=True,
   stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}),out,'D1_physical_prefix_construct');prefix.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(prefix,L,out/'prefix-physical-source',canonicalize=J.W.canon):assert prefix.run_prepared(out/'prefix-physical-source',90,end=cut)
  assert observable(r,True)==observable(prefix,True),'D1 physical prefix mismatch';del prefix
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):after=r.restore(out/'prefix-full-source/checkpoint.pkl')
  IO.write_json(out/'GATES.json',dict(passed=True,D0_original_event_exact=True,D1_physical_prefix_exact=True,cut=cut,both_physical_sides_persisted=True,actual_stable_identity_restore=True,seconds=time.monotonic()-gt,prefix_actual_fills=len(r.accounts['B'].trades)))
  print('D1_GATES_PASS',ref,'seconds',round(time.monotonic()-gt,3),'fills',len(r.accounts['B'].trades),flush=True);ready.append((ref,r,out,after,freeze))
 IO.write_json(root/'GATES_READY.json',dict(passed=True,references=[x[0] for x in ready],preparation_and_gates_seconds=time.monotonic()-begin,remaining_paths=len(ready),expected_full_replay_seconds_each=[150,200]));print('D1_ECONOMIC_PATHS_BEGIN',len(ready),flush=True)
 for ref,r,out,after,freeze in ready:
  started=time.monotonic()
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,300,resume_after=after)
  assert all(L.sha(Path(p))==h for p,h in freeze.items()),'frozen source/input changed during D1 path'
  IO.write_json(out/'TIMING.json',dict(completed=done,continuation_audit_and_export_seconds=time.monotonic()-started))
  if not done:print('D1_SAVED_AT_BUDGET',ref,flush=True);return
  print('D1_COMPLETE',ref,str(r.accounts['B'].current_nav),'seconds',round(time.monotonic()-started,3),flush=True)
 IO.write_json(root/'COMPLETION.json',dict(paths_complete=2,normal_or_cost_paths_replayed=False,only_D0_short_engineering_prefixes=True,total_seconds=time.monotonic()-begin))
if __name__=='__main__':
 try:main()
 except BaseException as error:
  try:IO.write_json(O/'runs/failure/ENTRY_ERROR.json',dict(action='D1 load/construct/gates/replay/export',error_type=type(error).__name__,reason=str(error)))
  except BaseException as report:error.add_note('Failure report unavailable: '+str(report))
  raise
