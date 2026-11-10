"""One authorized B_diag normal path; no lot exception or risk parameter sweep."""
from pathlib import Path
import gzip,json,pickle,shutil,time
import adapter as A
L=A.L;J=A.J;O=A.O;OUT=O/'run'

def observable(r):
 return J.W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,
  balances=r.balance_audit,accounts={k:dict(trades=a.trades,layers=a.layers,metadata=a.jmeta,audit=a.audit_log,
   journal=a.journal,buys=a.buys,positions=a.positions,available=a.available,
   budget=dict(sectors=a.budget.sectors,orders=a.budget.orders,lots=a.budget.lots,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))

class Pair(A.Runner):
 def checkpoint(self,out,last_event):
  super().checkpoint(out,last_event);out=Path(out);day=str(last_event.date())
  if day in ('2025-09-30','2025-12-31','2026-03-31'):
   for suffix in ('pkl','json'):shutil.copy2(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))

def main():
 assert L.read(O/'SYNTHETIC_GATE.json')['passed'];assert L.read(O.parent/'minimum-unit-v4-draft-20261031/COMPLETION.json')['draft_completed']
 assert not (OUT/'DONE.json').exists(),'completed diagnostic arm is never rerun'
 started=time.monotonic();shared,receipts,cp,states,ir,identity=L.inputs('universe')
 r=Pair(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 sources=[O/'adapter.py',O/'model_without_account_check.py',O/'route_without_account_check.py',Path(__file__),J.O/'joint_v3.py',J.BASE/'budget_v3/model.py',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv',J.O/'run-universe/pair/B.json.gz']
 r.source_freeze={str(p):L.sha(p) for p in sources}
 L.save(OUT/'FREEZE.json',dict(before_run=True,identity=identity,scope=[J.START,J.END],initial_cash=1000000,
  only_policy_change='remove total account nominal risk admission test in two places',original_core_risk='.0025',mobile_order_target='.02',
  v4_lot_exception=False,original_controls_and_all_other_caps=True,baseline='frozen v3 full-universe B not rerun',
  source_sha256=r.source_freeze,run_budget_seconds=600,no_risk_grid_or_new_window=True))
 prepared=time.monotonic();print('PREPARED',round(prepared-started,3),flush=True)
 cut='2025-07-07';first=time.monotonic();assert r.run_prepared(OUT/'prefix-full-source',90,end=cut);first_wall=time.monotonic()-first
 physical=J.W.physical(shared,cut);prefix=A.Runner(physical,
  {s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},stock_cp={s:f.loc[:cut] for s,f in cp.items()},
  industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},
  industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
 pstart=time.monotonic();prefix.run(end=cut,begin=J.START,max_seconds=90);assert observable(r)==observable(prefix),'single-factor physical prefix mismatch'
 prefix_wall=time.monotonic()-pstart;L.save(OUT/'PREFIX_GATE.json',dict(passed=True,cut=cut,new_policy_full_source_vs_physical_prefix_exact=True,
  no_old_B_replay=True,engineering_prefix_seconds=prefix_wall,first_segment_is_continued_same_new_arm=True))
 after=J.M.N.iso(cut+'T15:10:00+08:00');print('PREFIX_PASS',round(first_wall,3),round(prefix_wall,3),'fills',len(r.accounts['B'].trades),flush=True)
 del prefix
 rest=time.monotonic();done=r.run_prepared(OUT,max(1,600-first_wall-prefix_wall),resume_after=after)
 if not done:
  L.save(OUT/'BUDGET_SAVED.json',dict(completed=False,checkpoint=str(OUT/'checkpoint.pkl'),same_path_can_continue=True));print('SAVED_AT_BUDGET',flush=True);return
 L.save(OUT/'TIMING.json',dict(preparation_seconds=prepared-started,
  first_segment_wall_seconds=first_wall,physical_prefix_extra_wall_seconds=prefix_wall,
  continuation_replay_audit_save_wall_seconds=time.monotonic()-rest,total_wall_seconds=time.monotonic()-started,
  new_complete_economic_arms=1,original_A_or_B_replayed=False))
 print('B_DIAG_DONE',str(r.accounts['B'].current_nav),flush=True)

if __name__=='__main__':main()
