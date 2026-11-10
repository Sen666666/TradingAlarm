"""Thin arithmetic/source validation, no trading/replay."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
xs=json.loads((O/'COMPLETE_ORIGINAL_CHAINS.json').read_text());src=json.loads((O/'SOURCE_MANIFEST.json').read_text())['source_sha256']
checks=[]
def eq(a,b,k):
 assert abs(D(str(a))-D(str(b)))<D('.000001'),(k,a,b)
 checks.append(k)
def total(xs):return sum((D(str(x)) for x in xs),D(0))
for c in xs:
 cc=c['campaign'];es=c['entries'];sid=cc['sid'];cid=cc['campaign_id']
 assert len(es)==len(cc['layer_ids']) and len({e['layer'] for e in es})==len(es)
 eq(total(e['actual_layer_accounting']['cost'] for e in es),cc['actual_buycash'],cid+' buycash')
 sell=total(p['net_cash'] for e in es for p in e['actual_layer_accounting']['actual_sale_parts'])
 eq(sell-D(cc['actual_buycash']),cc['strict_realized'],cid+' cash realized')
 eq(total(e['actual_layer_accounting']['net'] for e in es),cc['endpoint_net'],cid+' recognized wealth')
 for e in es:
  a=e['original_signal_and_authorization'];o=next(o for o in c['observations'] if o['day']==a['decision_at'][:10])
  assert o['fact_source_day']==a['decision_at'][:10]
  eq(o['stock']['close'],a['original_stock_state']['close'],str(e['layer'])+' signal close')
  assert o['stock']['i_target']==1
  if a['role']=='mobile':
   p=e['original_CP_and_scale_proof']['CP1_canonical_trace']
   assert p and not p['trace_unknown'] and p['new_advance_price_event_ids'] and p['receipt_id']==a['receipt']
  assert e['actual_buy']['at'][:10]>a['decision_at'][:10]
 t=c['local_diagnostic_trigger']['first_negative_native_event_after_actual_first_fill']
 assert cc['opened'][:10]<=t<cc['closed'][:10]
 assert next(o for o in c['observations'] if o['day']==t)['native_event']['event']==-1
for p,h in src.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
out=dict(status='PASS_THIN_ARITHMETIC_AND_SOURCE_CHECK',cycles=len(xs),actual_entry_decisions=sum(len(c['entries']) for c in xs),CLOSE_observations=sum(len(c['observations']) for c in xs),mobile_receipts_with_positive_new_frontier_and_no_unknown=sum(e['original_signal_and_authorization']['role']=='mobile' for c in xs for e in c['entries']),sources_rehashed_unchanged=len(src),checks=len(checks),new_accounts=0,model_replays=0,limitation='thin independent recomputation of cash/wealth/clock/source identity; not a separate-agent economic review or execution counterfactual')
(O/'THIN_VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
