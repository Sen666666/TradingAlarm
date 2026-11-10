from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib,csv
P=Path(__file__).resolve().parent.parent;O=P/'independent_audit_allocation_v1';read=lambda p:json.loads(Path(p).read_text());out=[];replays={};fam=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','RETRY_TICKETS','RETAINED_AT_END','ADDITIONAL_EXIT','ADD_QUANTITY_LIMITS','FULL_CAP_VIOLATIONS']
for arm in ['A','B','D','E','F']:
 new=P/f'allocation_ablation_v1/run_{arm}_fact2';old=P/f'allocation_ablation_v1/run_{arm}_v1';q={}
 for n in fam:q[n]=read(new/'prior_prefix_replay'/(n+'.json'))==read(old/'full_prefix'/(n+'.json'));assert q[n],(arm,n)
 replays[arm]=dict(certified_through=read(old/'RUN_STATUS.json')['certified_through'],exact=q)
paths={a:P/f'allocation_ablation_v1/run_{a}_fact2/full_prefix' for a in ['A','B','D','E','F']};paths['M']=P/'mainline_candidate_v1/checkpoint_20240927'
for arm,f in paths.items():
 led=read(f/'DAY_LEDGER.json');orders=read(f/'ORDERS.json');sectors=read(f/'SECTOR_DAILY.json');cands=read(f/'CANDIDATES.json');end=led[-1]['day']
 for t in ['2024-09-23','2024-09-27','2024-10-08','2024-10-25']:
  rr=[x for x in led if x['day']<=t]
  if not rr or rr[-1]['day']!=t:continue
  row=rr[-1];peak=D(1200000);dd=D(0)
  for x in rr:peak=max(peak,D(x['NAV']));dd=max(dd,1-D(x['NAV'])/peak)
  se=[x for x in sectors if x['day']==t];big=max(se,key=lambda x:D(x['market_value']));oc=[x for x in cands if x['day']==t and x['phase']=='OPEN'];buy=[x for x in orders if x['day']==t and x['side'].startswith('BUY')]
  a=dict(arm=arm,day=t,certified_endpoint=end,NAV=row['NAV'],cash=row['cash'],shares=row['shares'],stocks=row['stocks'],weight_pct=row['weight_pct'],fees_to_date=row['fees_paid'],max_close_drawdown_pct=str(dd*100),largest_sector=big['sector51'],largest_sector_weight_pct=str(D(big['market_value'])/D(row['NAV'])*100),actual_day_buy_cost=str(-sum((D(x['cash_delta']) for x in buy),D(0))),semiconductor_day_seed_requests=sum(x['sector51']=='半导体' and x['event']=='SEED' for x in oc),semiconductor_day_seed_fills=sum(x['sector51']=='半导体' and x['side']=='BUY_SEED' for x in buy),battery_day_seed_requests=sum(x['sector51']=='动力电池' and x['event']=='SEED' for x in oc),battery_day_seed_fills=sum(x['sector51']=='动力电池' and x['side']=='BUY_SEED' for x in buy))
  out.append(a)
report=dict(result='PASS',common_comparable_date='2024-09-27',fact2_prior_replay_independently_equal=replays,rows=out,limitations=['Do not compare unequal final dates as if one completed period.','M is a separately pre-frozen combination, not a pure ablation and not a winner selected by these returns.','No current sample/classification PIT claim or exchange matching guarantee.','A/E/F end on10/25; B/D/M end on9/27 for different actual missing-source/fact exposures.'])
(O/'CERTIFIED_COMMON_DATE_COMPARISON.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
with (O/'CERTIFIED_COMMON_DATE_COMPARISON.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps([x for x in out if x['day']=='2024-09-27'],ensure_ascii=False,indent=2))
