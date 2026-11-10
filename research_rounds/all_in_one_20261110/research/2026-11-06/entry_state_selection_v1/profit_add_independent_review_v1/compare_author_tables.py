"""Cross-check newly published source-only arithmetic against sealed journals."""
from pathlib import Path
import json,gzip,csv,bisect
from decimal import Decimal as D
from collections import Counter,defaultdict
BASE=Path(__file__).resolve().parent
# Only reuse this reviewer's pure fee/serialization functions. No engine imports.
exec((BASE/'review_existing.py').read_text().split('for f in sorted(RUN.glob')[0])
checks=Counter();source={};reviews=[]
def load(p):return read(p)
def replay(trades,at,stop_receipt=None):
 layers={};pool=Z;qty=0;cash=Z;real=Z
 for t in trades:
  if t['at']>at or t.get('receipt_id')==stop_receipt:break
  n=t['shares'];px=dec(t['price']);ff=dec(t['fees_cny'])
  if t['side']=='buy':
   cost=n*px+ff;layers[t['layer']]={'q':n,'k':cost,'cash':-cost};pool+=cost;qty+=n;cash-=cost
  else:
   net=n*px-ff;ret=pool*dec(n)/dec(qty);pool-=ret;qty-=n;cash+=net;real+=net-ret
   for part in t['parts']:
    l=layers[part['layer']];l['k']*=dec(l['q']-part['shares'])/dec(l['q']);l['q']-=part['shares'];l['cash']+=dec(part['net_cash'])
 return layers,pool,qty,cash,real
C=R/'conditional_profit_add_risk_audit_v1';snaps=load(C/'SNAPSHOTS.json');cache={}
for r in snaps:
 key=(r['case_id'],r['arm']);p=cache.setdefault(key,load(Path(r['source']))) if key not in cache else cache[key];sid=p['case']['sid'];at=r['asof'];opened=r['phase']!='t_close';tr=p['trades'];seedids=set(p['rounds'][0]['layers']);tr=[t for t in tr if t['side']=='buy' and t['layer'] in seedids or t['side']=='sell' and any(z['layer'] in seedids for z in t['parts'])]
 layers,pool,qty,cash,real=replay(tr,at,r['receipt_id'] if opened else None);live={k:v for k,v in layers.items() if v['q']};lk=sum(v['k'] for v in live.values());eq(qty,r['existing_qty'],'conditional_Q');eq(pool,r['K_remaining_pool_buy_fee'],'conditional_pool_K');eq(lk,r['K_remaining_layer_buy_fee'],'conditional_layer_K');eq(real,r['realized_pool_net'],'conditional_realized_pool');eq(cash+lk,r['realized_layer_net'],'conditional_realized_layer')
 b=next(t for t in tr if t['side']=='buy' and t['layer']==r['add_layer']);decision=next(d for d in p['decisions'] if d['at']==r['signal_at']);intent=next(i for i in decision['intents'] if i['sid']==sid and i['kind']=='add');q=b['shares'] if opened else intent['cap'];eq(q,r['candidate_qty'],'conditional_candidate_Q');eq(b['floor'],intent['floor'],'conditional_frozen_floor')
 known=[d for d in p['daily'] if d['at']<=at];d=known[-1];factor=dec(d['close_factor']);eq(factor,r['factor_known_t'],'conditional_clock_factor');op=dec(b['raw_open']) if opened else dec(d['raw_close_today']);eq(op,r['mark_raw'],'conditional_clock_mark');price=op*D('1.0005');floor=dec(intent['floor'])/factor;sp=floor*D('.9995');bf=fee(sid,at,'buy',q,price);sf=fee(sid,at,'sell',q,sp);risk=dec(q)*(price-sp)+bf+sf
 for val,key2 in [(price,'candidate_buy_p_with_5bp'),(floor,'candidate_S_raw'),(bf,'candidate_buy_fee'),(sf,'candidate_protection_sell_fee'),(risk,'candidate_new_plan_risk')]:eq(val,r[key2],'conditional_'+key2)
 v=dec(qty)*op*D('.9995')-fee(sid,at,'sell',qty,op*D('.9995'));eq(v,r['V_inventory_net_liquidation'],'conditional_V');eq(v-pool,r['U_inventory_pool'],'conditional_U_inventory');eq(cash+v,r['U_round_confirmed_paid'],'conditional_U_cycle_cash')
 floors={};separate=Z
 for l in d['layers']:
  if l['id'] not in live:continue
  f=dec(l['last_core_line'] if l['kind']=='core' else l['floor'])/factor;n=live[l['id']]['q'];floors[f]=floors.get(f,0)+n;separate+=dec(n)*f*D('.9995')-fee(sid,at,'sell',n,f*D('.9995'))
 grouped=sum((dec(n)*f*D('.9995')-fee(sid,at,'sell',n,f*D('.9995')) for f,n in floors.items()),Z)
 eq(grouped,r['old_protection_value_grouped_floor'],'conditional_floor_grouped');eq(separate,r['old_protection_value_separate_layer'],'conditional_floor_separate');eq(cash+grouped,r['old_protection_round_confirmed_paid'],'conditional_old_floor_cycle');eq(cash+grouped-risk,r['after_ADD_protection_round_confirmed_paid'],'conditional_post_floor_cycle')
