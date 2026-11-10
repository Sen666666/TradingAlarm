from pathlib import Path
import json,gzip,hashlib
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent
A=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1/run_1200000/pair/PVR.json.gz')
t=pd.read_csv(O/'ORDERS.csv');daily=pd.read_csv(O/'DAILY.csv');acct=pd.read_csv(O/'ACCOUNT_CASES_ONLY.csv');checks=[]
for run,x in t.groupby('run',sort=False):
 q={};cost={};pnl={};lastbuy={};cash=1200000.
 for r in x.to_dict('records'):
  s=r['sid'];q.setdefault(s,0);cost.setdefault(s,0.);pnl.setdefault(s,0.)
  if r['action']in ['REJECT','REJECT_SELL']:continue
  assert r['signal']<r['day'];assert r['q']%100==0
  if r['action']in ['PROBE','ADD']:
   assert r['risk']<=r['budget']+1e-6
   assert r['post_campaign_stress_loss']<=r['campaign_principal_cap']+1e-6
   if r['action']=='ADD':assert q[s]>0 and r['U']>0
   else:assert q[s]==0
   paid=r['gross']+r['fee'];cost[s]+=paid;cash-=paid;q[s]+=r['q'];lastbuy[s]=r['day']
   assert abs(r['total_cost']-cost[s])<1e-6
  else:
   assert r['q']==q[s] and lastbuy[s]<r['day']
   net=r['gross']-r['fee'];realized=net-cost[s];assert abs(realized-r['pnl'])<1e-6
   cash+=net;pnl[s]+=realized;q[s]=0;cost[s]=0.
 assert all(v==0 for v in q.values())
 end=acct[acct.run.eq(run)].iloc[-1]
 assert abs(cash-end.equity)<1e-6
 assert abs(cash-1200000-sum(pnl.values()))<1e-6
 ar=acct[acct.run.eq(run)].copy();prev=ar.equity.shift().fillna(1200000)
 assert (ar.new_gross<=.1*prev+1e-6).all();assert(ar.new_probe_risk<=.0025*prev+1e-6).all()
 checks.append(dict(run=run,arithmetic='pass',cash_end=cash,net_pnl=sum(pnl.values()),buys=int(x.action.isin(['PROBE','ADD']).sum()),add_count=int(x.action.eq('ADD').sum()),all_adds_existing_stock_net_positive=True,next_day_and_Tplus1=True,same_day_gross_and_probe_risk_caps=True))
a=json.load(gzip.open(A,'rt'));cases=[('300085.SZ','2024-09-18','2024-10-14'),('002583.SZ','2024-09-18','2024-11-05'),('600675.SH','2022-04-07','2022-04-21'),('601298.SH','2023-04-25','2023-05-31')];context=[]
for sid,start,end in cases:
 trades=[r for r in a['trades']if r['security_id']==sid and start<=r['at'][:10]<=end]
 lids={r['layer']for r in trades if r['side']=='buy'}|{p['layer']for r in trades for p in r.get('parts',[])}
 related=[r for r in a['trades']if r['security_id']==sid and (r.get('layer')in lids or any(p['layer']in lids for p in r.get('parts',[])))]
 net=sum((D(r['gross_cny'])-D(r['fees_cny'])if r['side']=='sell'else -D(r['gross_cny'])-D(r['fees_cny'])for r in trades),D(0))
 context.append(dict(sid=sid,start=start,end=end,window_trade_net_cash=str(net),warning='Window cash flow is not profit if holdings enter or leave the window; original continuous account uses all other stocks, native pool gates and its current NAV, whereas candidate is selected-path cash-reset arithmetic.',window_trades=trades,related_layer_trades=related))
(O/'CHECKS.json').write_text(json.dumps(checks,indent=2));(O/'ORIGINAL_1200000_CONTEXT.json').write_text(json.dumps(context,ensure_ascii=False,indent=2))
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [A,O/'run_bounded.py',O/'verify_and_context.py',O/'FREEZE.json',O/'SUMMARY.json',O/'ORDERS.csv',O/'DAILY.csv',O/'ACCOUNT_CASES_ONLY.csv']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(checks,indent=2));print([(x['sid'],x['window_trade_net_cash'])for x in context]);
for run in ['300085.SZ','002583.SZ','600675.SH','601298.SH']:
 x=daily[daily.run.eq(run)];i=x.unrealized.idxmax();print('PEAK',daily.loc[i,['run','day','q','nominal','cost','unrealized','realized','stress_scenario_pnl']].to_dict())
