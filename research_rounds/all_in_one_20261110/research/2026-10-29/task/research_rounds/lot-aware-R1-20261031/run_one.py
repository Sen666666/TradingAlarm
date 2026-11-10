"""One frozen R1_diag normal path; no old-account or parameter rerun."""
from pathlib import Path
import json,shutil,time,difflib
import adapter_r1 as R
L=R.L;J=R.J;O=R.O;OUT=O/'run'
def observable(r):
 return J.W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,
  balances=r.balance_audit,r1_previews=r.r1_previews,r1_reservations=r.r1_reservations,
  accounts={k:dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,audit=a.audit_log,journal=a.journal,
   buys=a.buys,positions=a.positions,available=a.available,budget=dict(sectors=a.budget.sectors,orders=a.budget.orders,lots=a.budget.lots,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))
class Pair(R.Runner):
 def checkpoint(self,out,last_event):
  super().checkpoint(out,last_event);out=Path(out);day=str(last_event.date())
  if day in ('2025-09-30','2025-12-31','2026-03-31'):
   for suffix in ('pkl','json'):shutil.copy2(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
 def dump_joint(self,path):
  super().dump_joint(path)
  L.save(Path(path).parent/'R1_AUDIT.json',dict(opening_eligible_previews=self.r1_previews,actual_reservations=self.r1_reservations,
   actual_fills_must_join_canonical_CP1=True,unfilled_is_not_filled=True))
def main():
 assert L.read(O/'SYNTHETIC_GATE.json')['passed']
 assert not (OUT/'DONE.json').exists(),'completed arm is never rerun'
 R.save_source_views()
 for n,old,new in [('planning',R.method_source(J.Runner.planning),R.PLANNING),('opening',R.method_source(J.Runner.opening),R.OPENING),('route',(R.BASE.O/'route_without_account_check.py').read_text(),R.ROUTE_DIAG)]:
  (O/(n.upper()+'_DIFF.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='frozen_B_diag_'+n,tofile='R1_diag_'+n)))
 started=time.monotonic();shared,receipts,cp,states,ir,identity=L.inputs('universe')
 r=Pair(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 files=[Path(__file__),O/'adapter_r1.py',O/'test_adapter_r1.py',O/'CONTRACT.txt',O/'planning_r1.py',O/'opening_r1.py',O/'route_r1_diag.py',R.BASE.O/'adapter.py',R.BASE.O/'model_without_account_check.py',R.BASE.O/'route_without_account_check.py',R.BASE.O/'run/pair/B.json.gz',J.O/'joint_v3.py',J.BASE/'budget_v3/model.py',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv']
 r.source_freeze={str(p):L.sha(p) for p in files}
 L.save(OUT/'FREEZE.json',dict(before_run=True,identity=identity,dates=[J.START,J.END],initial_cash=1000000,
  only_policy_change='R1 full normal2% target below one opening minimum; exactly one confirmed unit, gross<=4% frozen decisionNAV',
  baseline='completed B_diag; not rerun',baseline_account_nominal_risk_check=False,
  sources=r.source_freeze,all_original_signals_stages_ranking_exits_and_other_caps=True,normal_daily_proxy=True,
  run_budget_seconds=450,missing_and_snapshot_limits_inherited=True))
 prep=time.monotonic();print('PREPARED_R1',round(prep-started,3),flush=True)
 cut='2025-07-07';t=time.monotonic();assert r.run_prepared(OUT/'prefix-full-source',90,end=cut);first=time.monotonic()-t
 physical=J.W.physical(shared,cut);prefix=R.Runner(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},
  stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
 t=time.monotonic();prefix.run(end=cut,begin=J.START,max_seconds=90);assert observable(r)==observable(prefix),'R1 physical prefix mismatch'
 prefix.dump_joint(OUT/'prefix-physical-source/pair');side=time.monotonic()-t
 L.save(OUT/'PREFIX_GATE.json',dict(passed=True,cut=cut,exact_observable_assertion=True,both_sides_saved=True,
  original_B_diag_not_replayed=True,full_source_prefix_seconds=first,physical_prefix_seconds=side))
 print('R1_PREFIX_PASS',round(first,3),round(side,3),'prefix_R1_admissions',len(r.r1_reservations),flush=True);del prefix
 after=J.M.N.iso(cut+'T15:10:00+08:00');t=time.monotonic()
 done=r.run_prepared(OUT,max(1,450-first-side),resume_after=after)
 L.save(OUT/'TIMING.json',dict(preparation_seconds=prep-started,first_segment_seconds=first,physical_prefix_seconds=side,
  continuation_audit_save_seconds=time.monotonic()-t,total_wall_seconds=time.monotonic()-started,new_complete_arms=int(done),baseline_replayed=False))
 if not done:print('SAVED_R1_CHECKPOINT',flush=True);return
 print('R1_DIAG_DONE',str(r.accounts['B'].current_nav),'R1_reserved',len(r.r1_reservations),flush=True)
if __name__=='__main__':main()
