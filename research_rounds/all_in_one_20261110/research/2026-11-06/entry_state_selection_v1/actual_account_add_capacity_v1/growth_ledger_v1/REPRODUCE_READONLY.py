from pathlib import Path
import json,gzip,csv,sys,collections
from decimal import Decimal as D
import pandas as pd
sys.dont_write_bytecode=True
dest=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/actual_account_add_capacity_v1')
base=dest.parent/'account_comparison_continuous_v1'
root=base/'no_loss_add_v1/run_1200000'
a=json.load(gzip.open(root/'pair/PVR.json.gz','rt'))
ds={x['at'][:10]:x for l in gzip.open(root/'pair/daily.jsonl.gz','rt') if (x:=json.loads(l))['account']=='PVR'}
sm={x['symbol']:x for x in json.load(open('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
rb=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.path.insert(0,str(rb/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=json.load(open(rb/'inputs-v2/market-rules.json'));proxies=json.load(open(rb/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
def fee(sid,q,px,dt,side='sell'):
 if not q:return D(0)
 ident=market_identity_on(rules,sid,dt,proxies);v=version_on(rules['fee_versions'][ident['venue']],dt,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
 return sum(fs.incremental(side,D(q)*px,{}, {},1,shares=q,par_value=par).values(),D(0))
raw={}
def priceframe(sid):
 if sid not in raw:raw[sid]=pd.read_parquet(next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet')))
 return raw[sid]
def risk(sid,q,buy,fl,dt):
 if not q:return D(0)
 return max(D(0),D(q)*buy+fee(sid,q,buy,dt,'buy')-D(q)*fl*D('.9995')+fee(sid,q,fl*D('.9995'),dt))
gates={}
for l in gzip.open(root/'PROFIT_GATE_EVENTS.jsonl.gz','rt'):
 g=json.loads(l)
 if g['at'][:10] in ['2024-09-24','2024-09-25','2024-09-26']:gates[(g['at'][:10],g['sid'],g['role'])]=g
targets=json.loads((dest/'RESULTS.json').read_text())['results']
targets += [dict(sid='300085.SZ',name='银之杰',date='2024-09-26',old_q=0,new_q=100,seed_day='2024-09-25')]
trade_by_layer={t['layer']:t for t in a['trades'] if t['side']=='buy'}
funds={}
for l in gzip.open(root/'pair/funding.jsonl.gz','rt'):
 x=json.loads(l)
 if x['at'][:10] in ['2024-09-24','2024-09-25','2024-09-26']:funds[(x['at'][:10],x['sid'],x['role'])]=x
allresults=[];layer_details=[];history_details=[]
for target in targets:
 sid=target['sid'];dt=target['date'];g=gates[(dt,sid,'mobile')];prev=g['signal_at'][:10]
 factor=D(str(priceframe(sid).loc[dt].adjustment_factor))
 intent=next(i for de in a['decisions'] if de['at'][:10]==prev for i in de['intents'] if i['sid']==sid and i['role']=='mobile')
 candidate_floor=D(intent['floor'])/factor;buy=D(g['buy_proxy']);op=D(g['known_open']);Q=int(g['qty']);C=D(g['cost']);U=D(g['net_profit'])
 if target['old_q']:
  reserve_ix=next(k for k,j in enumerate(a['journal']) if j['kind']=='real_reserve' and j['sid']==sid and j['at'][:10]==dt)
 else:
  # All this OPEN's recorded native intents are rejected by cash; no reserve/fill.
  assert not [j for j in a['journal'] if j['at'][:10]==dt and j['kind'] in ['real_reserve','real_buy_fill','real_sell_fill']]
  reserve_ix=next((k for k,j in enumerate(a['journal']) if j['at'][:10]>dt),len(a['journal']))
 journal=a['journal'][:reserve_ix]
 # Reconstruct exact active position round and per-layer costs from actual fills.
 lots={};round_id=0;seed_id=None;round_opened=None;qty=0;H=D(0);H_all=D(0);history=[];unknown=None
 own_pending={};global_pending={};own_pending_risk=D(0)
 for j in journal:
  kind=j['kind'];jsid=j['sid']
  if kind=='real_reserve':
   global_pending[j['budget_order']]=dict(j)
   if jsid==sid:own_pending[j['budget_order']]=dict(j)
  elif kind=='real_buy_fill':
   bo=j['budget_order'];assert bo in global_pending
   global_pending[bo]['shares']-=j['shares']
   if not global_pending[bo]['shares']:del global_pending[bo]
   if jsid==sid:
    assert bo in own_pending;own_pending[bo]['shares']-=j['shares']
    if not own_pending[bo]['shares']:del own_pending[bo]
  if jsid!=sid:continue
  if kind=='real_buy_fill':
   if qty==0:
    round_id+=1;seed_id=j['layer'];round_opened=j['at'][:10];lots={};H=D(0);H_all=D(0);history=[];unknown=None
   lots[j['layer']]=dict(q=j['shares'],cost=D(j['shares'])*D(j['price'])+D(j['fees']),seed=(j['layer']==seed_id),opened=j['at'][:10])
   qty+=j['shares']
  elif kind=='real_sell_fill':
   for part in j['parts']:
    lot=lots[part['layer']];assert part['shares']<=lot['q']
    retired=lot['cost']*D(part['shares'])/D(lot['q']);pn=D(part['net_cash'])-retired
    debt=max(D(0),-pn);H_all+=debt
    if not lot['seed']:H+=debt
    history.append(dict(sid=sid,point=dt,at=j['at'],layer=part['layer'],shares=part['shares'],seed=lot['seed'],retired_cost=str(retired),net_proceeds=part['net_cash'],realized_net=str(pn),H_increment=str(debt if not lot['seed'] else D(0))))
    lot['q']-=part['shares'];lot['cost']-=retired;qty-=part['shares']
  elif kind=='actual_split' and qty:
   # Exact layer split dispatch not reconstructed generically; preserve UNKNOWN.
   unknown='ACTIVE_ROUND_SPLIT_LAYER_ALLOCATION_NOT_RECONSTRUCTED'
 assert round_opened==target['seed_day']
 assert unknown is None,(sid,dt,unknown)
 assert qty==Q
 current=[x for x in ds[prev]['layers'] if x['sid']==sid]
 assert {x['id']:x['qty'] for x in current}=={k:v['q'] for k,v in lots.items() if v['q']},(sid,'layer qty bridge')
 assert not own_pending, (sid,'unexpected same-stock pending; must derive risk rather than assume zero')
 # P=0 is established by exact native reserve/fill prefix, not assumed.
 P=D(0);L=D(0);Dlive_all=D(0);G_all=D(0);layer_cost_sum=D(0)
 for x in current:
  lot=lots[x['id']];q=lot['q'];layer_cost_sum+=lot['cost']
  fl=D(x['last_core_line'] if x['kind']=='core' else x['floor'])/factor
  stopnet=D(q)*fl*D('.9995')-fee(sid,q,fl*D('.9995'),dt)
  principal=max(D(0),lot['cost']-stopnet)
  marknet=D(q)*op*D('.9995')-fee(sid,q,op*D('.9995'),dt)
  giveback=max(D(0),marknet-stopnet)
  if not lot['seed']:L+=principal
  Dlive_all+=principal;G_all+=giveback
  layer_details.append(dict(point=dt,sid=sid,layer=x['id'],economic_class='seed' if lot['seed'] else 'true_add',kind=x['kind'],qty=q,remaining_layer_cost=str(lot['cost']),protection_asof_close=prev,raw_protection=str(fl),raw_open_factor=str(factor),stop_net=str(stopnet),principal_loss_proxy=str(principal),giveback_proxy=str(giveback),opened=lot['opened']))
 seed=trade_by_layer[seed_id];seed_factor=D(str(priceframe(sid).loc[seed['at'][:10]].adjustment_factor));seed_floor=D(seed['floor'])/seed_factor
 R0=risk(sid,seed['shares'],D(seed['price']),seed_floor,seed['at'][:10])
 def Up(q):
  return D(Q+q)*op*D('.9995')-fee(sid,Q+q,op*D('.9995'),dt)-(C+D(q)*buy+fee(sid,q,buy,dt,'buy'))
 qr=QuantityRule(**version_on(rules['quantity_versions'][sid],dt,proxies)['rule'])
 top=qr.buy_floor(min(Q,target['old_q'] if target['old_q'] else int(intent['cap'])))
 def qualifies(q):
  return U>0 and Up(q)>0 and H+L+P+risk(sid,q,buy,candidate_floor,dt)<=D('.25')*R0+Up(q)
 q=top
 while q and not qualifies(q):q=qr.buy_floor(q-1)
 Dnew=risk(sid,q,buy,candidate_floor,dt) if q else D(0);up=Up(q) if q else U
 cashnew=D(q)*buy+fee(sid,q,buy,dt,'buy') if q else D(0)
 origfund=funds[(dt,sid,'mobile')]
 pending_cash=D(0)
 for order in global_pending.values():
  osid=order['sid'];oq=order['shares'];oprice=D(order['price'])
  pending_cash+=D(oq)*oprice+fee(osid,oq,oprice,dt,'buy')
 history_details.extend(history)
 allresults.append(dict(sid=sid,name=target['name'],date=dt,signal_day=prev,seed_day=round_opened,seed_layer=seed_id,seed_q=seed['shares'],R0=str(R0),qty=Q,remaining_stock_average_cost=str(C),sum_remaining_layer_cost=str(layer_cost_sum),U=str(U),H=str(H),H_all_layers=str(H_all),realized_parts_in_round=len(history),realized_true_add_parts=sum(not h['seed'] for h in history),L=str(L),P=str(P),pending_same_stock_orders=len(own_pending),pending_all_stock_orders=len(global_pending),pending_all_stock_cash=str(pending_cash),whole_stock_principal_before=str(Dlive_all),whole_stock_giveback_before=str(G_all),candidate_raw_floor=str(candidate_floor),old_q=target['old_q'],previous_fixed_cap_q=target['new_q'],growth_qty=q,U_post=str(up),growth_Dnew=str(Dnew),growth_budget=str(D('.25')*R0+up),growth_cash=str(cashnew),native_result=origfund['result'],native_pool=origfund.get('pool'),native_original_qty=origfund.get('shares',0),pointwise_qty_after_native=q if target['old_q'] else 0,principal_after_plus_H_all=str(Dlive_all+Dnew+H_all),principal_R0_headroom_before=str(R0-Dlive_all-H_all),strict_principal_cap_defined_in_native=False,minlot_D=str(risk(sid,qr.buy_minimum,buy,candidate_floor,dt)),minlot_U_post=str(Up(qr.buy_minimum))))

for x in allresults:
 sid=x['sid'];dt=x['date'];g=gates[(dt,sid,'mobile')];qr=QuantityRule(**version_on(rules['quantity_versions'][sid],dt,proxies)['rule']);q=x['growth_qty']
 while q and D(x['H_all_layers'])+D(x['whole_stock_principal_before'])+risk(sid,q,D(g['buy_proxy']),D(x['candidate_raw_floor']),dt)>D(x['R0'])+D('1e-8'):
  q=qr.buy_floor(q-1)
 x['strict_total_principal_R0_qty_DIAGNOSTIC_ONLY']=q
 relevant=[l for l in layer_details if l['point']==dt and l['sid']==sid]
 x['conditional_protected_profit_credit_NOT_CASH']=str(sum(max(D(0),D(l['stop_net'])-D(l['remaining_layer_cost'])) for l in relevant))
 x['minlot_growth_budget']=str(D('.25')*D(x['R0'])+D(x['minlot_U_post']))
 x['layer_sale_fee_convention']='Each layer has its own dated hypothetical stop-sale fee; conservative if multiple layers would share one actual sell order.'
 x['native_hard_caps']='sector mark-to-protection risk<=1% budgetNAV; probe risk<=0.5% budgetNAV; 10% previous-closeNAV cash reserve; original capital caps and pending reserves; no fixed per-stock principal-D cap'
 x['H_evidence']='No actual sell parts since exact current flat-to-held entry; no active-round split; reconstructed, not defaulted.'
 x['P_evidence']='Reserve/fill prefix reconciled; zero own-stock remaining orders before this candidate; other-stock reserves shown separately.'
print('RESULTS',json.dumps(allresults,ensure_ascii=False))
print('LAYERS',json.dumps(layer_details,ensure_ascii=False))
print('REALIZED',json.dumps(history_details,ensure_ascii=False))
oldcash=sum(D(str(r['cash_old'])) for r in json.loads((dest/'RESULTS.json').read_text())['results'])
newcash=sum(D(x['growth_cash']) for x in allresults[:12])
print('TOTAL12',json.dumps(dict(growth_nonzero=sum(x['growth_qty']>0 for x in allresults[:12]),growth_cash=str(newcash),growth_Dnew=str(sum(D(x['growth_Dnew']) for x in allresults[:12])),H=str(sum(D(x['H']) for x in allresults[:12])),L=str(sum(D(x['L']) for x in allresults[:12])),P=str(sum(D(x['P']) for x in allresults[:12])),strict_total_R0_nonzero_DIAGNOSTIC_ONLY=sum(x['strict_total_principal_R0_qty_DIAGNOSTIC_ONLY']>0 for x in allresults[:12]),static_cash_release_not_reassigned=str(oldcash-newcash),static_925_cash_not_an_account=str(D(ds['2024-09-25']['available'])+oldcash-newcash)),ensure_ascii=False))
