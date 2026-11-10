from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,sys,pandas as pd
P=Path(__file__).resolve().parent.parent;O=P/sys.argv[1];R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());ledger=read(R/'DAY_LEDGER.json');orders=read(R/'ORDERS.json');eq=read(R/'EQUITY_EVENTS.json');held=[h for h in read(R/'HOLDINGS.json') if h['day']==ledger[-1]['day']];lots={};realized=D(0);sales=[]
for t in orders:
 if t['side'].startswith('BUY'):lots[t['lot_id']]=dict(cost=-D(t['cash_delta']),qty=t['qty'],sid=t['sid'],kind=t['side'][4:],round_id=t['round_id'])
 else:
  assert sum(lots[l]['qty'] for l in t['lots'])==t['qty'];basis=sum((lots[l]['cost'] for l in t['lots']),D(0));pnl=D(t['cash_delta'])-basis;realized+=pnl;sales.append(dict(day=t['day'],sid=t['sid'],sector51=t['sector51'],side=t['side'],net_sale_cash=t['cash_delta'],cost_basis=str(basis),realized_trade_pnl=str(pnl)))
  for l in t['lots']:del lots[l]
assert set(lots)=={h['lot_id'] for h in held};div=sum((D(x['receivable_delta']) for x in eq if x['event']=='ACCRUE_NET80'),D(0));basis=sum((l['cost'] for l in lots.values()),D(0));mv=D(ledger[-1]['market_value']);nav=D(ledger[-1]['NAV']);floating=mv-basis;assert realized+div+floating==nav-D(1200000)
peak=D(1200000);peakday='INITIAL';mdd=D(0);worst={};dd=[]
for l in ledger:
 n=D(l['NAV'])
 if n>peak:peak=n;peakday=l['day']
 pct=n/peak-1;dd.append(dict(day=l['day'],NAV=str(n),running_peak_NAV=str(peak),drawdown_pct=str(100*pct)))
 if pct<mdd:mdd=pct;worst=dict(peak_day=peakday,peak_NAV=str(peak),trough_day=l['day'],trough_NAV=str(n),drawdown_cash=str(peak-n),drawdown_pct=str(100*pct))
names=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv').set_index('symbol').name.to_dict();rows=[];am={a['id']:a for a in read(R/'ATTEMPTS.json')}
for s in sorted({h['sid'] for h in held}):
 hs=[h for h in held if h['sid']==s];bm=sum((lots[h['lot_id']]['cost'] for h in hs),D(0));val=sum((D(h['market_value']) for h in hs),D(0));rows.append(dict(day=ledger[-1]['day'],sid=s,name=names[s],sector51=hs[0]['sector51'],qty=sum(h['qty'] for h in hs),SEED_qty=sum(h['qty'] for h in hs if h['kind']=='SEED'),ADD_qty=sum(h['qty'] for h in hs if h['kind']=='ADD'),market_value=str(val),NAV_weight_pct=str(100*val/nav),remaining_lot_cost_basis=str(bm),unrealized_marked_pnl=str(val-bm),mature_historical_ADD=am[hs[0]['round_id']]['add_count']>0,stale=any(h.get('stale',False) for h in hs),tradable=all(h.get('tradable',True) for h in hs)))
pd.DataFrame(rows).to_csv(O/'LATEST_HOLDINGS_BY_STOCK.csv',index=False);pd.DataFrame(sales).to_csv(O/'REALIZED_TRADE_PNL_BY_SALE.csv',index=False);pd.DataFrame(dd).to_csv(O/'CLOSE_NAV_DRAWDOWN.csv',index=False)
summary=dict(scope='FROZEN_EXPERIMENT_NOT_DEPLOYABLE_STRATEGY',certified_through=ledger[-1]['day'],NAV=str(nav),net_liquidation_NAV=ledger[-1]['net_liquidation_NAV'],cash=ledger[-1]['cash'],receivable=ledger[-1]['receivable'],market_value=str(mv),position_pct=ledger[-1]['weight_pct'],stocks=len(rows),held_sectors=len({h['sector51'] for h in held}),total_marked_PnL=str(nav-D(1200000)),total_return_pct=str(100*(nav/D(1200000)-1)),realized_trade_PnL_net_all_buy_and_sell_fees=str(realized),recognized_NET80_dividend=str(div),realized_trade_plus_dividend=str(realized+div),remaining_lot_cost_basis=str(basis),unrealized_marked_PnL=str(floating),hypothetical_liquidation_unrealized_PnL=str(floating-(nav-D(ledger[-1]['net_liquidation_NAV']))) if ledger[-1]['net_liquidation_NAV'] is not None else None,reconciliation_residual=str(nav-D(1200000)-realized-div-floating),maximum_close_NAV_drawdown=worst,drawdown_scope='Recorded CLOSE NAV only, not intraday or execution-certified',blocked=read(R/'BLOCKERS.json'),economic_alpha_rule_changes=0,accounting_boundary_extension='EXPLICIT_STALE_NONTRADABLE_SUSPENSION',stale_market_value=ledger[-1].get('stale_market_value','0'),whole_account_liquidation_available=ledger[-1].get('whole_account_liquidation_available',True),tradable_subset_net_liquidation_value=ledger[-1].get('tradable_subset_net_liquidation_value'))
(O/'ENDPOINT_ACCOUNTING_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
