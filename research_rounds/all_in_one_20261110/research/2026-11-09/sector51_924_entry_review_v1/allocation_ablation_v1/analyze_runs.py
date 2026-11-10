"""Read-only economic analysis of already exported arm accounts; writes reports only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,csv,sys,hashlib
sys.dont_write_bytecode=True
import pandas as pd
from allocation_rules import cohort_tags
O=Path(__file__).resolve().parent;Z=D(0);INITIAL=D(1200000)
SUFFIX=sys.argv[1] if len(sys.argv)>1 else 'v1'
REPORT=O if SUFFIX=='v1' else O/f'report_{SUFFIX}'
if REPORT!=O:REPORT.mkdir(exist_ok=True)
def read(p):return json.loads(Path(p).read_text())
def dec(x):return D(str(x))
def write(name,rows):
 (REPORT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str)+'\n')
 if rows and isinstance(rows,list):pd.DataFrame(rows).to_csv(O/(name+'.csv'),index=False)
def load_run(run):
 p=run/'full_prefix';names=['DAY_LEDGER','ORDERS','HOLDINGS','SECTOR_DAILY','ATTEMPTS','CANDIDATES','EQUITY_EVENTS','FULL_CAP_VIOLATIONS','ADDITIONAL_EXIT'];return {n:read(p/(n+'.json')) for n in names}
def before(rows,date):return [r for r in rows if r.get('day','')<=date]
def at(rows,date):return [r for r in rows if r.get('day')==date]
def sumd(rows,key):return sum((dec(r[key]) for r in rows),Z)
def metric(arm,data,date,scope):
 led=before(data['DAY_LEDGER'],date);end=led[-1];assert end['day']==date
 orders=before(data['ORDERS'],date);buys=[r for r in orders if r['side'].startswith('BUY')];sells=[r for r in orders if r['side'].startswith('SELL')]
 peak=INITIAL;mdd=Z;double=Z;single=Z;prev=INITIAL
 for row in led:
  nav=dec(row['NAV']);peak=max(peak,nav);mdd=min(mdd,nav/peak-1);tr=at(orders,row['day']);b=sumd([t for t in tr if t['side'].startswith('BUY')],'notional');s=sumd([t for t in tr if t['side'].startswith('SELL')],'notional');double+=(b+s)/prev;single+=max(b,s)/prev;prev=nav
 slip=sum((dec(t['notional'])*(D('.0005')/(D('1.0005') if t['side'].startswith('BUY') else D('.9995'))) for t in orders),Z)
 positions=at(data['HOLDINGS'],date);buybylot={r['lot_id']:r for r in buys};basis=sum((dec(h['qty'])/dec(buybylot[h['lot_id']]['qty'])*(-dec(buybylot[h['lot_id']]['cash_delta'])) for h in positions),Z)
 sector=at(data['SECTOR_DAILY'],date);maxsector=max(before(data['SECTOR_DAILY'],date),key=lambda r:dec(r['account_weight_pct']))
 contribution=sumd(sector,'marked_net_pnl');assert abs(contribution-(dec(end['NAV'])-INITIAL))<D('.0000001')
 return dict(arm=arm,scope=scope,cutoff=date,days=len(led),NAV=end['NAV'],profit=str(dec(end['NAV'])-INITIAL),return_pct=str((dec(end['NAV'])/INITIAL-1)*100),max_drawdown_pct=str(mdd*100),cash=end['cash'],receivable=end['receivable'],market_value=end['market_value'],weight_pct=end['weight_pct'],fees_paid=end['fees_paid'],slippage_proxy_cost=str(slip),fees_plus_slippage=str(slip+dec(end['fees_paid'])),gross_buy_all_in=str(-sumd(buys,'cash_delta')),sell_net_cash=str(sumd(sells,'cash_delta')),net_cash_invested=str(-sumd(orders,'cash_delta')),remaining_inventory_all_in_cost_basis=str(basis),seed_fills=sum(t['side']=='BUY_SEED' for t in orders),add_fills=sum(t['side']=='BUY_ADD' for t in orders),sell_fills=len(sells),rebalance_fills=0,single_turnover_pct=str(single*100),double_turnover_pct=str(double*100),max_sector_weight_pct=maxsector['account_weight_pct'],max_sector=maxsector['sector51'],max_sector_weight_day=maxsector['day'],sum_sector_contribution=str(contribution))
def round_rows(arm,data,date,source_sector):
 orders=before(data['ORDERS'],date);holds=at(data['HOLDINGS'],date);divs=[r for r in before(data['EQUITY_EVENTS'],date) if r['event']=='ACCRUE_NET80'];res=[]
 for a in data['ATTEMPTS']:
  if a['seed_day']>date:continue
  rid=a['id'];tr=[r for r in orders if r['round_id']==rid];pos=[r for r in holds if r['round_id']==rid];dv=sumd([r for r in divs if r.get('round_id')==rid],'receivable_delta');cash=sumd(tr,'cash_delta');mv=sumd(pos,'market_value');q=sum(r['qty'] for r in pos);tags=cohort_tags(signal_day=a['signal_day'],source_sector_name=source_sector[a['sid']])
  if not tags:continue
  for tag in tags:res.append(dict(arm=arm,cutoff=date,cohort=tag,round_id=rid,sid=a['sid'],sector51=a['sector51'],source_sector_name=source_sector[a['sid']],signal_day=a['signal_day'],seed_day=a['seed_day'],status='OPEN' if q else 'CLOSED',buy_all_in=str(-sumd([r for r in tr if r['side'].startswith('BUY')],'cash_delta')),sell_net_cash=str(sumd([r for r in tr if r['side'].startswith('SELL')],'cash_delta')),fees=str(sumd(tr,'fee')),NET80_entitlement=str(dv),remaining_qty=q,market_value=str(mv),round_cashflow=str(cash),closed_net=str(cash+dv) if not q else None,open_marked_net=str(cash+dv+mv) if q else None,total_marked_net=str(cash+dv+mv)))
 return res

def main():
 runs={p.name.split('_')[1]:p for p in O.glob(f'run_*_{SUFFIX}') if (p/'RUN_STATUS.json').exists()};datasets={a:load_run(p) for a,p in runs.items()};cut=min(d['DAY_LEDGER'][-1]['day'] for d in datasets.values());ro=pd.read_csv(O.parent/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv');source_sector=ro.set_index('symbol').sector_name.to_dict();sid_sector=ro.set_index('symbol').sector51.to_dict()
 metrics=[];daily=[];focus=[];signals=[];cohorts=[];blockers=[];false_exit=[]
 for a,d in datasets.items():
  end=d['DAY_LEDGER'][-1]['day'];metrics.append(metric(a,d,cut,'COMMON_CERTIFIED_DATE'))
  if end!=cut:metrics.append(metric(a,d,end,'OWN_LONGER_PREFIX_NOT_RANKABLE'))
  for point in ('2024-09-13','2024-09-23','2024-09-27','2024-10-08','2024-10-25','2024-10-31'):
   if any(x['day']==point for x in d['DAY_LEDGER']):metrics.append(metric(a,d,point,'DATED_CHECKPOINT'))
  peak=INITIAL
  for row in d['DAY_LEDGER']:
   peak=max(peak,dec(row['NAV']));daily.append(dict(arm=a,**row,drawdown_pct=str(100*(dec(row['NAV'])/peak-1))))
  for x in d['FULL_CAP_VIOLATIONS']:
   if x['day']=='2024-09-27' and sid_sector[x['sid']] in ('半导体','动力电池','电子元件材料','软件与IT服务','证券保险'):focus.append(dict(arm=a,sector51=sid_sector[x['sid']],**x))
  for x in d['CANDIDATES']:
   if x['phase']=='CLOSE' and x['event'] in ('A','B'):
    for tag in cohort_tags(signal_day=x['day'],source_sector_name=source_sector[x['sid']]):signals.append(dict(arm=a,cohort=tag,**x))
  cohorts += [dict(scope='COMMON_CERTIFIED_DATE', **x) for x in round_rows(a,d,cut,source_sector)]
  if end!=cut:cohorts += [dict(scope='OWN_LONGER_PREFIX_NOT_RANKABLE', **x) for x in round_rows(a,d,end,source_sector)]
  for x in read(runs[a]/'full_prefix/BLOCKED_DAY_ALL_ISSUES.json'):blockers.append(dict(arm=a,**x))
  if a=='E':
   false_exit=[dict(arm=a,**x) for x in d['ADDITIONAL_EXIT'] if x['incremental_exit']]
 write('UNIFIED_METRICS',metrics);write('ALL_ARMS_DAILY_NAV',daily);write('FOCUS_20240927_REQUESTS',focus);write('COHORT_ALL_SIGNALS',signals);write('COHORT_ALL_ROUNDS',cohorts);write('ACTUAL_BLOCKER_UNION_BY_ARM',blockers);write('E_INCREMENTAL_EXIT_PATHS_PENDING',false_exit)
 summaries=[]
 for a in datasets:
  for scope, tag in sorted(set((x['scope'],x['cohort']) for x in cohorts if x['arm']==a)):
   rr=[x for x in cohorts if x['arm']==a and x['cohort']==tag and x['scope']==scope];closed=[x for x in rr if x['status']=='CLOSED'];opened=[x for x in rr if x['status']=='OPEN']
   summaries.append(dict(arm=a,scope=scope,cohort=tag,cutoff=rr[0]['cutoff'],all_signal_count=sum(x['arm']==a and x['cohort']==tag and x['day']<=rr[0]['cutoff'] for x in signals),actual_rounds=len(rr),closed_rounds=len(closed),unfinished_rounds=len(opened),buy_all_in=str(sumd(rr,'buy_all_in')),sell_net_cash=str(sumd(rr,'sell_net_cash')),fees=str(sumd(rr,'fees')),NET80_entitlement=str(sumd(rr,'NET80_entitlement')),closed_net=str(sumd(closed,'closed_net')),closed_negative_component=str(sum((dec(x['closed_net']) for x in closed if dec(x['closed_net'])<0),Z)),closed_positive_component=str(sum((dec(x['closed_net']) for x in closed if dec(x['closed_net'])>0),Z)),unfinished_marked_net=str(sumd(opened,'open_marked_net')),unfinished_market_value=str(sumd(opened,'market_value')),all_rounds_marked_net=str(sumd(rr,'total_marked_net'))))
 write('COHORT_SUMMARY',summaries)
 union={}
 for b in blockers:
  key=(b['day'],b['sid'])
  if key not in union:union[key]=dict(day=b['day'],sid=b['sid'],sector51=b['sector51'],issues=b['issues'],actions=b['actions'],source_origin=b['source_origin'],previous_factor=b['previous_factor'],current_factor=b['current_factor'],action_path=b['action_path'],arm_exposures=[])
  union[key]['arm_exposures'].append({k:b[k] for k in ['arm','held_qty','pending_seed','retained_ticket']})
 write('ACTUAL_BLOCKER_REQUEST_UNION',list(union.values()))
 sectors=[]
 for a,d in datasets.items():
  for r in d['SECTOR_DAILY']:sectors.append(dict(arm=a,**r))
 write('ALL_ARMS_ALL50_SECTOR_DAILY',sectors)
 endpoint=[]
 for a,d in datasets.items():
  base23={r['sector51']:dec(r['marked_net_pnl']) for r in at(d['SECTOR_DAILY'],'2024-09-23')}
  for date in ('2024-10-08','2024-10-31',d['DAY_LEDGER'][-1]['day']):
   for r in at(d['SECTOR_DAILY'],date):
    if r['sector51'] in ('半导体','动力电池','电子元件材料','软件与IT服务','证券保险'):endpoint.append(dict(arm=a,cutoff=date,sector51=r['sector51'],market_value=r['market_value'],weight_pct=r['account_weight_pct'],cumulative_contribution=r['marked_net_pnl'],increment_since_0923=str(dec(r['marked_net_pnl'])-base23[r['sector51']]) if r['sector51'] in base23 else None))
 write('FOCUS_ENDPOINT_CONTRIBUTIONS',endpoint)
 write('ANALYSIS_STATUS',dict(common_certified_date=cut,arms=list(datasets),C='DISABLED',all_losses_and_winners_in_fixed_cohorts=True,own_longer_prefix_must_not_be_used_for_cross_arm_return_ranking=True,price_proxy_not_real_fills=True,source_roster_not_PIT=True))
 print(json.dumps(dict(common_certified_date=cut,arms=list(datasets),metrics=[x for x in metrics if x['scope']=='COMMON_CERTIFIED_DATE']),ensure_ascii=False))
if __name__=='__main__':main()
