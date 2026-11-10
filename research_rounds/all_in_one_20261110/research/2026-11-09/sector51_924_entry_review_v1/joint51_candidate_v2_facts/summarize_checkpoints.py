from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
orders=read(R/'ORDERS.json');cand=read(R/'CANDIDATES.json');sectors=read(R/'SECTOR_DAILY.json');held=read(R/'HOLDINGS.json');ledger=read(R/'DAY_LEDGER.json');ro=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv');sm=ro.set_index('symbol').sector51.to_dict();pending=read(O/'prefix_20240923_once/PENDING_AT_END.json')
sep23=[]
for x in [x for x in sectors if x['day']=='2024-09-23']:
 s=x['sector51'];q=[o for o in orders if o['sector51']==s and o['day']<='2024-09-23'];x=dict(x,actual_ADDs_through_23=sum(o['side']=='BUY_ADD' for o in q),actual_SEEDs_through_23=sum(o['side']=='BUY_SEED' for o in q),pending_SEEDs_for_24=sum(sm[o['sid']]==s for o in pending));sep23.append(x)
pd.DataFrame(sep23).to_csv(O/'SEP23_ALL50_SECTOR_POSITIONS.csv',index=False);save(O/'SEP23_ALL50_SECTOR_POSITIONS.json',sep23)
cap=[]
for x in [x for x in sectors if x['day']=='2024-09-24']:
 x=dict(x,total_buy_cash=str(D(x['seed_buy_cash'])+D(x['add_buy_cash'])));cap.append(x)
pd.DataFrame(cap).to_csv(O/'SEP24_ALL50_CAPITAL_DESTINATIONS.csv',index=False);save(O/'SEP24_ALL50_CAPITAL_DESTINATIONS.json',cap)
falseplans=[x for x in cand if x.get('phase')=='CLOSE' and x.get('decision')=='ADD_PLANNED' and x.get('sector_state')==0];keys={(x['round_id'],x['day']) for x in falseplans};falsefills=[x for x in orders if x['side']=='BUY_ADD' and (x['round_id'],x['signal_day']) in keys]
summary=dict(scope='FROZEN_EXPERIMENT_NOT_DEPLOYABLE_STRATEGY',completed_through=ledger[-1]['day'],blockers=read(R/'BLOCKERS.json'),sep23=next(x for x in ledger if x['day']=='2024-09-23'),sep24=ledger[-1],sep23_held_sectors=sum(x['stocks']>0 for x in sep23),sep23_actual_ADDs_by_sector=dict(Counter(x['sector51'] for x in orders if x['side']=='BUY_ADD' and x['day']<='2024-09-23')),sep23_CLOSE_ADD_gate_counts=dict(Counter(x['decision'] for x in cand if x['day']=='2024-09-23' and x['event']=='ADD_GATE')),sep23_software_A_decisions=dict(Counter(x['decision'] for x in cand if x['day']=='2024-09-23' and x['event']=='A' and x['sector51']=='软件与IT服务')),sep24_buy_cash=str(sum((D(x['total_buy_cash']) for x in cap),D(0))),sep24_seed_cash=str(sum((D(x['seed_buy_cash']) for x in cap),D(0))),sep24_add_cash=str(sum((D(x['add_buy_cash']) for x in cap),D(0))),sep24_actual_seed_fills=sum(x['seeds_filled'] for x in cap),sep24_actual_add_fills=sum(x['adds_filled'] for x in cap),sep24_OPEN_rejections=dict(Counter((x['sector51']+'|'+x['decision']) for x in cand if x['day']=='2024-09-24' and x['phase']=='OPEN' and x['decision']!='PASS')),FALSE_sector_ADD_plans=falseplans,FALSE_sector_actual_ADDs=falsefills,small_N_edge_not_modified=True,no_PIT_or_real_fill_certification=True)
save(O/'CHECKPOINT_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False))
