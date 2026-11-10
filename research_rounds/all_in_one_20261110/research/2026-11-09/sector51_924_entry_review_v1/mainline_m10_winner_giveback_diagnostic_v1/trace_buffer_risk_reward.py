import json,runpy,contextlib,io,hashlib,csv
from pathlib import Path
from decimal import Decimal as D
P=Path(__file__).parent
with contextlib.redirect_stdout(io.StringIO()):ns=runpy.run_path(str(P/'check_overlap_and_buffer.py'))
extra=ns['res'];z=ns['data']['M10'];sales=ns['sales']['M10'];fee=ns['fee'];main=json.loads((P/'M10_DIAGNOSTIC.json').read_text());ranks={r['round_id']:r for r in main['all_M10_rounds_1106']};rows=[]
for cr in extra['buffer_recrossings']:
 for b in cr['day_orders']:
  if b['side']!='BUY_ADD':continue
  lid=b['lot_id'];s=b['sid'];rid=b['round_id'];cost=D(b['all_in_cost']);qty=b['qty'];ss=sales[lid];hs=[h for h in z['HOLDINGS'] if h['lot_id']==lid and h['day']<='2024-11-06'];endhold=next((h for h in hs if h['day']=='2024-11-06'),None);sold=sum(o['qty'] for o in ss);remain=endhold['qty'] if endhold else 0;assert sold+remain==qty
  divs=[e for e in z['EQUITY_EVENTS'] if e.get('round_id')==rid and e['event']=='ACCRUE_NET80' and e['day']>=b['day']]
  dividend_note='No round dividend accrual while relevant; target lot entitlement zero'
  if divs:
   ep=P.parent/'retained_20241014_15_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20241014_15_SEVEN_V1.json'; evs=ns['read'](ep)
   for e in divs:
    ev=next(ev for ev in evs if ev['sid']==s and ev['ex_date']==e['day']);recordq=sum(h['qty'] for h in hs if h['day']==ev['record_date']);assert recordq==0,(lid,recordq);assert sum(h['qty'] for h in z['HOLDINGS'] if h['round_id']==rid and h['day']==ev['record_date'])==e['record_qty']
   dividend_note='Round accrues137.60 net80 on10/15 to remaining200 SEED shares; target414 ADD sold10/14 OPEN before10/14 record CLOSE, so this ADD entitlement is0'

  values=[]
  for h in hs:
   d=h['day'];q=h['qty'];px=D(h['raw_mark'])*D('.9995');liq=q*px-fee(s,d,q,px);realizedcash=sum((o['cash_delta'] for o in ss if o['day']<=d),D(0));values.append(dict(day=d,remaining_qty=q,raw_close=h['raw_mark'],remaining_unrealized_net=liq-cost*D(q)/D(qty),cumulative_lot_net=realizedcash+liq-cost))
  pf=max(values,key=lambda x:x['remaining_unrealized_net']);pn=max(values,key=lambda x:x['cumulative_lot_net']);endmarked=D(endhold['market_value']) if endhold else D(0);endpx=D(endhold['raw_mark'])*D('.9995') if endhold else D(0);endliq=remain*endpx-fee(s,'2024-11-06',remain,endpx) if remain else D(0);actualsold=sum((o['cash_delta'] for o in ss),D(0));rr=ranks[rid]
  row=dict(sid=s,name=b['name'],round_id=rid,lot_id=lid,add_day=b['day'],add_qty=qty,add_fill_price=b['price'],buy_all_in_cost=cost,layer_buffer_before=cr['previous_layer_net'],layer_buffer_after=cr['current_layer_net'],added_floor_risk=D(cr['previous_layer_net'])-D(cr['current_layer_net']),sold_qty=sold,remaining_qty=remain,actual_sales=ss,allocated_actual_sale_fees=sum((o['allocated_fee'] for o in ss),D(0)),actual_net_sale_proceeds=actualsold,remaining_marked_value=endmarked,remaining_hypothetical_net_sale_value=endliq,lot_final_marked_contribution=actualsold+endmarked-cost,lot_final_net_liquidation_contribution=actualsold+endliq-cost,dividend_entitlement=0,dividend_note=dividend_note,max_observed_remaining_unrealized_net=pf['remaining_unrealized_net'],max_remaining_unrealized_day=pf['day'],max_observed_cumulative_lot_net=pn['cumulative_lot_net'],max_cumulative_lot_day=pn['day'],round_peak_day=rr['peak_day'],round_peak_net=rr['peak_net'],round_final_net=rr['final_net'],round_final_qty=rr['final_qty'],round_exit_day=rr['exit_day'],interpretation='Observed risk/reward exchange only; crossing zero floor net is not a violation and does not imply ADD should have been blocked')
  rows.append(row)
result=dict(source_hashes=ns['hashes'],rows=rows,positive_lot_final=sum(r['lot_final_net_liquidation_contribution']>0 for r in rows),negative_lot_final=sum(r['lot_final_net_liquidation_contribution']<0 for r in rows),caveats=['No counterfactual financing or blocked-ADD strategy is run. The actual lot contribution is not the causal incremental account profit.','MFE uses actual observed CLOSE snapshots, not intraday high. Remaining unrealized PnL subtracts remaining pro-rata original all-in buy cost and a hypothetical separate sell fee; cumulative lot PnL additionally includes actual prior allocated sale proceeds.','Actual mixed-order sale fees allocated by shares; remaining end-11/6 shares hypothetically sold separately with inherited5bp slippage and per-lot fee. Marked contribution is separately provided.','All8 target ADD lots have zero dividend entitlement. 688516 original round receives137.60 net80 for200 SEED shares, but its target414 ADD sold before10/14 record CLOSE; source adapter and record-date holdings checked.','The user accepts principal risk for trend capture; nonpositive floor pressure describes capital at risk, not an automatic error or a default break-even constraint.'])
(P/'BUFFER_RISK_REWARD.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
flat=[{k:v for k,v in r.items() if k!='actual_sales'} for r in rows]
with (P/'BUFFER_RISK_REWARD.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
print(json.dumps(result,ensure_ascii=False,default=str))