# Original NOACT copied trade rows are independently bound to the sealed account.
O=R/'profit_funded_add_case_audit_v1';orig=load(R/'act_only_ablation_continuous_v1/run/pair/NOACT.json.gz');origby={t['receipt_id']:t for t in orig['trades']};tr=load(O/'ACTUAL_TRADES.json');rounds=load(O/'ROUND_SUMMARY.json');os=load(O/'ADD_CLOCK_SNAPSHOTS.json')
for t in tr:
 src=origby[t['receipt_id']];assert {k:v for k,v in t.items() if k!='round_id'}==src;checks['original_trade_source_binding']+=1;eq(dec(t['shares'])*dec(t['price']),t['gross_cny'],'original_gross');eq(fee(t['security_id'],t['at'],t['side'],t['shares'],dec(t['price'])),t['fees_cny'],'original_dated_fill_fee')
byround=defaultdict(list)
for t in tr:byround[t['round_id']].append(t)
for r in rounds:
 tt=byround[r['round_id']];layers,pool,qty,cash,real=replay(tt,r['closed']);assert qty==0;eq(cash,r['round_cash_pnl'],'original_closed_trade_cash');eq(cash+dec(r['booked_dividend']),r['round_net_pnl'],'original_closed_pnl')
for r in os:
 at=r['at'];sid=r['sid'];tt=byround[r['round_id']];b=next(t for t in tt if t['side']=='buy' and t['layer']==r['new_layer_id']);isopen=r['clock']=='OPEN';layers,pool,qty,cash,real=replay(tt,at,b['receipt_id'] if isopen else None);K=sum(x['k'] for x in layers.values());eq(K,r['remaining_buy_cost_including_fees'],'original_layer_K');eq(cash,r['cumulative_trade_cash_from_zero'],'original_cycle_cash');eq(cash+K,r['cumulative_realized_net_sales'],'original_layer_realized');eq(qty,r['held_qty'],'original_Q');assert dec(r['booked_dividend_accrual'])==0
 intent=next(i for d in orig['decisions'] if d['at']==b['signal_at'] for i in d['intents'] if i['sid']==sid and i['kind']==b['kind']);eq(intent['floor'],r['new_floor_adjusted'],'original_intent_floor');eq(b['shares'] if isopen else intent['cap'],r['new_quantity'],'original_causal_Q')
 op=dec(r['mark_raw']);fac=dec(r['factor']);n=r['new_quantity'];price=op*D('1.0005');floor=dec(intent['floor'])/fac;stop=floor*D('.9995');bf=fee(sid,at,'buy',n,price);sf=fee(sid,at,'sell',n,stop);risk=dec(n)*(price-stop)+bf+sf
 eq(risk,r['new_signed_scenario_risk'],'original_new_plan_risk');eq(bf,r['new_buy_fee'],'original_new_buy_fee');eq(sf,r['new_scenario_sell_fee'],'original_new_sell_fee');v=dec(qty)*op*D('.9995')-fee(sid,at,'sell',qty,op*D('.9995'));eq(v-K,r['remaining_net_liquidation_profit_one_order'],'original_layer_U');eq(cash+v,r['full_round_net_liquidation_profit_one_order'],'original_cycle_U')
 fl=Z
 for l in r['layer_details']:
  old=layers[l['layer_id']];eq(old['q'],l['qty'],'original_live_layer_Q');eq(old['k'],l['remaining_cost'],'original_live_layer_cost');sp=dec(l['floor_adjusted'])/fac*D('.9995');feeold=fee(sid,at,'sell',l['qty'],sp);eq(feeold,l['scenario_sell_fee'],'original_old_floor_fee');val=dec(l['qty'])*sp-feeold;fl+=val;eq(val-old['k'],l['scenario_net_remaining'],'original_old_floor_layer_net')
 eq(cash+fl,r['old_full_round_protection_net'],'original_old_floor_cycle');eq(cash+fl-risk,r['full_round_protection_net_after'],'original_post_floor_cycle')
 reviews.append(dict(round_id=r['round_id'],new_layer=r['new_layer_id'],clock=r['clock'],pooled_K=pool,layer_K=K,pooled_U=v-pool,layer_U=v-K,cycle_U=cash+v))
for r in load(O/'LAYER_EXIT_LOSS_BRIDGE.json'):
 keys=['entry_to_trigger_floor_loss','trigger_floor_to_close_loss','trigger_close_to_first_observed_open_loss','first_observed_open_to_actual_sale_loss','sell_slippage','buy_fee','allocated_sell_fees','negative_dividend'];eq(sum(dec(r[k]) for k in keys),-dec(r['actual_net_pnl']),'original_exit_loss_bridge')
result=dict(status='PASS_ALL_NEW_TABLE_ARITHMETIC',checks=checks,conditional_snapshots=len(snaps),original_snapshots=len(os),original_closed_rounds=len(rounds),original_actual_trades=len(tr),limitations=['Original inventory cost is per-layer, not conditional pooled gate. Whole-cycle PnL invariant to either allocation.','Author raw/fact prices are source-contract values, not broker/live execution or independent PIT proof.','No actual financial or strategy simulation was executed.','Positive cycle boolean alone is not risk coverage or realized cash availability.'])
(OUT/'AUTHOR_TABLE_COMPARISON.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');(OUT/'ORIGINAL_POOL_VS_LAYER_COST.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2,default=str)+'\n');(OUT/'AUTHOR_SOURCE_SHA256.json').write_text(json.dumps(source,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,default=str))
