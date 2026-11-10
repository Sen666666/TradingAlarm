"""Read-only descriptive M7 concentration analysis. No strategy mutation or orders."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,csv,hashlib
O=Path(__file__).resolve().parent; ROOT=O.parent
P=ROOT/'mainline_m7_downturn_cash_batch_v6/once_20241031'
ZERO=D(0); PV='光伏风电设备'; END='2024-10-31'
NAMES=['SECTOR_DAILY','HOLDINGS','ORDERS','DAY_LEDGER','REFERENCE_DAILY','CAPITAL_LOTS','TRANSFERS','TRANSFER_PLAN_AT_END','ADD_FLOOR_RISK','CANDIDATES','PENDING_AT_END']
data={n:json.loads((P/(n+'.json')).read_text()) for n in NAMES}
def save(n,rows):
 (O/(n+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str))
 if isinstance(rows,list) and rows:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def sumd(rows,col):return sum((D(r.get(col,0)) for r in rows),ZERO)
sectors=[r for r in data['SECTOR_DAILY'] if r['sector51'] in [PV,'半导体','软件与IT服务'] and r['day']>='2024-10-08']
save('FOCUS_SECTOR_DAILY',sectors)
refs=[r for r in data['REFERENCE_DAILY'] if r['sector51']==PV and r['day']>='2024-10-22']
save('PV_CAPITAL_REFERENCE', [{k:v for k,v in r.items() if k!='independent_demand_details'} for r in refs])
save('PV_LEGAL_DEMAND',[dict(plan_day=r['day'],**x) for r in refs for x in r['independent_demand_details']])
orders=[r for r in data['ORDERS'] if r['sector51']==PV and r['day']>='2024-10-22'];save('PV_ORDERS',orders)
holds=[r for r in data['HOLDINGS'] if r['sector51']==PV and r['day']==END]
capital={r['lot_id']:r for r in data['CAPITAL_LOTS'] if r['day']==END}
names={r['sid']:r['name'] for r in data['ORDERS']}
nav=D(data['DAY_LEDGER'][-1]['NAV'])
by_sid=defaultdict(list)
for r in holds:by_sid[r['sid']].append(r)
stocks=[]
for sid,rs in by_sid.items():
 cr=[capital[r['lot_id']] for r in rs];market=sumd(rs,'market_value')
 risk=sum((r['qty']*max(ZERO,D(r['raw_mark'])-D(r['protection_signal'])/D(r['factor'])) for r in rs),ZERO)
 stocks.append(dict(sid=sid,name=names[sid],qty=sum(r['qty'] for r in rs),market_value=market,weight_pct=market/nav*100,
  mobile_value=sumd(cr,'mobile_value'),frozen_value=sumd(cr,'frozen_value'),initial_value=sumd([r for r in cr if r['capital_role']=='INITIAL'],'market_value'),
  expansion_value=sumd([r for r in cr if r['capital_role']=='EXPANSION'],'market_value'),locked_value=sumd([r for r in rs if r.get('locked_exit')],'market_value'),
  current_close_to_known_floor_loss_before_cost=risk,locked_exit_reasons=sorted({r['locked_exit'] for r in rs if r.get('locked_exit')})))
stocks.sort(key=lambda r:-r['market_value']);save('PV_END_STOCKS',stocks)
daily=[]
for ds in sorted({r['day'] for r in orders}):
 ts=[r for r in orders if r['day']==ds];sd=next(r for r in sectors if r['day']==ds and r['sector51']==PV)
 daily.append(dict(day=ds,M_close=sd['M'],sector_state_close=sd['state'],stocks=sd['stocks'],weight_pct=sd['account_weight_pct'],
  buy_seed_cash=-sumd([r for r in ts if r['side']=='BUY_SEED'],'cash_delta'),buy_add_cash=-sumd([r for r in ts if r['side']=='BUY_ADD'],'cash_delta'),
  sell_cash=sumd([r for r in ts if r['side'].startswith('SELL')],'cash_delta'),
  seed_orders=sum(r['side']=='BUY_SEED' for r in ts),add_orders=sum(r['side']=='BUY_ADD' for r in ts),
  sell_orders=sum(r['side'].startswith('SELL') for r in ts),signal_days=sorted({r['signal_day'] for r in ts if r.get('signal_day')})))
save('PV_DAILY_TRADING',daily)
fund=[]
for dt in ['2024-10-24','2024-10-28','2024-10-29','2024-10-30','2024-10-31']:
 for r in data['TRANSFERS']:
  if r['day']==dt and r['event'] in ['DEMAND_PLAN','RECEIVER_FUNDING','TRANSFER_CASH']:
   fund.append({k:v for k,v in r.items() if k!='receivers'})
save('CASH_AND_DEMAND',fund)
donors=[]
for dt in ['2024-10-24','2024-10-28','2024-10-29']:
 ts=[r for r in data['ORDERS'] if r['day']==dt and r['side'].startswith('SELL') and r.get('transfer_rank')]
 for sec in sorted({r['sector51'] for r in ts}):
  ss=[r for r in ts if r['sector51']==sec]
  donors.append(dict(day=dt,sector51=sec,orders=len(ss),net_cash=sumd(ss,'cash_delta'),reasons=sorted({r['reason'] for r in ss})))
save('EXPANSION_DONORS',donors)
risks=[r for r in data['ADD_FLOOR_RISK'] if r['day']>='2024-10-22' and any(t['round_id']==r['round_id'] for t in orders)]
save('PV_ADDITION_FLOOR_RISKS',risks)
risk_summary=[]
for ds in sorted({r['day'] for r in risks}):
 rr=[r for r in risks if r['day']==ds]
 risk_summary.append(dict(day=ds,adds=len(rr),all_in_cost=sumd(rr,'buy_all_in'),incremental_known_floor_loss=sumd(rr,'incremental_known_floor_loss'),not_profit_covered=sum(r['not_profit_covered'] for r in rr)))
save('PV_ADDITION_RISK_SUMMARY',risk_summary)
summary=dict(result='PASS',through=END,account_NAV=nav,pv_market=sumd(stocks,'market_value'),pv_weight_pct=sumd(stocks,'market_value')/nav*100,pv_stocks=len(stocks),
 expansion_mobile_value=sumd(stocks,'mobile_value'),initial_frozen_value=sumd(stocks,'initial_value'),locked_value=sumd(stocks,'locked_value'),
 raw_close_to_floor_loss_before_fees_slippage=sumd(stocks,'current_close_to_known_floor_loss_before_cost'),
 pv_reference_target=refs[-1]['T'],cash=data['DAY_LEDGER'][-1]['cash'],
 next_close_planned_mature_demand=next(r['M_desired_cost'] for r in reversed(data['TRANSFERS']) if r['event']=='DEMAND_PLAN'),
 next_financing_gap=next(r['initial_gap'] for r in reversed(data['TRANSFERS']) if r['event']=='DEMAND_PLAN'),next_transfer_orders=len(data['TRANSFER_PLAN_AT_END']),
 planned_PV_new_requests=sum(r.get('_ref_q',0)>0 and r.get('event_id','').startswith(PV) for r in data['PENDING_AT_END'] if r.get('event_id')),
 caveats=['Diagnostic only, not an alternate funded trading simulation.','M=-1 is unknown, not false. OPEN uses prior completed CLOSE decision.','Reference target is a funding ceiling, not mandatory rebalance.','Known floor risk is not guaranteed execution loss; gap, nontradability, tax, fees and slippage can worsen it.','No live orders; unchanged frozen M7 files.'])
assert summary['pv_market']==D(next(r['market_value'] for r in sectors if r['day']==END and r['sector51']==PV))
assert summary['expansion_mobile_value']+summary['initial_frozen_value']+summary['locked_value']==summary['pv_market']
assert summary['next_transfer_orders']==0 and D(summary['next_financing_gap'])==0
save('SUMMARY',summary)
save('SOURCE_HASHES',{str(P/(n+'.json')):hashlib.sha256((P/(n+'.json')).read_bytes()).hexdigest() for n in NAMES})
print(json.dumps(summary,ensure_ascii=False,default=str))
