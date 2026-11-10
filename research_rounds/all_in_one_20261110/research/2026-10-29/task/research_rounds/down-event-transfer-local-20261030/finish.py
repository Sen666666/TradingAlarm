"""Summarize the single completed 32-event run; no additional paths."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,statistics,hashlib
from collections import Counter
O=Path(__file__).resolve().parent;Z=D(0);rows=list(csv.DictReader((O/'full/arm-endpoints.csv').open()));index={(r['cycle_id'],r['cost'],r['arm'],r['view']):r for r in rows};cycles=list(dict.fromkeys(r['cycle_id'] for r in rows));pairs=[]
def sumd(g,k):return sum((D(x[k]) for x in g),Z)
def metric(v):
 return dict(net=sum(v,Z),positive=sum((x for x in v if x>0),Z),negative_loss=-sum((x for x in v if x<0),Z),positive_events=sum(x>0 for x in v),negative_events=sum(x<0 for x in v),zero_events=sum(x==0 for x in v),median=statistics.median(v),minimum=min(v),maximum=max(v))
for cycle in cycles:
 for cost in ['1','2']:
  for view in ['H21','Hfull']:
   a,b,c=[index[cycle,cost,k,view] for k in ['A','B','C']];I0=D(a['initial_equity']);assert I0==D(b['initial_equity'])==D(c['initial_equity']);ba=D(b['final_equity'])-D(a['final_equity']);cb=D(c['final_equity'])-D(b['final_equity']);ca=D(c['final_equity'])-D(a['final_equity']);assert ba+cb==ca
   pairs.append(dict(cycle_id=cycle,trigger=a['trigger'],old=a['old'],new=a['new'],old_name=a['old_name'],new_name=a['new_name'],cost=int(cost),view=view,endpoint=a['endpoint'],initial_equity=I0,B_minus_A=ba,C_minus_B=cb,C_minus_A=ca,B_minus_A_return=ba/I0,C_minus_B_return=cb/I0,C_minus_A_return=ca/I0,net_liquidation_C_minus_A=D(c['estimated_net_liquidation_equity'])-D(a['estimated_net_liquidation_equity']),original_tail30=a['original_tail30']=='True',original_cycle_return=a['original_cycle_return'],A_post_trigger_pnl=a['post_trigger_pnl'],B_post_trigger_pnl=b['post_trigger_pnl'],C_post_trigger_pnl=c['post_trigger_pnl'],A_DD=a['max_local_drawdown'],B_DD=b['max_local_drawdown'],C_DD=c['max_local_drawdown'],A_min_return=a['min_trigger_return'],B_min_return=b['min_trigger_return'],C_min_return=c['min_trigger_return'],A_fees=a['fees'],B_fees=b['fees'],C_fees=c['fees'],old_sale_net=c['old_sale_net'],new_buy_spend=c['new_buy_spend'],unused_sale_cash=D(c['old_sale_net'])-D(c['new_buy_spend']),new_initial_qty=c['new_initial_qty'],attempt_status=c['attempt_status'],new_status=c['new_status']))
with (O/'paired-differences.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
summary={}
for cost in [1,2]:
 summary[str(cost)]={}
 for view in ['H21','Hfull']:
  g=[x for x in pairs if x['cost']==cost and x['view']==view];gg=[x for x in rows if int(x['cost'])==cost and x['view']==view];arms={}
  for arm in ['A','B','C']:
   ar=[x for x in gg if x['arm']==arm];arms[arm]=dict(post_trigger_pnl=metric([D(x['post_trigger_pnl']) for x in ar]),mean_post_trigger_return=statistics.mean(D(x['post_trigger_return']) for x in ar),fees=sumd(ar,'fees'),slippage=sumd(ar,'slippage'),mean_min_trigger_return=statistics.mean(D(x['min_trigger_return']) for x in ar),worst_trigger_return=min(D(x['min_trigger_return']) for x in ar),mean_max_local_DD=statistics.mean(D(x['max_local_drawdown']) for x in ar),worst_max_local_DD=max(D(x['max_local_drawdown']) for x in ar),mean_holding_close_observations=statistics.mean(int(x['holding_close_observations']) for x in ar),mean_cash_only_close_observations=statistics.mean(int(x['cash_only_close_observations']) for x in ar),inventory_yuan_observations=sumd(ar,'inventory_yuan_observations'),terminal_inventory=sumd(ar,'inventory'),terminal_claim=sumd(ar,'claim'),terminal_sale_receivable=sumd(ar,'sale_receivable'),estimated_liquidation_fees=sumd(ar,'estimated_liquidation_fee'),estimated_liquidation_slippage=sumd(ar,'estimated_liquidation_slippage'))
  effects={k:metric([x[k] for x in g])|dict(event_equal_mean_return=statistics.mean(x[k+'_return'] for x in g),initial_equity_weighted_return=sum((x[k] for x in g),Z)/sum((x['initial_equity'] for x in g),Z)) for k in ['B_minus_A','C_minus_B','C_minus_A']}
  tails={label:dict(events=len(sub),**{k:metric([x[k] for x in sub]) for k in ['B_minus_A','C_minus_B','C_minus_A']}) for label,sub in [('original_tail30',[x for x in g if x['original_tail30']]),('other',[x for x in g if not x['original_tail30']])]}
  bystock=Counter();bydate=Counter()
  for x in g:bystock[x['old']]+=x['C_minus_A'];bydate[x['trigger']]+=x['C_minus_A']
  summary[str(cost)][view]=dict(events=len(g),total_initial_equity=sum((x['initial_equity'] for x in g),Z),effects=effects,arms=arms,original_tail_split=tails,estimated_net_liquidation_C_minus_A=metric([x['net_liquidation_C_minus_A'] for x in g]),C_attempts=dict(Counter(x['attempt_status'] for x in g)),C_buy_status=dict(Counter(x['new_status'] for x in g)),unused_sale_cash=sum((x['unused_sale_cash'] for x in g),Z),mean_sale_cash_reinvested_fraction=statistics.mean(D(x['new_buy_spend'])/D(x['old_sale_net']) for x in g if D(x['old_sale_net'])>0),stock_delta=dict(bystock),date_delta=dict(bydate),largest_positive_cases=sorted(g,key=lambda x:x['C_minus_A'],reverse=True)[:3],largest_negative_cases=sorted(g,key=lambda x:x['C_minus_A'])[:3])
(O/'RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str));compact={co:{vi:{k:v for k,v in s.items() if k in ['events','effects','original_tail_split','C_attempts','C_buy_status','unused_sale_cash','mean_sale_cash_reinvested_fraction']} for vi,s in vs.items()} for co,vs in summary.items()};print(json.dumps(compact,ensure_ascii=False,default=str),flush=True)
