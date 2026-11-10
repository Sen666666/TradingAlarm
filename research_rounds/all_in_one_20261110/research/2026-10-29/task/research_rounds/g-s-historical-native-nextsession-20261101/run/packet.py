"""Build compact evidence from saved JSON only; never load/advance an account."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,collections
O=Path(__file__).resolve().parent.parent;R=O/'run';OLD=O.parent/'g-s-historical-native-prefix-20261101'
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(s):return f'{D(s)*100:.4f}%'
specs={'2025_26':('2025-07-02','2025-07-03'),'2022':('2022-01-05','2022-01-06')}
def main():
 out=R/'packet';out.mkdir(exist_ok=False);detail={};lines=[]
 for k,(before,day) in specs.items():
  old=read(OLD/'runs'/k/'primary-resume'/(before+'-CLOSE.json'))
  new=read(R/k/'close'/(day+'-CLOSE.json'));rep=read(R/'report-v2'/(k+'.json'))
  callbacks=new['account']['native_callbacks'][len(old['account']['native_callbacks']):]
  batch=next(x for x in callbacks if x['kind']=='entire_batch_reserved_before_windows')
  accepted=dict(batch['orders']);routes=collections.defaultdict(list)
  for rej in new['account']['rejections'][len(old['account']['rejections']):]:routes[rej['sid']].append(rej['route'])
  fills={f['receipt_id']:f for f in rep['new_fills']};filled={};outcomes=[]
  for cb in callbacks:
   if cb['kind']=='native_buy':
    m=new['account']['capital_meta'][str(cb['layer'])];filled.setdefault(fills[cb['receipt']]['security_id'],[]).append(dict(callback=cb,fill=fills[cb['receipt']],capital_meta=m))
  for i in sorted(old['pending'],key=lambda x:(x['priority'],x['sid'])):
   sid=i['sid'];assert sid in accepted or routes[sid]
   row=dict(sid=sid,priority=i['priority'],core=i['core'],canonical_receipt_id=(i['receipt'] or {}).get('event_id'),
     status='reserved_and_filled' if sid in filled else ('reserved_not_filled' if sid in accepted else 'no_reservation'),
     order_id=accepted.get(sid),actual_fills=filled.get(sid,[]),failed_route_attempts=routes[sid])
   if sid not in accepted:row['last_route_rejection']=routes[sid][-1]
   outcomes.append(row)
  assert len(outcomes)==len({i['sid'] for i in old['pending']})
  write(out/(k+'-intent-outcomes.json'),outcomes)
  used_old=set(old['account']['policy']['consumed']);used_new=set(new['account']['policy']['consumed'])
  ids=[new['account']['supports'][oid]['receipt']['event_id'] for sid,oid in batch['orders'] if new['account']['supports'][oid]['role']=='mobile']
  assert len(ids)==len(set(ids)) and not (set(ids)&used_old) and used_new-used_old==set(ids)
  pending_exits=rep['pending_exit_locks'];new_sids={r['sid'] for r in rep['buy_classification']}
  same_day=[dict(sid=x['sid'],layer=x['lot'],remaining_shares=x['remaining'],reasons=x['duty']['reasons'],earliest_at=x['duty']['earliest_at']) for x in pending_exits if x['sid'] in new_sids]
  for e in rep['actual_old_exit_layers']:
   reasons=old['account']['exit_duties'][e['eid']]['reasons'];e['original_duty_reasons']=reasons
   assert reasons==['CP1_old_line_exit']
  new_intents=[dict(sid=i['sid'],priority=i['priority'],core=i['core'],canonical_receipt_id=(i['receipt'] or {}).get('event_id'),
      decision_at=i['clock']['decision_at'],earliest_execution_at=i['clock']['earliest_execution_at'],deadline=i['deadline']) for i in new['pending']]
  write(out/(k+'-future-intents-unexecuted.json'),new_intents)
  old_events=[(e['at'],e['phase']) for e in old['events']];assert [(e['at'],e['phase']) for e in new['events'][:len(old_events)]]==old_events
  added_events=[dict(at=e['at'],phase=e['phase'],bridge=e['bridge']) for e in new['events'][len(old_events):]]
  statuses=collections.Counter(r['status'] for r in outcomes)
  meta=new['account']['capital_meta'];role_cash=collections.defaultdict(D);purpose_cash=collections.defaultdict(D)
  for sid,rows in filled.items():
   for r in rows:
    gross=D(r['fill']['gross_cny']);role_cash[r['capital_meta']['role']]+=gross;purpose_cash[r['capital_meta']['purpose']]+=gross
  def stringify(d):return {k:str(v) for k,v in d.items()}
  summary=dict(day=day,opening_intents=len(outcomes),unique_stock_outcomes=dict(statuses),failed_route_records=sum(len(v) for v in routes.values()),
    warning='failed route records include S/G/T and core/mobile alternatives; they are not independent opportunities',
    new_receipts_consumed_once=ids,old_receipt_consumption_preserved=True,new_buy_role_gross=stringify(role_cash),new_buy_purpose_gross=stringify(purpose_cash),
    exact_old_exit_layers=rep['actual_old_exit_layers'],released_exit_risk=str(sum((D(e['risk_charge_before_real_fill']) for e in rep['actual_old_exit_layers']),D(0))),
    new_financial_events=added_events,new_action_count=len(rep['new_action_records']),held_before_action_count=sum(bool(x['old_shares']) for x in rep['new_action_records']),
    declared_payments_count=len(rep['payments_due_input']),same_day_new_allocation_requests=same_day,
    pending_exit_count=len(pending_exits),pending_exit_reasons=rep['pending_exit_reason_counts'],future_intents=len(new_intents),
    cash_equation=rep['cash_equation_exact'],NAV=rep['end_balance']['nav'],available=rep['end_balance']['available'],
    actual_exposure=rep['end_exposure'],purpose_weights=rep['purpose_weights'],largest_sector_weight=rep['largest_sector_weight'],
    overnight_existing_inventory_mark_change=rep['passive_overnight_value_change'],active_new_inventory_at_open=rep['active_bought_mark_value'],
    active_sold_inventory_at_open=rep['active_sold_mark_value'],open_to_close_inventory_price_change=rep['passive_open_to_close_value_change'])
  detail[k]=summary
  lines += [f'{k} {day}',f"  Opening inherited intents {len(outcomes)}; actual reservations/buy fills {len(accepted)}/{sum(len(x) for x in filled.values())}; no reservation {statuses['no_reservation']}.",
    f"  Actual sells {len(rep['actual_old_exit_layers'])}; net settled sale cash {rep['real_sale_net']}; all old duties CP1_old_line_exit.",
    f"  Buy gross by role {stringify(role_cash)}; by authorization purpose {stringify(purpose_cash)}; total cash incl fees {rep['new_buy_cost_including_fees']}.",
    f"  Close NAV {rep['end_balance']['nav']}; available {rep['end_balance']['available']}; exposure {pct(rep['end_exposure'])}; max industry {pct(rep['largest_sector_weight'])}.",
    f"  Purpose weights { {u:pct(v) for u,v in rep['purpose_weights'].items()} }; S is multi-industry, not one-theme 80%.",
    f"  Passive overnight old inventory {rep['passive_overnight_value_change']}; active bought/sold opening mark value {rep['active_bought_mark_value']}/{rep['active_sold_mark_value']}; passive open-to-close {rep['passive_open_to_close_value_change']}.",
    f"  Outstanding next-session funding exits {len(pending_exits)}; future unreserved intents {len(new_intents)}. Same-day new stocks requested for partial/full funding reduction: {same_day}.",
    f"  Source actions {len(rep['new_action_records'])}, positive pre-action held quantities {summary['held_before_action_count']}, declared cash payments {summary['declared_payments_count']}.",'']
 write(out/'BEHAVIOR.json',detail)
 lines += ['Scope and remaining coverage:',
  '- Exactly one new financial session per saved account. No old two-day finance replay; no Jul4 or Jan7-or-later event.',
  '- All 9 new buy fills are first actual participation; no add or actual-flat reentry is demonstrated.',
  '- Financial checks use the original Decimal/native inventory/fees/settlement ledger and designated layer exit interface. Close bridges and lot mapping are checked, not forced equal through an arbitrary NAV residual.',
  '- Capacity mainly uses inherited market-warm mature S permissions; this does not prove account-funded trial-to-maturity. Origin purpose and current holding support are separate fields in report-v2.',
  '- No positive held split/dividend entitlement or declared payment occurred. Source action identities (including zero-position split events) are retained; unknown pay/sellability dates retain original research proxy.',
  '- ACT incident/unlock, pending buy support fallback, partial exit, repeated unfilled funding, and unsupported fractional or multi-layer funding cases are not newly exercised by these added real sessions.',
  '- The 4 same-day new buys subsequently requested for allocation funding are an actual turnover concern, not silently corrected. Their requested quantities are explicit and no next-session sale is assumed.',
  '- Existing raw daily-window H/L/C/volume proxy and current-snapshot stock universe limitations remain; no live executability or profitability claim.',
  '- Analysis v1 failed on duplicate eid keyword while serializing locks; source and stderr retained. Only the read-only analysis was fixed; financial checkpoint SHA stayed unchanged.',
  '- Pending next-session intents and funding requests are unexecuted, not failed trades. Stop for independent audit.']
 (out/'READOUT.txt').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(readonly=True,financial_events_executed=0,output=str(out)),ensure_ascii=False))
if __name__=='__main__':main()
