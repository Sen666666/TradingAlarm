from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import json,sys,pandas as pd
P=Path(__file__).resolve().parent.parent;O=P/sys.argv[1];R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());c=read(R/'CANDIDATES.json');o=read(R/'ORDERS.json');ledger=read(R/'DAY_LEDGER.json');executed=any(x['day']=='2024-09-27' for x in ledger);ro=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv');sectors=sorted(ro[ro.eligible].sector51.unique());names=ro.set_index('symbol').name.to_dict();rows=[]
for sec in sectors:
 tickets=[x for x in c if x['day']=='2024-09-26' and x['phase']=='CLOSE' and x['sector51']==sec and x['event'] in ['A','B']];opens=[x for x in c if x['day']=='2024-09-27' and x['phase']=='OPEN' and x['sector51']==sec and x['event']=='SEED' and x['signal_day']=='2024-09-26'];rows.append(dict(sector51=sec,N=int((ro.sector51==sec).sum()),signal_day='2024-09-26',intended_OPEN='2024-09-27',OPEN_status='EXECUTED_CERTIFIED_PREFIX' if executed else 'NOT_EXECUTED_DAY_BLOCKED',new_A=sum(x['event']=='A' for x in tickets),new_B=sum(x['event']=='B' for x in tickets),held_no_new_attempt=sum(x['decision']=='HELD_NO_NEW_ATTEMPT' for x in tickets),I_failed_or_unknown=sum(x['decision']=='I_INELIGIBLE_OR_UNKNOWN' for x in tickets),unheld_I_pass=sum(x['decision'] not in ['HELD_NO_NEW_ATTEMPT','I_INELIGIBLE_OR_UNKNOWN'] for x in tickets),planned_SEED=sum(x['decision']=='PASS' for x in tickets),CLOSE_decisions=json.dumps(dict(Counter(x['decision'] for x in tickets)),ensure_ascii=False),actual_SEED_fills=sum(x['decision']=='PASS' for x in opens) if executed else None,OPEN_rejects=sum(x['decision']!='PASS' for x in opens) if executed else None,OPEN_decisions=json.dumps(dict(Counter(x['decision'] for x in opens)),ensure_ascii=False) if executed else None))
pd.DataFrame(rows).to_csv(O/'SEP27_ENTRY_FUNNEL_ALL50.csv',index=False)
sem=[dict(x,name=names[x['sid']]) for x in c if x['sector51']=='半导体' and ((x['phase']=='CLOSE' and x['day']=='2024-09-26') or (x['phase']=='OPEN' and x['day']=='2024-09-27'))];pd.DataFrame(sem).to_csv(O/'SEP27_SEMICONDUCTOR_ALL_DECISIONS.csv',index=False)
context=[]
for dt in ['2024-09-25','2024-09-26','2024-09-27']:
 if not any(x['day']==dt for x in ledger):continue
 os=[x for x in o if x['day']==dt];context.append(dict(day=dt,exit_net_cash=str(sum((D(x['cash_delta']) for x in os if x['side'].startswith('SELL')),D(0))),ADD_buy_cash=str(-sum((D(x['cash_delta']) for x in os if x['side']=='BUY_ADD'),D(0))),SEED_buy_cash=str(-sum((D(x['cash_delta']) for x in os if x['side']=='BUY_SEED'),D(0))),actual_orders=os))
report=dict(scope='FROZEN_EXPERIMENT_NOT_DEPLOYABLE_STRATEGY',certified_through=ledger[-1]['day'],semiconductor=next(x for x in rows if x['sector51']=='半导体'),funding_chain=context,not_executed_is_not_zero_fills=True,economic_rules_unchanged=True)
(O/'SEP27_FUNNEL_AND_FUNDING.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['semiconductor'],ensure_ascii=False))
