"""Continue the one R1 account after an artifact mkdir failure, no trade change."""
import time
from pathlib import Path
import adapter_r1 as R
from run_one import Pair,observable
L=R.L;J=R.J;O=R.O;OUT=O/'run'
def main():
 assert not (OUT/'DONE.json').exists()
 original=L.read(OUT/'FREEZE.json');frozen=original['sources']
 for path,sha in frozen.items():assert L.sha(path)==sha,('source changed before technical resume',path)
 started=time.monotonic();shared,receipts,cp,states,ir,identity=L.inputs('universe')
 assert identity==original['identity']
 r=Pair(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=frozen
 after=r.restore(OUT/'prefix-full-source/checkpoint.pkl');cut='2025-07-07';assert str(after.date())==cut
 prepared=time.monotonic();print('RESUME_PREPARED',round(prepared-started,3),'checkpoint',str(after),flush=True)
 # Only repeat the lost, tiny physical-prefix artifact. The full-source account
 # prefix is restored, not rerun, and will be continued without reinitializing.
 physical=J.W.physical(shared,cut);prefix=R.Runner(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
 t=time.monotonic();prefix.run(end=cut,begin=J.START,max_seconds=90);assert observable(r)==observable(prefix)
 target=OUT/'prefix-physical-source/pair';target.mkdir(parents=True,exist_ok=True);prefix.dump_joint(target);prefix_seconds=time.monotonic()-t
 L.save(OUT/'PREFIX_GATE.json',dict(passed=True,cut=cut,both_sides_saved=True,exact_observable_assertion=True,original_B_diag_not_replayed=True,restored_full_source_prefix=True,physical_prefix_seconds=prefix_seconds))
 print('RESUMED_PREFIX_PASS',round(prefix_seconds,3),'R1 reservations',len(r.r1_reservations),flush=True);del prefix
 t=time.monotonic();done=r.run_prepared(OUT,420,resume_after=after)
 L.save(OUT/'TIMING.json',dict(first_attempt_preparation_seconds=76.054,resume_preparation_seconds=prepared-started,restored_prefix_no_replay=True,physical_prefix_artifact_rebuild_seconds=prefix_seconds,continuation_audit_save_seconds=time.monotonic()-t,resume_total_seconds=time.monotonic()-started,first_attempt_artifact_failure_preserved=True,new_complete_arms=int(done),baseline_replayed=False))
 if not done:print('R1_SAVED_AT_BUDGET',flush=True);return
 print('R1_DIAG_DONE',str(r.accounts['B'].current_nav),'R1_reserved',len(r.r1_reservations),flush=True)
if __name__=='__main__':main()
