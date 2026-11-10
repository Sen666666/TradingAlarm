from pathlib import Path
from decimal import Decimal as D
import csv,json,statistics
O=Path(__file__).resolve().parent;Z=D(0);rows=list(csv.DictReader((O/'full/unit-ledgers.csv').open()));ix={(r['cycle_id'],r['cost'],r['arm']):r for r in rows};ids=list(dict.fromkeys(r['cycle_id'] for r in rows));pairs=[]
def metric(v):return dict(net=sum(v,Z),gain=sum((x for x in v if x>0),Z),negative_loss=-sum((x for x in v if x<0),Z),benefit=sum(x>0 for x in v),harm=sum(x<0 for x in v),equal=sum(x==0 for x in v),min=min(v),max=max(v))
def risk(g):return dict(mean_min_return=statistics.mean(D(x['min_full_cycle_return']) for x in g),worst_min_return=min(D(x['min_full_cycle_return']) for x in g),mean_max_DD=statistics.mean(D(x['max_full_cycle_DD']) for x in g),worst_max_DD=max(D(x['max_full_cycle_DD']) for x in g),mean_holding_observations=statistics.mean(int(x['holding_close_observations']) for x in g))
for key in ids:
 for cost in ['1','2']:
  a,b=ix[key,cost,'A'],ix[key,cost,'B'];delta=D(b['full_cycle_net'])-D(a['full_cycle_net']);pairs.append(dict(cycle_id=key,symbol=a['symbol'],name=a['name'],cost=int(cost),triggered=a['triggered']=='True',trigger=a['trigger'],unknown_event_days=a['unknown_event_days'],unknown_before_first=a['unknown_before_first'],previous32=a['previous32']=='True',original_tail30=a['original_tail30']=='True',original_profitable=a['original_profitable']=='True',original_entry=a['original_entry'],original_exit=a['original_exit'],B_first_sell=b['first_sell'],B_last_sell=b['last_sell'],B_fill_count=b['sell_fill_count'],A_net=D(a['full_cycle_net']),B_net=D(b['full_cycle_net']),B_minus_A=delta,return_difference=delta/D(a['initial_actual_cost']),A_fees=D(a['full_fees']),B_fees=D(b['full_fees']),A_dividend=D(a['dividend']),B_dividend=D(b['dividend']),A_min_return=a['min_full_cycle_return'],B_min_return=b['min_full_cycle_return'],A_DD=a['max_full_cycle_DD'],B_DD=b['max_full_cycle_DD']))
with (O/'cycle-differences.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
summary={}
targets=['605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03']
for cost in [1,2]:
 g=[p for p in pairs if p['cost']==cost];groups={
 'all69':g,'triggered57':[x for x in g if x['triggered']],'no_trigger12':[x for x in g if not x['triggered']],
 'previously_paired32_first_old_trigger':[x for x in g if x['triggered'] and x['previous32']],
 'previously_unpaired25':[x for x in g if x['triggered'] and not x['previous32']],
 'original_tail30':[x for x in g if x['original_tail30']],
 'original_loss':[x for x in g if not x['original_profitable']],
 'original_small_profit':[x for x in g if x['original_profitable'] and not x['original_tail30']],
 'targets3':[x for x in g if x['cycle_id'] in targets]}
 out={}
 for label,gg in groups.items():
  out[label]=dict(cycles=len(gg),difference=metric([x['B_minus_A'] for x in gg]),A_net=sum((x['A_net'] for x in gg),Z),B_net=sum((x['B_net'] for x in gg),Z),event_equal_mean_return_difference=statistics.mean(x['return_difference'] for x in gg))
 arms={}
 for arm in ['A','B']:
  ar=[x for x in rows if int(x['cost'])==cost and x['arm']==arm]
  arms[arm]=dict(net=metric([D(x['full_cycle_net']) for x in ar]),fees=sum((D(x['full_fees']) for x in ar),Z),dividend=sum((D(x['dividend']) for x in ar),Z),risk=risk(ar),unclosed=sum(int(x['final_shares'])>0 for x in ar))
 summary[str(cost)]=dict(groups=out,arms=arms,targets=[x for x in g if x['cycle_id'] in targets],largest_harms=sorted(g,key=lambda x:x['B_minus_A'])[:3],largest_benefits=sorted(g,key=lambda x:x['B_minus_A'],reverse=True)[:3],triggered_exit_fills=dict(__import__('collections').Counter(x['B_fill_count'] for x in g if x['triggered'])))
(O/'RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str));print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
