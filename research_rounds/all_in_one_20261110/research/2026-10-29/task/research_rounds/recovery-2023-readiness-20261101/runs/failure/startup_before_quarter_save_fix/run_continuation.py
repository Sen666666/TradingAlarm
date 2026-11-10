"""Exactly two approved same-account 2023 normal continuations; no new capital."""
from pathlib import Path
import sys,time,gc,json,gzip,hashlib
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'execution-pressure-preflight-20261031'))
from initialization_guard import IO,initialize
def main():
 t=time.monotonic();Y=initialize(lambda:__import__('continuation_2023'),O/'runs','load_frozen_2023_horizon');J,L,E=Y.J,Y.L,Y.E
 shared,receipts,cp,states,ir,identity=initialize(Y.inputs,O/'runs','original_2023_numeric_cache_and_receipt_input');loadsec=time.monotonic()-t;print('INPUTS_READY',round(loadsec,3),flush=True)
 kwargs=dict(stock_cp=cp,industry_states=states,industry_receipts=ir);cut='2023-01-03';atcut=J.M.N.iso(cut+'T15:10:00+08:00')
 refs=[('Bdiag',Y.Bdiag,W/'2022-normal-reference-20261031/runs/B_diag','6e1ab631d549535eb762d84422659ab8f33459ddb5c07c6fe649eb47c091bdcd'),('C1',Y.C1,W/'c1-drawdown-capacity-20261101/runs/2022','2d7d3a8bc7490c7db466e376959bfd85f5991d19b82092cf731c90f15c056929')]
 for ref,cls,parent,expected in refs:
  out=O/'runs'/ref
  if (out/'DONE.json').exists():print('SKIP_COMPLETED',ref,flush=True);continue
  sources=[Path(__file__),O/'continuation_2023.py',O/(ref+'_route_trace.py'),O/'inputs/FREEZE.json',O/'inputs/MANIFEST.json',O/'inputs/COMPLETION.json',O/'CHECKPOINT_READINESS.json',Path(Y.C.__file__),J.O/'joint_v3.py',J.BASE/'budget_v3/model.py',Y.BASE.O/'adapter.py',Y.BASE.O/'model_without_account_check.py',Y.BASE.O/'route_without_account_check.py',Path(L.__file__),W/'_shared/research_output_io.py',J.M.O/'recovery.csv',J.M.P/'h1.npz',parent/'checkpoint-2022-12-30.pkl',parent/'checkpoint-2022-12-30.provenance.json']
  frozen={str(p):L.sha(p) for p in sources};Y.save(out/'FREEZE.json',dict(before_events=True,reference=ref,identity=identity,sources=frozen,no_new_initial_cash=True,original_normal_only=True,only_extra_logging=True))
  g=time.monotonic();r=initialize(lambda:cls(shared,receipts,**kwargs),out,'construct_extended_input_view_before_exact_state_import');r.source_freeze=dict(frozen)
  after,proof=r.import_verified(parent,expected);Y.save(out/'VERIFIED_IMPORT.json',proof);print('IMPORTED',ref,'NAV',r.accounts['B'].current_nav,'ACT',r.accounts['B'].risk_state,flush=True)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):r.checkpoint(out/'verified-Dec30',after)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'first-Jan3',120,resume_after=after,end=cut)
  firstsec=r.run_seconds
  restored=initialize(lambda:cls(shared,receipts,**kwargs),out,'same_bound_identity_restart');restored.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(restored,L,out,canonicalize=J.W.canon):assert restored.restore(out/'first-Jan3/checkpoint.pkl')==atcut
  assert E.equal(E.observable(r),E.observable(restored)),'Jan3 full restart differs'
  physical=J.W.physical(shared,cut);pre=initialize(lambda:cls(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}),out,'physical_Jan3_input_prefix');pre.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(pre,L,out,canonicalize=J.W.canon):assert pre.restore(out/'verified-Dec30/checkpoint.pkl')==after;assert pre.run_prepared(out/'physical-Jan3',120,resume_after=after,end=cut)
  assert E.equal(E.observable(r),E.observable(pre)),'Jan3 physical prefix differs'
  Y.save(out/'GATES.json',dict(passed=True,exact_original_yearend_state_import=True,known_generation_identity_not_backfilled=True,Jan3_restart_all_state_exact=True,Jan3_physical_prefix_exact=True,old_policy_sources_unchanged=True,route_trace_only_inverse_exact=True,first_segment_seconds=firstsec,gate_seconds=time.monotonic()-g))
  print('GATES_PASS',ref,round(time.monotonic()-g,3),'firstday',round(firstsec,3),'provisional_loop_estimate',round(firstsec*242,1),flush=True)
  del r,pre;gc.collect();r=restored;started=time.monotonic()
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,420,resume_after=atcut,end=Y.END)
  assert all(L.sha(p)==v for p,v in frozen.items()),'source/input changed while frozen path ran'
  Y.save(out/'TIMING.json',dict(complete=done,input_load_seconds=loadsec,first_segment_seconds=firstsec,continuation_audit_export_seconds=time.monotonic()-started,no_2022_account_replay=True))
  if not done:print('SAVED_AT_BUDGET',ref,flush=True);return
  print('COMPLETE',ref,'NAV',r.accounts['B'].current_nav,'seconds',round(time.monotonic()-started,3),flush=True);del r,restored;gc.collect()
 Y.save(O/'runs/COMPLETION.json',dict(completed=2,year2023_continuation_only=True,seconds=time.monotonic()-t,original2022_replayed=False))
if __name__=='__main__':
 try:main()
 except BaseException as e:IO.write_json(O/'runs/failure/ENTRY_ERROR.json',dict(action='approved 2023 same-account normal continuations',type=type(e).__name__,reason=str(e)));raise
