"""Read-only checkpoint/financial verification; never calls a financial event."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
import json, argparse, pickle
import provider_fix1 as F
P=F.P;E=F.E;HERE=Path(__file__).resolve().parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def check_json(p):
 x=read(p);a=x['account'];b=a['balance'];fills=a['fills']
 flows=sum((D(f['gross_cny'])*(1 if f['side']=='sell' else -1) for f in fills),Z)
 fees=sum((D(f['fees_cny']) for f in fills),Z)
 income=sum((D(z['dividend']) for z in a['layers']),Z)
 inventory=sum((D(z['qty'])*D(a['market_marks'][z['sid']]) for z in a['layers']),Z)
 reserved=sum((D(o['remaining_budget_cny'])+D(o['fee_reserved_cny']) for o in a['buys'].values()),Z)
 quantities=defaultdict(int)
 for z in a['layers']:quantities[z['sid']]+=z['qty']
 native={sid:sum(lot['shares'] for lot in q['lots']) for sid,q in a['native_inventory'].items()}
 assert {s:q for s,q in quantities.items() if q}=={s:q for s,q in native.items() if q}
 diffs=dict(nav_journal=D(b['nav'])-(D(1000000)+flows-fees+income+inventory),
   cash_journal=D(b['available'])+D(b['order_reserved'])+D(b['sale_receivable'])-(D(1000000)+flows-fees+income-D(b['dividend_receivable'])),
   layer_cash=sum((D(z['cash']) for z in a['layers']),Z)-(flows-fees),
   native_equity=D(b['nav'])-(D(b['available'])+D(b['order_reserved'])+D(b['sale_receivable'])+D(b['dividend_receivable'])+inventory),
   order_reserved=D(b['order_reserved'])-reserved,fee_sum=D(b['fees_cny'])-fees,inventory=D(b['inventory'])-inventory)
 assert all(v==0 for v in diffs.values()),(str(p),diffs)
 assert all(E.iso(v)<=E.iso(x['last_completed']) for v in a['market_asof'].values())
 return {k:str(v) for k,v in diffs.items()}
def restore_check(p):
 side=read(p.with_suffix('.provenance.json'));cls=pickletools_class(p)
 r=cls.restore(p);r.assert_observers();at=r.last_completed_event
 output=p.with_suffix('.json');saved=read(output)
 encoded=json.loads(json.dumps(r.observable(at),default=E.encode))
 assert encoded==saved,'restored full observable mismatch '+str(p)
 assert P.sha(p)==side['checkpoint_sha256']
 return dict(file=str(p.relative_to(HERE)),checkpoint_sha256=P.sha(p),cursor=str(at),full_observable_equal=True,source_identity_verified=True,account_bridge_verified=True,financial_events_executed=0)
def pickletools_class(p):
 # Provenance type chooses the exact original vs explicitly repaired class.
 with p.open('rb') as f:r=pickle.load(f)
 cls=type(r)
 assert cls in (P.HistoricalRunner,F.FixedRunner)
 return cls
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 paths=[]
 for root in ('2022-C10','2022-C10-recovered','2022-C_BATCH20','2025_26-C10','2025_26-C_BATCH20'):
  for p in sorted((HERE/'runs'/root).glob('20*-*.pkl')):
   if p.with_suffix('.json').exists():paths.append(p)
 rows=[]
 for p in paths:rows.append(dict(**restore_check(p),independent_differences=check_json(p.with_suffix('.json'))))
 E.IO.write_json(a.out/'SAVED_STATE_CHECKS.json',dict(passed=True,saved_states=len(rows),checks_per_state=7,share_bridge=True,asof_marks_verified=True,rows=rows,financial_events_executed=0))
 print(json.dumps(dict(passed=True,saved_states=len(rows),financial_events_executed=0)))
if __name__=='__main__':main()
