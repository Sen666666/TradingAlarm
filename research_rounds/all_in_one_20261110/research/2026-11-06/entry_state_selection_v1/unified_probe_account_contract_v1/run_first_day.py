"""Bounded engineering check only: original empty account, Jan 4-5 2022."""
from pathlib import Path
import sys,copy,json,hashlib,time,traceback
from datetime import datetime,time as dtime
from decimal import Decimal as D
import unified_probe as U
sys.path.insert(0,str(U.BASE/'no_loss_add_v1'))
import run_no_loss_add as R
C,A,N,J,L,IO=R.C,R.A,R.N,R.J,R.L,R.IO
HERE=Path(__file__).resolve().parent

def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--out',default='first_day_check');args=parser.parse_args()
 assert '/' not in args.out and args.out not in ('.','..')
 out=HERE/args.out;assert not out.exists(),'No overwrite or automatic rerun'
 out.mkdir();started=time.monotonic();r=None;last=None;normal_open_completed=False
 R.save(out/'STARTED.json',dict(status='RUNNING',scope='bounded Jan4-5 engineering only',full_window_run=False))
 try:
  hashes=U.source_hashes();print('LOAD_CONTINUOUS_INPUTS',flush=True)
  shared,receipts,cp,states,ir,identity=C.inputs();print('INPUTS_READY',round(time.monotonic()-started,2),flush=True)
  bundle,original_market,original_facts=shared
  timelines={sid:R.OpenFactorTimeline(raw,original_market.actions.get(sid,[]),method=bundle.series[sid].record['adjustment']['method'],end=C.END) for sid,raw in original_market.raw.items() if not raw.empty}
  factors=R.FactorSource(timelines)
  r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
  a=r.accounts['B'];assert not a.positions and not a.trades and not a.budget.lots
  a.available=R.CAPITAL;a.initial_cash=R.CAPITAL;a.current_nav=R.CAPITAL;a.minimum_available=R.CAPITAL;a.budget.cash=float(R.CAPITAL);a.risk_state=dict(on=True,peak=R.CAPITAL,saw_off=False,previous_fast=False,episode=0);a.label='PVR';r.accounts={'PVR':a}
  U.install(r)
  m,f=R.attach(original_market,original_facts,factors,J.C.L);r.market=m;r.facts=f;a.market=m;a.facts=f;r.open_checks=[]
  r.source_freeze=A.source_freeze();r.source_freeze.update(hashes)
  for p in [Path(__file__),HERE/'CONTRACT.md',HERE/'test_unified.py',U.BASE/'continuous_execution.py',U.BASE/'factors/continuous_factors.py',U.BASE/'inputs/continuous_inputs.py']:
   r.source_freeze[str(p)]=R.sha(p)
  for p,h in N.SCORES.source_manifest_sha256.items():r.source_freeze[p]=h
  J.M.E.risk_policy.RECOVERY=R.pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:C.END]
  lo=J.M.N.iso('2022-01-01T00:00:00+08:00');hi=J.M.N.iso('2022-01-05T15:10:00+08:00')
  opens={x for x in m.sessions['A'] if lo<=x<=hi};closes={x for x in m.cutoffs if lo<=x<=hi}
  actions={datetime.combine(datetime.fromisoformat(d).date(),dtime.min,J.M.N.TZ) for d in r.actions_by_date}
  events=sorted(opens|closes|{x for x in actions if lo<=x<=hi})
  R.save(out/'PREDECLARED.json',dict(scope='two trading day engineering/first entry check only, not economic validation',window=['2022-01-01','2022-01-05'],real_orders=False,source_freeze=r.source_freeze,input_identity=identity,contract=str(HERE/'CONTRACT.md')))
  gate=False
  with IO.atomic_runner_outputs(r,L,out,canonicalize=R.canon):
   for at in events:
    if at in opens and str(at.date())=='2022-01-05':
     assert last is not None
     r.checkpoint(out/'restart_gate',last);cpfile=out/'restart_gate/checkpoint.pkl';nexec=len(m.exec_rows);counts=copy.copy(m.exec_counts)
     R.event(r,m,at,opens,closes,None);normal=R.digest(R.payload(r));normal_open_completed=True
     R.save(out/'NORMAL_OPEN_COMPLETED.json',dict(at=at,payload_sha256=normal,buy_fills=len(r.accounts['PVR'].trades),admission_events=r.admission_events))
     r.restore(cpfile);m.exec_rows=m.exec_rows[:nexec];m.exec_counts=counts
     needed=set().union(*(set(a.positions)|set(a.exits)|{i['sid'] for i in a.pending} for a in r.accounts.values()));assert needed
     backup=R.poison_future(m,at,needed)
     try:
      R.event(r,m,at,opens,closes,None);poisoned=R.digest(R.payload(r));assert normal==poisoned,'future HLCV or restart dependency'
     finally:R.unpoison(backup)
     R.save(out/'RESTART_OPEN_PERTURB_GATE.json',dict(passed=True,normal_sha256=normal,restored_poison_sha256=poisoned,stocks=len(needed),at=at,scope='entire mutable runner/account payload'))
     gate=True
    else:R.event(r,m,at,opens,closes,None)
    last=at;print('EVENT_DONE',str(at),flush=True)
   assert gate;r.checkpoint(out/'latest_checkpoint',last);r.dump_joint(out/'pair')
  a=r.accounts['PVR'];reserve=[x for x in a.journal if x['kind']=='real_reserve'];fills=[x for x in a.journal if x['kind']=='real_buy_fill']
  assert fills and all(x['pool']=='probe' for x in reserve+fills)
  assert all(x['pool']=='probe' for x in a.jmeta.values()) and all(x.pool=='probe' for x in a.budget.lots)
  assert not [e for e in r.promotion_events if e['moved']]
  for e in r.admission_events:
   assert e['flat'] and e['gross']<=D(e['decision_nav'])*D('.02') and e['fee_inclusive_risk']<=D(e['decision_nav'])*D('.0025')
   assert e['probe_after'][0]<=.10*e['budget_nav']+1e-6 and e['probe_after'][1]<=.005*e['budget_nav']+1e-6
  for p,h in r.source_freeze.items():assert R.sha(p)==h,('source drift',p)
  close=r.daily[-1];summary=dict(passed=True,scope='FIRST_DAY_ENGINEERING_ONLY_NOT_ECONOMIC_VALIDATION',unique_first_stocks=len({x['sid'] for x in fills}),first_buy_fills=len(fills),first_reserves=len(reserve),role_counts=dict(R.Counter(x['role'] for x in fills)),gross=str(sum((D(x['shares'])*x['price'] for x in fills),D(0))),fees=str(sum((x['fees'] for x in fills),D(0))),close_nav=str(close['nav']),close_inventory=str(close['inventory']),close_inventory_fraction=float(close['inventory']/close['nav']),close_probe=close['pool_probe'],close_confirmed=close['pool_confirmed'],promotion_count=len(r.promotion_events),funding_rejections=dict(R.Counter(x['result'] for x in r.funding if x['result']!='reserved')),original_source_files_unchanged=True,real_orders=False,full_window_run=False,seconds=time.monotonic()-started,implementation_sha256=R.sha(HERE/'unified_probe.py'))
  R.save(out/'SUMMARY.json',summary);R.save(out/'ADMISSION_EVENTS.json',r.admission_events);R.save(out/'PROMOTION_EVENTS.json',r.promotion_events);R.save(out/'OPEN_CASH_CHECKS.json',r.open_checks);R.save(out/'DONE.json',dict(completed=True,last_event=last,summary='SUMMARY.json'))
  print(json.dumps(summary,default=str,indent=2),flush=True)
 except BaseException as exc:
  R.save(out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),last_complete_event=last,normal_open_completed=normal_open_completed,partial_event_not_resumable=True,automatic_rerun=False))
  if r is not None:R.IO.write_pickle(out/'PARTIAL_STATE_DIAGNOSTIC_ONLY.pkl',dict(status='FAILED_EVENT_NOT_A_RESUMABLE_CHECKPOINT',payload=R.payload(r)))
  raise
if __name__=='__main__':main()
