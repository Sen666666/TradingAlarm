"""Read-only original-ledger attribution, not a no-loss-add counterfactual account."""
from pathlib import Path
import json,gzip,hashlib
from decimal import Decimal as D
from bisect import bisect_left
import pandas as pd
O=Path(__file__).resolve().parent/'losing_add_audit';O.mkdir(exist_ok=True)
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/pair')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
a=json.load(gzip.open(B/'B.json.gz','rt'));ds=[json.loads(x)for x in gzip.open(B/'daily.jsonl.gz','rt')];days=[x['at'][:10]for x in ds]
buys={t['layer']:t for t in a['trades']if t['side']=='buy'};final={x['id']:x for x in a['layers']};actions={};rows=[]
for t in a['trades']:
 if t['side']!='buy' or t['kind']!='add':continue
 sid=t['security_id'];day=t['at'][:10];j=bisect_left(days,day)-1
 z=dict(sid=sid,buy_day=day,signal_at=t['signal_at'],layer=t['layer'],new_qty=t['shares'],new_gross=float(t['gross_cny']),new_fee=float(t['fees_cny']),new_total=float(D(t['gross_cny'])+D(t['fees_cny'])),year=day[:4],raw_open=float(t['raw_open']),execution_basis=t['execution_basis'])
 if j<0:z.update(classification='UNKNOWN_no_prior_close');rows.append(z);continue
 prior=ds[j];old=[x for x in prior['layers']if x['sid']==sid];q=sum(x['qty']for x in old);z.update(prior_close=prior['at'][:10],old_qty=q,old_layer_count=len(old),old_layer_ids=','.join(str(x['id'])for x in old))
 assert q==prior['positions'].get(sid,0)
 if not q:z.update(classification='MOBILE_FLAT_ENTRY_NOT_ADD');rows.append(z);continue
 if sid not in actions:actions[sid]=json.loads((P/'actions'/f'{sid}.json').read_text())['events']
 ca=[e for e in actions[sid]if prior['at'][:10]<e['effective_date']<=day]
 same_sell=[x for x in a['trades']if x['side']=='sell' and x['security_id']==sid and x['at']==t['at']]
 if ca or same_sell:z.update(classification='UNKNOWN_open_CA_or_same_open_sell',ca_count=len(ca),same_open_sell_count=len(same_sell));rows.append(z);continue
 K=D(0);div=D(0);layers=[]
 for x in old:
  orig=buys[x['id']];principal=D(x['qty'])*D(str(x['unit_cost']));fee=principal/D(orig['gross_cny'])*D(orig['fees_cny']);k=principal+fee;K+=k;div+=D(x['dividend']);pnl=D(x['qty'])*D(t['raw_open'])-k
  layers.append(dict(id=x['id'],qty=x['qty'],remaining_cost_including_fee=float(k),mark_pnl=float(pnl),dividend_accrual=float(D(x['dividend']))))
 mv=D(q)*D(t['raw_open']);pnl=mv-K;economic=pnl+div
 z.update(old_cost=float(K),old_open_mark=float(mv),old_open_unrealized_pnl=float(pnl),old_dividend_accrual=float(div),old_open_pnl_plus_accrued_dividend=float(economic),old_losing_layer_count=sum(x['mark_pnl']<0 for x in layers),classification='ADD_STOCK_LOSS' if pnl<0 else 'ADD_STOCK_PROFIT' if pnl>0 else 'ADD_STOCK_FLAT',layer_states=json.dumps(layers,ensure_ascii=False))
 closed=final[t['layer']]
 if not closed['qty'] and closed.get('closed'):
  z.update(added_layer_closed=closed['closed'][:10],added_layer_final_net_pnl=float(D(closed['cash'])+D(closed['dividend'])),final_status='CLOSED_BY_2024_END')
 else:z.update(final_status='OPEN_AT_2024_END_not_realized')
 rows.append(z)
f=pd.DataFrame(rows);f.to_csv(O/'ALL_MOBILE_CLASSIFICATION.csv',index=False)
summary=[]
for year in ['2022','2023','2024','ALL']:
 d=f if year=='ALL' else f[f.year.eq(year)];loss=d[d.classification.eq('ADD_STOCK_LOSS')];profit=d[d.classification.eq('ADD_STOCK_PROFIT')];closed=loss[loss.final_status.eq('CLOSED_BY_2024_END')]
 summary.append(dict(year=year,mobile_buys=len(d),mobile_flat_entries=int(d.classification.eq('MOBILE_FLAT_ENTRY_NOT_ADD').sum()),held_stock_adds=int(d.classification.str.startswith('ADD_').sum()),loss_state_adds=len(loss),loss_state_gross=float(loss.new_gross.sum()),loss_state_total_paid=float(loss.new_total.sum()),loss_state_old_unrealized=float(loss.old_open_unrealized_pnl.sum()),loss_state_even_after_accrued_dividend=int(loss.old_open_pnl_plus_accrued_dividend.lt(0).sum()),profitable_stock_adds=len(profit),profitable_stock_with_losing_layer=int(profit.old_losing_layer_count.gt(0).sum()),unknown=int(d.classification.str.startswith('UNKNOWN').sum()),loss_add_closed_by_2024_end=len(closed),loss_add_final_net=float(closed.added_layer_final_net_pnl.sum()),loss_add_negative_outcome_sum=float(closed.loc[closed.added_layer_final_net_pnl.lt(0),'added_layer_final_net_pnl'].sum()),loss_add_positive_outcome_sum=float(closed.loc[closed.added_layer_final_net_pnl.gt(0),'added_layer_final_net_pnl'].sum()),loss_add_winning_outcomes=int(closed.added_layer_final_net_pnl.gt(0).sum()),loss_add_closed_in_entry_year=int((closed.added_layer_closed.str[:4]==closed.year).sum()),loss_add_net_closed_in_entry_year=float(closed.loc[closed.added_layer_closed.str[:4]==closed.year,'added_layer_final_net_pnl'].sum())))
(O/'SUMMARY.json').write_text(json.dumps(dict(scope='Original 1m-start 2022-2024 account; before new buy, all old same-stock CORE/MOBILE live lots merged. OPEN is old daily-price proxy, not certified executable quote.',cost='Remaining quantity times same-day snapshot unit_cost plus prorated original buy fees. Realized past campaign PnL kept separate, dividend accrual separately reported. Same-OPEN CA or sell is UNKNOWN.',attribution='Final outcome of added layer is hindsight attribution only. It is not PnL gain from banning it; ban changes future cash, eligibility and positions.',years=summary),ensure_ascii=False,indent=2))
print(json.dumps(summary,indent=2));print(f[f.classification.eq('ADD_STOCK_LOSS')][['sid','buy_day','layer','old_qty','old_cost','old_open_unrealized_pnl','new_qty','new_total','added_layer_final_net_pnl']].head(15).to_string(index=False));print('profit stock losing layer examples');print(f[f.classification.eq('ADD_STOCK_PROFIT')&f.old_losing_layer_count.gt(0)][['sid','buy_day','layer','old_open_unrealized_pnl','old_losing_layer_count','new_qty']].head(5).to_string(index=False))
