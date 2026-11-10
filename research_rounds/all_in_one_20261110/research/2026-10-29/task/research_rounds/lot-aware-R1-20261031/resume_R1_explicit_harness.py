"""Explicit-file R1 harness recovery; reject ambiguous same-name modules."""
from pathlib import Path
import inspect,time
import adapter_r1 as R
L=R.L;J=R.J;O=R.O;OUT=O/'run';ARCHIVE=O/'invalid-hybrid-after-resume'
H=J.W.load('R1_unique_frozen_run_harness',O/'run_one.py')
Pair=H.Pair
def main():
 assert not (OUT/'DONE.json').exists()
 assert Path(inspect.getfile(Pair)).resolve()==(O/'run_one.py').resolve()
 assert issubclass(Pair,R.Runner)
 assert Pair.planning is R.Runner.planning and Pair.opening is R.Runner.opening and Pair.route is R.Runner.route
 L.save(O/'RESUME_CLASS_GATE.json',dict(passed=True,actual_module=Pair.__module__,actual_file=inspect.getfile(Pair),planning_opening_route_are_R1=True,harness_sha256=L.sha(O/'run_one.py'),resume_script_sha256=L.sha(Path(__file__))))
 original=L.read(ARCHIVE/'FREEZE.json');frozen=original['sources']
 for path,sha in frozen.items():assert L.sha(path)==sha,('frozen source changed',path)
 started=time.monotonic();shared,receipts,cp,states,ir,identity=L.inputs('universe');assert identity==original['identity']
 r=Pair(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=frozen
 after=r.restore(ARCHIVE/'prefix-full-source/checkpoint.pkl');cut='2025-07-07';assert str(after.date())==cut
 assert type(r) is Pair and r.r1_enabled and r.planning.__func__ is R.Runner.planning and r.opening.__func__ is R.Runner.opening and r.route.__func__ is R.Runner.route
 L.save(OUT/'FREEZE.json',dict(original,valid_R1_resume=True,invalid_hybrid_archive=str(ARCHIVE),resume_identity=L.read(O/'RESUME_CLASS_GATE.json'),restored_valid_checkpoint=str(ARCHIVE/'prefix-full-source/checkpoint.pkl')))
 prepared=time.monotonic();print('CORRECT_R1_RESUME_PREPARED',round(prepared-started,3),Pair.__module__,flush=True)
 physical=J.W.physical(shared,cut);prefix=R.Runner(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
 t=time.monotonic();prefix.run(end=cut,begin=J.START,max_seconds=90);assert H.observable(r)==H.observable(prefix)
 prefix.dump_joint(OUT/'prefix-physical-source/pair');L.save(OUT/'prefix-physical-source/R1_AUDIT.json',dict(opening_eligible_previews=prefix.r1_previews,actual_reservations=prefix.r1_reservations));side=time.monotonic()-t
 L.save(OUT/'PREFIX_GATE.json',dict(passed=True,cut=cut,exact_observable_assertion=True,full_side_saved=str(ARCHIVE/'prefix-full-source/pair'),physical_side_saved=str(OUT/'prefix-physical-source/pair'),both_R1_function_identities_asserted=True,source_prefix_account_restored_not_replayed=True))
 print('CORRECT_R1_PREFIX_PASS',round(side,3),'initial_receipts',len(r.r1_previews),flush=True);del prefix
 t=time.monotonic();done=r.run_prepared(OUT,420,resume_after=after)
 L.save(OUT/'TIMING.json',dict(valid_resume_preparation_seconds=prepared-started,physical_prefix_seconds=side,valid_continuation_audit_save_seconds=time.monotonic()-t,total_valid_resume_wall_seconds=time.monotonic()-started,new_complete_valid_R1_arms=int(done),baseline_replayed=False,invalid_hybrid_not_counted_as_R1=True,prior_failed_attempts_preserved=str(ARCHIVE)))
 if not done:print('R1_SAVED_AT_BUDGET',flush=True);return
 assert r.r1_enabled and r.planning.__func__ is R.Runner.planning
 print('VALID_R1_DIAG_DONE',str(r.accounts['B'].current_nav),'R1_previews',len(r.r1_previews),'R1_reserved',len(r.r1_reservations),flush=True)
if __name__=='__main__':main()
