"""Reconstruct the minimum usable cash from chronological source ledger events."""
from decimal import Decimal as D
ZERO=D(0);PAD=D('1000000000000')
def verify(log,daily,final):
 cash=PAD;minimum=cash;orders={};cash_by_time={};operations=0
 for r in log:
  k=r['kind'];at=r.get('at')
  if k=='reserve':
   fee=D(r['fee_reserved_cny']);orders[r['order_id']]=fee;cash-=D(r['gross_budget_cny'])+fee
  elif k=='release_buy':
   fee=D(r['fee_released']);assert orders.pop(r['order_id'])==fee
   cash+=D(r['gross_released'])+fee
  elif k=='fill':
   f=r['receipt'];at=f['at'];fee=D(f['fees_cny'])
   if f['side']=='buy':
    old=orders[r['order_id']];topup=max(ZERO,fee-old);cash-=topup;orders[r['order_id']]=old+topup-fee
   else:
    net=D(f['gross_cny'])-fee
    if net<0:cash+=net
  elif k=='settle':
   s=r['settlement']
   if not s['debit']:cash+=D(s['cny_amount'])
  elif k=='expense':cash-=D(r['cny_amount'])
  elif k=='dividend_payment':cash+=D(r['entitlement']['net_local'])*D(r['fx_rate'])
  else:continue
  assert cash>=0
  minimum=min(minimum,cash);cash_by_time[at]=cash;operations+=1
 assert abs(cash-D(final['available']))<D('1e-12')
 assert abs(PAD-minimum-D(final['peak_funding']))<D('1e-12')
 # Check every end-of-day available balance against event-flow reconstruction.
 from bisect import bisect_right
 times=sorted(cash_by_time)
 for d in daily:
  i=bisect_right(times,d['at'])-1;v=cash_by_time[times[i]] if i>=0 else PAD
  assert abs(v-D(d['available']))<D('1e-12'),(d['at'],v,d['available'])
 return dict(passed=True,operations=operations,peak_funding=str(PAD-minimum),daily_available_checks=len(daily),method='independent reservation,fee_topup,release,settlement,payment event replay')
