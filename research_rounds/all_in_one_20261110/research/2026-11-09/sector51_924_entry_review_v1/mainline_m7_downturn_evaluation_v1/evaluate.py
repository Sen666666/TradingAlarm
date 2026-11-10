"""Post-run descriptive accounting. Never imported by the frozen strategy."""
from pathlib import Path
from decimal import Decimal as D
import json, csv, hashlib, argparse
O=Path(__file__).resolve().parent;ROOT=O.parent;Z=D(0);INIT=D(1200000);ANCHOR='2024-10-08'
p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();P=ROOT/a.run/'once_20241031'
names=['DAY_LEDGER','SECTOR_DAILY','HOLDINGS','ORDERS','EQUITY_EVENTS','ATTEMPTS','CAPITAL_LOTS','ADD_FLOOR_RISK','SEED_FLOOR_RISK','BLOCKERS'];data={n:json.loads((P/(n+'.json')).read_text()) for n in names}
ledger=data['DAY_LEDGER'];base=next(x for x in ledger if x['day']==ANCHOR);base_nav=D(base['NAV']);lastday=ledger[-1]['day'];out=O/(a.run+'__'+lastday);out.mkdir(exist_ok=True)
def save(n,x):
 (out/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (out/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
summary=[];cash=INIT;recv=fees=slip=Z;peak=INIT;dd=Z;prev=INIT;quant={};checks=0
for row in ledger:
 ds=row['day'];orders=[r for r in data['ORDERS'] if r['day']==ds]
 for t in orders:
  cash+=D(t['cash_delta']);fees+=D(t['fee']);sgn=1 if t['side'].startswith('BUY') else -1;quant[t['sid']]=quant.get(t['sid'],0)+sgn*t['qty'];slip+=abs(D(t['price'])-D(t['price'])/(D('1.0005') if sgn==1 else D('.9995')))*t['qty']
 for e in data['EQUITY_EVENTS']:
  if e['day']==ds:cash+=D(e.get('cash_delta',0));recv+=D(e.get('receivable_delta',0))
 hs=[r for r in data['HOLDINGS'] if r['day']==ds];hq={}
 for h in hs:hq[h['sid']]=hq.get(h['sid'],0)+h['qty']
 assert hq=={s:q for s,q in quant.items() if q};checks+=1
 nav=cash+recv+sum((D(r['market_value']) for r in hs),Z)
 assert nav==D(row['NAV']) and cash==D(row['cash']) and recv==D(row['receivable']) and fees==D(row['fees_paid']);checks+=4
 assert sum((D(r['marked_net_pnl']) for r in data['SECTOR_DAILY'] if r['day']==ds),Z)==nav-INIT;checks+=1
 peak=max(peak,nav);dd=min(dd,nav/peak-1);roles=[r for r in data['CAPITAL_LOTS'] if r['day']==ds]
 if ds>=ANCHOR:
  summary.append(dict(**row,daily_return_pct=100*(nav/prev-1),cumulative_return_pct=100*(nav/INIT-1),since_1008_return_pct=100*(nav/base_nav-1),running_max_close_drawdown_pct=100*dd,total_cost_fees_plus_open_5bp_proxy=fees+slip,buy_cash=sum((-D(t['cash_delta']) for t in orders if t['side'].startswith('BUY')),Z),sell_cash=sum((D(t['cash_delta']) for t in orders if t['side'].startswith('SELL')),Z),buy_seed_count=sum(t['side']=='BUY_SEED' for t in orders),buy_add_count=sum(t['side']=='BUY_ADD' for t in orders),sell_count=sum(t['side'].startswith('SELL') for t in orders),core_value=sum((D(r['core_value']) for r in roles),Z),frozen_value=sum((D(r['frozen_value']) for r in roles),Z),mobile_value=sum((D(r['mobile_value']) for r in roles),Z)))
 prev=nav
old={r['sector51']:r for r in data['SECTOR_DAILY'] if r['day']==ANCHOR};sectors=[]
for r in data['SECTOR_DAILY']:
 if r['day']>ANCHOR:
  q=old[r['sector51']];sectors.append(dict(**r,since_1008_net_contribution=D(r['marked_net_pnl'])-D(q['marked_net_pnl']),weight_1008=q['account_weight_pct'],M_1008=q['M']))
trades=[r for r in data['ORDERS'] if r['day']>ANCHOR];closed=[r for r in data['ATTEMPTS'] if r['final_qty']==0 and r.get('exit_day','')>ANCHOR];trial=[r for r in closed if r['add_count']==0 and D(r['marked_net_pnl'])<0]
risk=[r for r in data['ADD_FLOOR_RISK'] if r['day']>ANCHOR]
report=dict(run=a.run,verified_last_day=lastday,planned_end='2024-10-31',completed=lastday=='2024-10-31',blockers=data['BLOCKERS'],account_checks=checks,final=summary[-1],post1008_closed_rounds=len(closed),post1008_closed_round_net=sum((D(r['marked_net_pnl']) for r in closed),Z),post1008_closed_losing_no_add_rounds=len(trial),post1008_closed_losing_no_add_net=sum((D(r['marked_net_pnl']) for r in trial),Z),post1008_adds=len(risk),post1008_adds_exceed_prior_profit=sum(r['not_profit_covered'] for r in risk),max_post1008_add_known_floor_loss=max((D(r['incremental_known_floor_loss']) for r in risk),default=Z),caveats=['Core value is a subset of frozen value; do not add them twice.','Current non-PIT universe and industry mapping remain.','Rules frozen at M7, but previously selected parameters are not claimed out-of-sample.','Conditional OPEN with +/-5bp proxy is not certified execution.','Close-to-close drawdown is not intraday drawdown.','Closed round PnL spans the entire round, not just post10/8.','Known protection risk is not a guaranteed stop fill.'])
save('DAILY_ACCOUNT',summary);save('ALL50_POST1008_SECTORS',sectors);save('POST1008_ORDERS',trades);save('POST1008_CLOSED_ROUNDS',closed);save('SUMMARY',report);save('SOURCE_HASHES',{str(P/(n+'.json')):hashlib.sha256((P/(n+'.json')).read_bytes()).hexdigest() for n in names});print(json.dumps(report,ensure_ascii=False,default=str))
