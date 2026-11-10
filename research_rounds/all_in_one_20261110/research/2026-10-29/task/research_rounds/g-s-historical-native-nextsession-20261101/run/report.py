"""Read only saved ledgers: new fills, exact layer exits, cash and price effects."""
from driver import *
from dataclasses import asdict
import collections,pickle
spec=importlib.util.spec_from_file_location('full_mutable_view_existing',OLD/'export-recovery/audit_state.py');V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)

def val(a,at):return sum((D(a.quantity(s))*a.market.native.latest_mark(s,at).raw_price for s in a.positions),Z)
def supports(a,at):
 rows=[]
 for z in a.layers:
  if not z['qty']:continue
  m=a.capital_meta[z['id']];mark=a.market.native.latest_mark(z['sid'],at).raw_price
  rows.append(dict(sid=z['sid'],layer=z['id'],role=m['role'],pool=m['pool'],origin_purpose=m['purpose'],current_A_support=a._current_holding_support(m['sector']),
   sector=m['sector'],qty=z['qty'],market_value=D(z['qty'])*mark))
 return rows

def main():
 out=HERE/'report-v2';out.mkdir(exist_ok=False);reports={}
 for k,s in SPECS.items():
  old=H.HistoricalRunner.restore(old_checkpoint(k));r=NextSessionRunner.restore(HERE/k/'close'/(s['next_day']+'-CLOSE.pkl'))
  op=NextSessionRunner.restore(HERE/k/(s['next_day']+'-OPEN.pkl'));a=r.account;day=s['next_day'];atopen=iso(day+'T09:30:00+08:00');atclose=iso(day+'T15:10:00+08:00')
  new=a.fills[len(old.account.fills):];sells=[f for f in new if f.side=='sell'];buys=[f for f in new if f.side=='buy']
  quantities=collections.Counter({sid:old.account.quantity(sid) for sid in old.account.positions});ever={z['sid'] for z in old.account.layers};classes=[]
  for f in new:
   if f.side=='sell':quantities[f.security_id]-=f.shares
   else:
    category='add' if quantities[f.security_id] else ('reentry_after_actual_flat' if f.security_id in ever else 'first_actual_participation')
    classes.append(dict(receipt=f.receipt_id,sid=f.security_id,shares=f.shares,gross=f.gross_cny,category=category));quantities[f.security_id]+=f.shares;ever.add(f.security_id)
  assert {sid:q for sid,q in quantities.items() if q}=={sid:a.quantity(sid) for sid in a.positions}
  old_exit=[]
  for eid,e in old.account.policy.locks.items():
   if not e.remaining:continue
   z=next(z for z in old.account.layers if z['id']==e.lot);floor=old.account.raw_floor(z);mark=a.market.native.latest_mark(e.sid,atopen).raw_price
   after=a.policy.locks[eid];assert after.remaining==0 and after.extinguished_event
   trade=next(t for t in a.trades if t['receipt_id']==after.extinguished_event)
   parts=[p for p in trade['parts'] if p['layer']==e.lot];assert sum(p['shares'] for p in parts)==e.remaining
   old_exit.append(dict(eid=eid,sid=e.sid,layer=e.lot,requested_qty=e.remaining,actual_parts=parts,fill_receipt=after.extinguished_event,
    known_floor_before_open=floor,opening_mark=mark,risk_charge_before_real_fill=e.charge(mark,floor),risk_charge_after_fill=Z,
    settlement_id=trade['settlement_id']))
  assert len(old_exit)==len(sells)
  sale_net=sum((f.gross_cny-f.fees_cny for f in sells),Z);buy_cost=sum((f.gross_cny+f.fees_cny for f in buys),Z)
  open_balance=op.account.balance(atopen,op.account.market.marks(atopen,op.account.positions))
  assert old.account.available+sale_net-buy_cost-open_balance['order_reserved']==op.account.available
  settlements=[]
  sale_ids={f.settlement_id for f in sells}
  for row in a.audit_log:
   if row['kind']=='settle' and row['settlement'].settlement_id in sale_ids:settlements.append(dict(at=row['at'],settlement=asdict(row['settlement'])))
  assert len(settlements)==len(sale_ids)
  pre_value=sum((D(old.account.quantity(sid))*a.market.native.latest_mark(sid,atopen).raw_price for sid in old.account.positions),Z)
  old_value=val(old.account,old.last_completed_event);sold_mark=sum((D(f.shares)*a.market.native.latest_mark(f.security_id,atopen).raw_price for f in sells),Z)
  bought_mark=sum((D(f.shares)*a.market.native.latest_mark(f.security_id,atopen).raw_price for f in buys),Z)
  assert pre_value-sold_mark+bought_mark==open_balance['inventory']
  end_balance=a.balance(atclose,a.market.marks(atclose,a.positions));passive_close=end_balance['inventory']-open_balance['inventory']
  for e in r.events:
   b=e['bridge'];assert D(b['independent_nav_difference'])==D(b['cash_asset_difference'])==D(b['layer_cash_difference'])==0
  active_locks=[dict(**asdict(e),duty=a.exit_duties[eid]) for eid,e in a.policy.locks.items() if e.remaining]
  reasons=collections.Counter(reason for row in active_locks for reason in row['duty']['reasons'])
  new_buy_sids={f.security_id for f in buys};same_day_new=[row for row in active_locks if row['sid'] in new_buy_sids]
  layers=supports(a,atclose);by_origin={};by_sector={}
  for row in layers:
   by_origin[row['origin_purpose']]=by_origin.get(row['origin_purpose'],Z)+row['market_value'];by_sector[row['sector']]=by_sector.get(row['sector'],Z)+row['market_value']
  rpt=dict(new_fills=[asdict(f) for f in new],buy_classification=classes,actual_old_exit_layers=old_exit,real_sale_net=sale_net,new_buy_cost_including_fees=buy_cost,
    sale_settlements=settlements,cash_equation_exact=True,old_close_inventory=old_value,old_holdings_marked_at_next_open=pre_value,
    passive_overnight_value_change=pre_value-old_value,active_sold_mark_value=sold_mark,active_bought_mark_value=bought_mark,
    passive_open_to_close_value_change=passive_close,open_balance=open_balance,end_balance=end_balance,
    open_exposure=open_balance['inventory']/open_balance['nav'],end_exposure=end_balance['inventory']/end_balance['nav'],
    purpose_market_values=by_origin,purpose_weights={k:v/end_balance['nav'] for k,v in by_origin.items()},sector_market_values=by_sector,
    largest_sector_weight=max(by_sector.values())/end_balance['nav'],current_holding_support_rows=layers,
    new_action_records=[x for x in r.action_log if str(x['at'])[:10]==day],payments_due_input=r.inputs.payments_due(atclose),
    current_k=list(a.policy.k),new_pending_intents=len(a.pending),pending_exit_reason_counts=dict(reasons),pending_exit_locks=active_locks,
    newly_bought_then_requested_for_allocation=same_day_new,allocation_plan=r.lifecycle[-1]['allocation'],
    actual_wealth_and_locks_continuous=True,price_and_actual_capital_changes_separated=True)
  save(out/(k+'.json'),rpt);reports[k]=dict(sells=len(sells),buys=len(buys),sale_net=sale_net,new_buy_cost=buy_cost,opening_exposure=rpt['open_exposure'],end_exposure=rpt['end_exposure'],NAV=end_balance['nav'],pending_exits=len(active_locks),pending_intents=len(a.pending),same_day_new_allocation_requests=len(same_day_new))
 save(out/'SUMMARY.json',reports);print(json.dumps(normalize(reports),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
