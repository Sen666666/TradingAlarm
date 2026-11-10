"""Exactly two approved original-normal continuous Q2 suffixes."""
from pathlib import Path
import sys,importlib.util,time,gc
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
from initialization_guard import IO,initialize
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 E=initialize(lambda:load('frozen_normal_Q2_continuation',O/'continuation.py'),O/'runs','load_explicit_continuation');L=E.L;J=E.J
 IO.write_bytes(O/'INPUT_LOADER_SOURCE.txt',E.INPUT_SOURCE.encode());IO.write_bytes(O/'CHECKPOINT_DERIVED_INPUT_EXCLUSION.txt',E.CHECKPOINT_SOURCE.encode())
 t=time.monotonic();shared,receipts,cp,states,ir,identity=initialize(lambda:E.inputs('universe'),O/'runs','load_existing_Q2_cache');prep=time.monotonic()
 IO.write_json(O/'runs/INPUTS.json',dict(seconds=prep-t,identity=identity,horizon=E.END,new_cache_generation=0));print('Q2_INPUTS_READY',round(prep-t,3),flush=True)
 expected={x['reference']:x for x in L.read(O.parent/'q2-extension-readiness-20261031/CHECKPOINT_READINESS.json')['checkpoints']}
 kwargs=dict(stock_cp=cp,industry_states=states,industry_receipts=ir);cut='2026-04-01'
 for ref,cls,parent in [('B3',E.B3,J.O/'run-universe'),('B_diag',E.Bdiag,E.BASE.O/'run')]:
  out=O/'runs'/ref
  if (out/'DONE.json').exists():print('Q2_SKIP_COMPLETE',ref,flush=True);continue
  IO.write_json(out/'SPEC.json',dict(reference=ref,normal=True,R1=False,new_stage=False,cost=1,delay=0,original_initial_cash=1000000,extension=['2026-04-01',E.END],parent_checkpoint=str(parent/'checkpoint.pkl'),expected_parent_SHA=expected[ref]['sha256'],no_new_cash_or_state_reset=True))
  sources=[Path(__file__),O/'continuation.py',out/'SPEC.json',O.parent/'_shared/research_output_io.py',J.O/'joint_v3.py',Path(L.__file__),E.BASE.O/'adapter.py',E.BASE.O/'model_without_account_check.py',E.BASE.O/'route_without_account_check.py',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv',J.M.P/'h1.npz',parent/'checkpoint.pkl',parent/'checkpoint.json',parent/'pair/B.json.gz',O.parent/'q2-extension-readiness-20261031/CHECKPOINT_READINESS.json']
  freeze={str(p):L.sha(p) for p in sources};IO.write_json(out/'FREEZE.json',dict(before_new_events=True,identity=identity,sources=freeze))
  g=time.monotonic();r=initialize(lambda:cls(shared,receipts,**kwargs),out,'construct_with_full_Q2_views');r.source_freeze=dict(freeze)
  after,proof=r.import_verified_legacy(parent,expected[ref]);IO.write_json(out/'LEGACY_IMPORT_VERIFICATION.json',proof)
  print('Q2_LEGACY_IMPORTED',ref,'fields',len(proof['all_account_state_fields']),'NAV',proof['account_NAV'],'seconds',round(time.monotonic()-g,3),flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):r.checkpoint(out/'verified-imported-March31',after)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'first-April1-uninterrupted',90,resume_after=after,end=cut)
  current=J.M.N.iso(cut+'T15:10:00+08:00')
  restored=initialize(lambda:cls(shared,receipts,**kwargs),out,'construct_current_identity_restart');restored.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(restored,L,out,canonicalize=J.W.canon):assert restored.restore(out/'first-April1-uninterrupted/checkpoint.pkl')==current
  assert E.equal(E.observable(r),E.observable(restored)),'April1 restart changed full strategy/account state'
  physical=J.W.physical(shared,cut)
  prefix=initialize(lambda:cls(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}),out,'construct_physical_April1_prefix');prefix.source_freeze=dict(freeze)
  with IO.atomic_runner_outputs(prefix,L,out/'physical-April1-prefix',canonicalize=J.W.canon):
   start=prefix.restore(out/'verified-imported-March31/checkpoint.pkl');assert prefix.run_prepared(out/'physical-April1-prefix',90,resume_after=start,end=cut)
  assert E.equal(E.observable(r),E.observable(prefix)),'April1 physical prefix changed actual path'
  IO.write_json(out/'GATES.json',dict(passed=True,legacy_import_exact=True,old_file_identity_not_backfilled=True,all_state_equal_before_first_new_event=True,April1_restart_exact=True,April1_physical_prefix_exact=True,first_segment_continues_same_path=True,seconds=time.monotonic()-g))
  print('Q2_GATES_PASS',ref,round(time.monotonic()-g,3),flush=True);del r,prefix;gc.collect();r=restored
  started=time.monotonic()
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,180,resume_after=current,end=E.END)
  assert all(L.sha(Path(p))==v for p,v in freeze.items()),'Source/input changed during original-normal extension'
  IO.write_json(out/'TIMING.json',dict(complete=done,continuation_audit_export_seconds=time.monotonic()-started))
  if not done:print('Q2_SAVED_AT_BUDGET',ref,flush=True);return
  print('Q2_COMPLETE',ref,str(r.accounts['B'].current_nav),round(time.monotonic()-started,3),flush=True);del r,restored;gc.collect()
 IO.write_json(O/'runs/COMPLETION.json',dict(completed=2,normal_Q2_only=True,no_cost_D1_R1_or_new_policy=True,seconds=time.monotonic()-t))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  IO.write_json(O/'runs/failure/ENTRY_ERROR.json',dict(action='verified legacy normal Q2 continuation',type=type(e).__name__,reason=str(e)));raise
