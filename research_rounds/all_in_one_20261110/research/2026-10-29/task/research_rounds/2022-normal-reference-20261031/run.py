"""Only the two authorized frozen2022 normal paths, with short technical gates."""
from pathlib import Path
import sys,time,gc,importlib.util
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
from initialization_guard import IO,initialize
def load():
 s=importlib.util.spec_from_file_location('fixed_calendar2022_original_normal',O/'adapter.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def main():
 started=time.monotonic();A=initialize(load,O/'runs','load2022date_input_wrapper');J,L,E=A.J,A.L,A.E
 t=time.monotonic();shared,receipts,cp,states,ir,identity=initialize(A.inputs,O/'runs','load_existing_numeric_caches_and_new_trace');print('INPUTS_READY',round(time.monotonic()-t,2),flush=True)
 kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir);cut='2022-01-10';cut_at=J.M.N.iso(cut+'T15:10:00+08:00')
 for ref,cls in [('B3',A.B3),('B_diag',A.Bdiag)]:
  out=O/'runs'/ref
  if (out/'DONE.json').exists():print('SKIP_COMPLETED',ref,flush=True);continue
  sources=[Path(__file__),O/'adapter.py',O/'PROTOCOL.txt',O/'inputs/FREEZE.json',O/'inputs/MANIFEST.json',O/'inputs/COMPLETION.json',J.O/'joint_v3.py',J.BASE/'budget_v3/model.py',A.BASE.O/'model_without_account_check.py',A.BASE.O/'route_without_account_check.py',Path(L.__file__),O.parent/'_shared/research_output_io.py',J.M.O/'recovery.csv',J.M.P/'h1.npz']
  frozen={str(p):L.sha(p) for p in sources};A.save(out/'FREEZE.json',dict(before_events=True,reference=ref,identity=identity,sources=frozen,normal_only=True,R1=False,new_stage=False))
  g=time.monotonic();r=initialize(lambda:cls(shared,receipts,**kw),out,'fresh1m_original_warm_state');r.source_freeze=dict(frozen)
  a=r.accounts['B'];A.save(out/'INITIAL_STATE.json',dict(cash=a.available,NAV=a.current_nav,positions=0,orders=0,core_locks=0,losses=0,ACT=getattr(a,'risk_state',None),ACT_initialization='original risk_policy.step initializes lazily at first decision; no imported phase/peak',industry_states=J.W.canon(a.budget.sectors),source='new account, only original market warm state inherited'))
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'short-Jan10',120,end=cut)
  short_s=r.run_seconds
  restart=initialize(lambda:cls(shared,receipts,**kw),out,'same_identity_restart');restart.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(restart,L,out,canonicalize=J.W.canon):assert restart.restore(out/'short-Jan10/checkpoint.pkl')==cut_at
  assert E.equal(E.observable(r),E.observable(restart)),'Jan10 checkpoint restart mismatch'
  physical=J.W.physical(shared,cut);pre=initialize(lambda:cls(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}),out,'physical_short_prefix');pre.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(pre,L,out,canonicalize=J.W.canon):assert pre.run_prepared(out/'physical-Jan10',120,end=cut)
  assert E.equal(E.observable(r),E.observable(pre)),'Jan10 physical prefix mismatch'
  A.save(out/'GATES.json',dict(passed=True,original_bound_planning_opening=True,empty_financial_state=True,short_restart_exact=True,physical_prefix_exact=True,short_days=len(r.daily),short_replay_seconds=short_s,short_linear_242day_estimate_seconds=short_s*242/len(r.daily),gate_seconds=time.monotonic()-g))
  print('GATES_PASS',ref,round(time.monotonic()-g,2),'short',round(short_s,2),'estimate',round(short_s*242/len(r.daily),2),flush=True)
  del r,pre;gc.collect();r=restart;t=time.monotonic()
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,420,resume_after=cut_at,end=A.END)
  A.save(out/'TIMING.json',dict(complete=done,remaining_account_replay_audit_export_seconds=time.monotonic()-t))
  assert all(L.sha(p)==h for p,h in frozen.items()),'frozen source changed during run'
  if not done:print('SAVED_AT_BUDGET',ref,flush=True);return
  print('COMPLETE',ref,str(r.accounts['B'].current_nav),round(time.monotonic()-t,2),flush=True);del r,restart;gc.collect()
 A.save(O/'runs/COMPLETION.json',dict(completed=2,new_year2022normal_only=True,seconds=time.monotonic()-started))
if __name__=='__main__':
 try:main()
 except BaseException as e:IO.write_json(O/'runs/failure/ENTRY_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
