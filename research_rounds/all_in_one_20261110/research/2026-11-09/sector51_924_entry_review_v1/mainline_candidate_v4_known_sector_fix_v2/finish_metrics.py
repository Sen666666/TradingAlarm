"""Descriptive actual-path comparison only; not causal attribution or an alternate portfolio."""
from pathlib import Path
from decimal import Decimal as D
import json,pandas as pd
O=Path(__file__).resolve().parent;P=O/'once_20241008';B=O.parent/'mainline_candidate_v3_core_reference/once_20241008';Z=D(0)
read=lambda p:json.loads(p.read_text())
def write(n,v):
 (O/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str));
 if isinstance(v,list):pd.DataFrame(v).to_csv(O/(n+'.csv'),index=False)
def boolean(x):
 if x is True or x=='True':return True
 if x is False or x=='False':return False
 raise ValueError(x)
days=['2024-09-23','2024-09-27','2024-09-30','2024-10-08'];out=[];scompare=[];states=[];fail=[];op=[]
for arm,p in [('M3',B),('M4',P)]:
 orders=read(p/'ORDERS.json');at=read(p/'ATTEMPTS.json');holds=read(p/'HOLDINGS.json');lots=read(p/'CAPITAL_LOTS.json');ss=read(p/'SECTOR_DAILY.json');ledger=read(p/'DAY_LEDGER.json');cp=read(p/'INFORMATION_CONFIRMATIONS.json')
 for d in days:
  l=next(l for l in ledger if l['day']==d);hs=[h for h in holds if h['day']==d];lr=[x for x in lots if x['day']==d];roundids={h['round_id'] for h in hs};confirmed={x['round_id'] for x in cp if x['day']<=d and x['decision']=='INFORMATION_CONFIRMED'};added={t['round_id'] for t in orders if t['day']<=d and t['side']=='BUY_ADD'};currentadd={h['round_id'] for h in hs if h['kind']=='ADD'}
  for label,ids in [('UNCONFIRMED_NEVER_ADD',roundids-confirmed-added),('CONFIRMED_NEVER_ADD',(roundids&confirmed)-added),('CURRENT_ADD',currentadd),('EVER_ADD_NOW_SEED_ONLY',(roundids&added)-currentadd)]:
   rs=[h for h in hs if h['round_id'] in ids];states.append(dict(arm=arm,day=d,state=label,stocks=len({h['sid'] for h in rs}),rounds=len(ids),shares=sum(h['qty'] for h in rs),market_value=sum((D(h['market_value']) for h in rs),Z),weight_pct=100*sum((D(h['market_value']) for h in rs),Z)/D(l['NAV'])))
  out.append(dict(arm=arm,**l,winner_core=sum((D(x['core_value']) for x in lr),Z),mobile_ADD=sum((D(x['mobile_value']) for x in lr if x['kind']=='ADD'),Z),actual_seed_market_value=sum((D(h['market_value']) for h in hs if h['kind']=='SEED'),Z),current_trend_winner_count=len({x['round_id'] for x in lr if boolean(x['current_winner'])})))
  for sec in [s for s in ss if s['day']==d]:scompare.append(dict(arm=arm,**sec))
 closed=[a for a in at if a['final_qty']==0];noadd=[a for a in closed if a['add_count']==0];neg=[a for a in noadd if D(a['marked_net_pnl'])<0]
 for label,group in [('ALL_CLOSED',closed),('CLOSED_NO_ADD_TRIALS',noadd),('LOSING_CLOSED_NO_ADD_TRIALS',neg)]:
  ids={a['id'] for a in group};ts=[t for t in orders if t['round_id'] in ids];fail.append(dict(arm=arm,group=label,rounds=len(group),net=sum((D(a['marked_net_pnl']) for a in group),Z),fees=sum((D(t['fee']) for t in ts),Z),slippage=sum((abs(D(t['price'])-D(t['price'])/(D('1.0005') if t['side'].startswith('BUY') else D('.9995')))*t['qty'] for t in ts),Z),worst_round=min((D(a['marked_net_pnl']) for a in group),default=None)))
 write(arm+'_ALL_CLOSED_TRIAL_ROUNDS',[a for a in noadd]);write(arm+'_LOSING_CLOSED_TRIAL_ROUNDS',neg)
write('FOUR_DAY_STATE_COMPARISON',states);write('FOUR_DAY_ACCOUNT_COMPARISON',out);write('ALL50_FOUR_DAY_COMPARISON',scompare);write('FAILURE_AND_CLOSED_COST_COMPARISON',fail)
m4held={a['sid'] for a in read(P/'ATTEMPTS.json') if a['final_qty']>0};m3held={a['sid'] for a in read(B/'ATTEMPTS.json') if a['final_qty']>0}
for arm,path,other in [('M3',B,m4held),('M4',P,m3held)]:
 for a in read(path/'ATTEMPTS.json'):
  if a['final_qty']>0 and a['sid'] not in other:op.append(dict(arm=arm,**a,interpretation='Actual marked contribution of names absent from other final portfolio, NOT a funded counterfactual or isolated effect of selecting fewer stocks.'))
write('BREADTH_OPPORTUNITY_DESCRIPTIVE',op)
ev=read(P/'EVENT_REGISTRY.json');seeds=read(P/'SEED_FLOOR_RISK.json');adds=read(P/'ADD_FLOOR_RISK.json');summary=dict(events=len(ev),priority_attempted=sum(x['priority_attempted'] for x in ev.values()),attempted_without_event_spend=sum(x['priority_attempted'] and D(x['spent'])==0 for x in ev.values()),cold_events=sum(x['cold_start'] for x in ev.values()),event_spent=sum((D(x['spent']) for x in ev.values()),Z),event_pending_reserved=sum((D(x['reserved']) for x in ev.values()),Z),seed_orders=len(seeds),seed_positive_known_floor_risk=sum(D(x['incremental_known_floor_loss'])>0 for x in seeds),seed_max_known_floor_loss=max((D(x['incremental_known_floor_loss']) for x in seeds),default=Z),ADD_orders=len(adds),ADD_risk_exceeds_existing_profit=sum(x['not_profit_covered'] for x in adds),ADD_max_known_floor_loss=max((D(x['incremental_known_floor_loss']) for x in adds),default=Z),known_floor_loss_is_not_guaranteed_stop_fill=True)
write('EVENT_AND_PRINCIPAL_RISK_SUMMARY',summary);print(json.dumps(dict(failure=fail,risk=summary,state=[x for x in states if x['day']=='2024-10-08']),ensure_ascii=False,default=str))
