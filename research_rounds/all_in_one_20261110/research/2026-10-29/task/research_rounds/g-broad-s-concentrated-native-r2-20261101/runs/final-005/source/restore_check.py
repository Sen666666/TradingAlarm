"""Cross-process identity/financial/evidence state readback, no new events."""
import sys
from pathlib import Path
from datetime import datetime
from native_capital import SyntheticRunner,digest,LR
from imports_native import IO,T,quantity,fees
r=SyntheticRunner.restore(Path(sys.argv[1]));at=datetime.fromisoformat(sys.argv[3])
result=dict(digest=digest(r.account.exported(at)),contract=r.binding()['contract'],cross_process=True,new_account_events=0)
if len(sys.argv)>4:
 next_at=datetime.fromisoformat(sys.argv[4]);a=r.account;sid=next(iter(a.exits));p=a.market.prices[sid]
 w=T.window(sid,p*(1-LR.SLIP),next_at,50,fees=fees(next_at,a.market.stars[sid]),rule=quantity(next_at,a.market.stars[sid]),eid='cross-process-next-sell',raw_open=p,cash_due_at=next_at)
 a.fill_exit(sid,w);a.settle_due(next_at);result.update(continued_digest=digest(a.exported(next_at)),new_account_events=2)
IO.write_json(Path(sys.argv[2]),result)
