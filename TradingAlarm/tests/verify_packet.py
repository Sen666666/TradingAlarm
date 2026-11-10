import sys,json,copy
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'TradingAlarm'))
from desk.data import MarketData
from desk.strategy import packet,build_report
from desk.admission import eligibility
m=MarketData('/tmp/tradingalarm-contract-readonly')
sys.path[:0]=[str(root/'research_rounds/actual-risk-recovery-20261027/code'),str(root/'research_rounds/tech-finite-compound-20261026/code')]
import run_v2 as runner,engine
nr=root/'research_rounds/e0-reclaim-accounts-20261026/prepared';runner.PREP=nr;engine.PREP=nr
b,market=runner.context();facts=engine.Facts(b,market)
receipts=[]
for day in ['2024-09-27','2025-10-20','2026-07-17','2026-10-26']:
 c,ss,sectors,_=packet(m,day);oldc,oldss,oldsectors=facts.packet(c.decision_at,'I')
 new={s.security_id:eligibility(s,{x.sector_id:x for x in sectors},c,'S0') for s in ss}
 old={s.security_id:runner.admission.eligibility(s,{x.sector_id:x for x in oldsectors},oldc,'S0') for s in oldss}
 diffs=[]
 for sid in new:
  if new[sid].q!=old[sid].q:diffs.append((sid,new[sid].q,old[sid].q,new[sid].reasons,old[sid].reasons))
 assert not diffs,diffs
 quotes=engine.LazyQuotes(market,c.decision_at);a=runner.ledger.SectorAccount()
 def factory(**kw):return runner.admission.decide(clock=oldc,variant='S0',securities=oldss,sectors=oldsectors,**kw)
 ack=runner.ledger.commit_cutoff(a,decision_factory=factory,clock=oldc,quotes=quotes,marks={},bootstrap=True)
 subset=copy.copy(m);subset.as_of=day;subset.recovery=m.recovery.loc[:day]
 report=build_report(subset,dict(initial_cash='1000000',started_on=day),[])
 buys=[x for x in report['instructions'] if x['action']=='BUY']
 assert tuple(x['symbol'] for x in buys)==ack.accepted,(day,'allocator selection')
 for guide in buys:
  order=a.buys[guide['symbol']]
  assert guide['shares']==order.remaining_shares,(day,'quantity')
  assert runner.ledger.dec(guide['max_gross'])==order.budget_cny,(day,'gross budget')
  assert runner.ledger.dec(guide['estimated_fee'])==order.fee_reserved_cny,(day,'fee reservation')
 receipts.append(dict(day=day,stock_eligibility_exact=len(new),selected=list(ack.accepted),budgets_and_quantities_exact=True))
 print(day,'new eligible',sum(x.q is True for x in new.values()),'old',sum(x.q is True for x in old.values()),'diffs',len(diffs),diffs[:4],flush=True)

(root/"TradingAlarm/packet-verification.json").write_text(json.dumps(dict(passed=True,receipts=receipts,new_fills=0,new_backtests=0),indent=2))
