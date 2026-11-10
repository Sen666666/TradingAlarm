"""Physical source truncation and checkpoint continuation; fixed short CASE only."""
from types import SimpleNamespace
from pathlib import Path
import time
import launch_v3 as L
J=L.J;W=L.W

def observable(r):
 return W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,
  balances=r.balance_audit,accounts={k:dict(trades=a.trades,audit=a.audit_log,layers=a.layers,metadata=a.jmeta,
   journal=a.journal,orders=a.buys,positions=a.positions,available=a.available,
   budget=dict(sectors=a.budget.sectors,orders=a.budget.orders,lots=a.budget.lots,
    consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))

def main():
 t=time.monotonic();r,status=L.preflight('case');root=J.O/'prefix-engineering';cut='2025-07-07'
 assert r.run_prepared(root/'full-input',60,end=cut)
 shared=W.physical((r.bundle,r.market,r.facts),cut)
 receipts={s:{d:x for d,x in rows.items() if d<=cut} for s,rows in r.receipts.items()}
 cp={s:f.loc[:cut] for s,f in r.cp.items()};states={s:[x for d,x in rows.items() if d<=cut] for s,rows in r.industry_rows.items()}
 industry={k:v for k,v in r.industry_cp.items() if v['confirmed_day']<=cut}
 p=J.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=industry)
 p.run(end=cut,begin=J.START,max_seconds=60)
 assert observable(r)==observable(p),'full-input prepared loop vs original physical-prefix loop'
 checkpoint=root/'full-input/checkpoint.pkl';after=L.read(root/'full-input/checkpoint.json')['at']
 after=J.M.N.iso(after)
 assert r.run_prepared(root/'continuous-next',60,resume_after=after,end='2025-07-09')
 restored=L.PreparedRunner((r.bundle,r.market,r.facts),r.receipts,stock_cp=r.cp,
  industry_states={s:list(rows.values()) for s,rows in r.industry_rows.items()},industry_receipts=r.industry_cp)
 restored.source_freeze=status['freeze'];same=restored.restore(checkpoint);assert same==after
 assert restored.run_prepared(root/'restored-next',60,resume_after=same,end='2025-07-09')
 assert observable(r)==observable(restored),'saved restart continuation differs'
 L.save(J.O/'PREFIX_GATE.json',dict(passed=True,physical_prefix=cut,restart_suffix=['2025-07-08','2025-07-09'],
  original_event_loop_and_prepared_resume_loop_exact=True,all_trade_order_cash_budget_events_exact=True,
  market_input_physical_truncation=True,checkpoint_restored_without_cash_or_stage_reset=True,
  seconds=time.monotonic()-t,adapter_sha256=L.sha(J.O/'joint_v3.py'),launcher_sha256=L.sha(J.O/'launch_v3.py'),
  purpose='engineering short segment, not another policy experiment',full_account_economic_paths=0))
 print('PREFIX_AND_RESTART_PASS',time.monotonic()-t,flush=True)

if __name__=='__main__':main()
