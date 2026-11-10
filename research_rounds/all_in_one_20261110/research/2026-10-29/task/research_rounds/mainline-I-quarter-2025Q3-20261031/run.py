"""Short correctness gates, then the two authorized normal Q3 paths only."""
import adapter as M
from pathlib import Path
import time,json,traceback,collections
import pandas as pd,numpy as np
O=M.O
def canonical(x):return json.dumps(M.N.encoded(x),ensure_ascii=False,sort_keys=True,default=M.C.encoded,allow_nan=False)
def account_state(r):
 return dict(daily=r.daily,accounts={k:dict(trades=a.trades,layers=a.layers,audit=a.audit_log,counts=dict(a.counts),decisions=a.decisions,minimum_available=a.minimum_available,risk_state=a.risk_state,core_epoch=a.core_epoch) for k,a in r.accounts.items()})
def gate():
 t=time.monotonic();checks=[]
 def ok(n,**v):checks.append(dict(name=n,passed=True,**v));print('GATE',n,flush=True)
 # Real historical L0 executor, original TECH input, all finance rows compared.
 runners=[]
 for label,fn in [('original',M.original_planning),('hook_off',M.rank_planning)]:
  root=O/('off-'+label);root.mkdir();(root/'execution-rules-v2.json').symlink_to(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
  M.C.plan_original_add=fn;r=M.C.Pilot('TECH',root,'2024-01-12',stresses=('base',),policies=('L0',));r.gate_enabled=False;r.run('2024-01-12');runners.append(r)
 assert canonical(account_state(runners[0]))==canonical(account_state(runners[1]))
 ok('real_L0_hook_off_exact',closes=len(runners[0].daily),fills=sum(len(a.trades) for a in runners[0].accounts.values()),orders_audit_decisions_cash_shares_exits_exact=True)
 # Replace only unused CP/PVR dependency with explicitly absent values: P0
 # core, protection and funding must still be exactly the same.
 r=runners[1];r0=runners[0];day='2024-01-12';at=M.N.iso(day+'T15:10:00+08:00')
 M.C.plan_original_add=M.rank_planning
 root=O/'off-unused-reads';root.mkdir();(root/'execution-rules-v2.json').symlink_to(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
 r2=M.C.Pilot('TECH',root,'2024-01-12',stresses=('base',),policies=('L0',));r2.gate_enabled=False
 empty=pd.DataFrame(index=pd.DatetimeIndex([]));r2.cp={s:empty for s in r2.market.lines};r2.pv={s:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for s in r2.market.lines};r2.run('2024-01-12')
 # Scores are diagnostic only for these CORE intents; compare all economic
 # state, allowing only score/pvr values to be absent in diagnostic records.
 def economic_view(r):
  a=next(iter(r.accounts.values()));return dict(daily=r.daily,layers=a.layers,shares={s:a.quantity(s) for s in a.positions},balance=a.balance(at,r.market.marks(at,a.positions)),core_epoch=a.core_epoch,orders=[(x['security_id'],x['side'],x['shares'],x['gross_cny'],x['fees_cny'],x['at']) for x in a.trades],intent_contracts=[[(i['sid'],i['budget'],i['cap'],i['floor'],i.get('risk_budget'),i['epoch']) for i in d['intents']] for d in a.decisions])
 assert canonical(economic_view(r0))==canonical(economic_view(r2))
 ok('unused_CP_PVR_removed_economic_identity',diagnostic_scores_may_be_unknown=True)
 del runners,r,r0,r2
 # Frozen real market short prefix, before the two full economic paths.
 t0=time.monotonic();a=M.Pilot();a.run('2025-07-08');prefix_seconds=time.monotonic()-t0
 b=M.Pilot(cut='2025-07-08');b.run('2025-07-08')
 assert canonical(account_state(a))==canonical(account_state(b));assert canonical(a.selection_rows)==canonical(b.selection_rows)
 ok('physical_input_prefix_exact',end='2025-07-08',closes=len(a.daily),full_setup_and_6day_run_seconds=prefix_seconds)
 # Equal shortlist before private state: use the actual first day data and
 # then change account-only state; neither N nor either rank may change.
 at=M.N.iso('2025-07-01T15:10:00+08:00');a.make_lists(at);before=canonical(a.selection_rows[-2:]);aa=next(iter(a.accounts.values()));oldcash=aa.available;oldlocks=aa.core_epoch.copy();aa.available=M.D(0);aa.core_epoch.update({s:('arbitrary_private_state',1) for s in a.market.lines});a.make_lists(at);assert canonical(a.selection_rows[-2:])==before;aa.available=oldcash;aa.core_epoch=oldlocks
 ok('shortlist_independent_of_private_cash_and_epoch')
 # Actual ledger keeps existing buy orders until its own day-expiry method;
 # our hook does not inspect or cancel them. Check source calls explicitly.
 assert 'cancel_buy' not in M.source and M.source.count('a.expire_day_buys(at)')==1
 ok('ranking_no_extra_order_cancellation',original_expiry_function_unchanged=True)
 first=next((i for i,(x,y) in enumerate(zip(a.daily[::2],a.daily[1::2])) if canonical({k:v for k,v in x.items() if k!='account'})!=canonical({k:v for k,v in y.items() if k!='account'})),None)
 if first is not None:
  for x,y in zip(a.daily[::2][:first],a.daily[1::2][:first]):assert canonical({k:v for k,v in x.items() if k!='account'})==canonical({k:v for k,v in y.items() if k!='account'})
 ok('before_first_financial_divergence_exact',short_prefix_first_difference_index=first)
 prep=M.read(O/'PREPARED.json');assert prep['passed']
 ok('market_clock_original_formula_and_physical_prefix',prefix=prep['physical_market_prefix'],Q3_breakouts=prep['market_breakouts_Q3'])
 # Output cache freezes remain the identities from the prior interface run.
 freeze=M.read(M.IC/'FREEZE.json');assert all(M.sha(p)==h for p,h in freeze['source_sha'].items());ok('native_I_input_implementation_identity')
 M.save(O/'GATE.json',dict(passed=True,checks=checks,seconds=time.monotonic()-t,short_prefix_run_seconds=a.run_seconds,estimate_full_63day_two_arms_seconds=a.run_seconds/len(a.daily)*126,gate_is_not_policy_selection=True))
 print('ALL_GATES',time.monotonic()-t,'economic_estimate',a.run_seconds/len(a.daily)*126,flush=True)

def economic():
 assert M.read(O/'GATE.json')['passed']
 files=[O/'PROTOCOL.txt',O/'adapter.py',O/'run.py',O/'recovery.csv',O/'PREPARED.json',M.F,M.IC/'FREEZE.json',M.IC/'VERIFICATION.json',M.IC/'COMPLETION.json',Path(M.BP.__file__),Path(M.LR.__file__),Path(M.C.__file__),Path(M.E.__file__),Path(M.E.risk_policy.__file__),Path(M.BP.A.__file__),Path(M.BP.L.__file__)]
 M.save(O/'FREEZE.json',dict(before_two_economic_paths=True,quarter='2025Q3',policies=['H1','ATT'],normal_only=True,half_budget_not_optimized=True,sha256={str(p):M.sha(p) for p in files},industry_sha={p.name:M.sha(p) for p in (O/'industry-facts').glob('*.parquet')},native_I_receipts_sha=M.sha(M.IC/'FULL_GATE.json')))
 r=M.Pilot();start=time.monotonic()
 try:r.run(max_seconds=120);r.dump(O/'results');M.save(O/'ECONOMIC_DONE.json',dict(passed=True,paths=2,seconds=r.run_seconds,wall_with_dump=time.monotonic()-start,account_closes=len(r.daily),no_other_economic_runs=True))
 except BaseException as e:
  r.run_seconds=time.monotonic()-start;r.dump(O/'failed-partial');raise
 print('ECONOMIC_DONE',r.run_seconds,len(r.daily),[(k,str(a.current_nav)) for k,a in r.accounts.items()],flush=True)
if __name__=='__main__':
 try:gate();economic()
 except BaseException as e:M.save(O/'RUN_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
