"""Post-run audit/report only, never used as strategy input."""
from pathlib import Path
from decimal import Decimal as D
import json,sys,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;P=O/(sys.argv[1] if len(sys.argv)>1 else 'once_20241008');Z=D(0);INITIAL=D(1200000)
def read(p):return json.loads(p.read_text())
def save(n,x):(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def csv(n,x):pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
fams=['ORDERS','DAY_LEDGER','HOLDINGS','ATTEMPTS','EQUITY_EVENTS','SECTOR_DAILY','FUNDING_REQUESTS','INFORMATION_CONFIRMATIONS','ADD_FLOOR_RISK','REFERENCE_DAILY','CAPITAL_LOTS','REFERENCE_REQUESTS','TRANSFERS','CANDIDATES']
v={n:read(P/(n+'.json')) for n in fams};ro=pd.read_csv(R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv').set_index('symbol')
orders=v['ORDERS'];cash=INITIAL;recv=Z;fees=Z;slip=Z;peak=INITIAL;maxdd=Z;shares={};out=[];turn=Z;prevnav=INITIAL
for l in v['DAY_LEDGER']:
 day=l['day'];ts=[t for t in orders if t['day']==day]
 for t in ts:
  cash+=D(t['cash_delta']);fees+=D(t['fee']);buy=t['side'].startswith('BUY');shares[t['sid']]=shares.get(t['sid'],0)+(t['qty'] if buy else -t['qty']);assert shares[t['sid']]>=0
  raw=D(t['price'])/(D('1.0005') if buy else D('.9995'));slip+=abs(D(t['price'])-raw)*t['qty']
 for a in v['EQUITY_EVENTS']:
  if a['day']==day:cash+=D(a.get('cash_delta',0));recv+=D(a.get('receivable_delta',0))
 hs=[h for h in v['HOLDINGS'] if h['day']==day];q={}
 for h in hs:q[h['sid']]=q.get(h['sid'],0)+h['qty']
 assert q=={s:q for s,q in shares.items() if q};mv=sum((D(h['market_value']) for h in hs),Z);nav=cash+recv+mv;assert nav==D(l['NAV']) and cash==D(l['cash']) and recv==D(l['receivable']) and fees==D(l['fees_paid'])
 peak=max(peak,nav);dd=nav/peak-1;maxdd=min(maxdd,dd);turn+=sum((D(t['notional']) for t in ts),Z)/prevnav;prevnav=nav
 ss=[s for s in v['SECTOR_DAILY'] if s['day']==day];assert sum((D(s['marked_net_pnl']) for s in ss),Z)==nav-INITIAL
 out.append(dict(**l,return_pct=100*(nav/INITIAL-1),drawdown_pct=100*dd,running_max_drawdown_pct=100*maxdd,fees=fees,slippage_proxy=slip,total_cost=fees+slip,two_way_turnover=turn,peak_sector=max(ss,key=lambda s:D(s['account_weight_pct']))))
csv('DAILY_ACCOUNT_METRICS',out);save('ENDPOINTS',{r['day']:r for r in out if r['day'] in ['2024-09-23','2024-09-27','2024-09-30','2024-10-08']})
keydays=['2024-09-23','2024-09-27','2024-09-30','2024-10-08'];key=[]
for day in keydays:
 for s in [s for s in v['SECTOR_DAILY'] if s['day']==day]:
  sec=s['sector51'];lots=[r for r in v['CAPITAL_LOTS'] if r['day']==day and r['sector51']==sec];ref=next(r for r in v['REFERENCE_DAILY'] if r['day']==day and r['sector51']==sec);req=[r for r in v['FUNDING_REQUESTS'] if r['day']==day and ro.loc[r['sid'],'sector51']==sec];tt=[t for t in orders if t['day']==day and t['sector51']==sec]
  key.append(dict(**s,actual_unconfirmed_seed=sum((D(r['market_value']) for r in lots if r['kind']=='SEED' and not r['confirmed_history']),Z),winner_core=sum((D(r['core_value']) for r in lots),Z),mobile_ADD=sum((D(r['mobile_value']) for r in lots if r['kind']=='ADD'),Z),T=ref['T'],T_unused=max(Z,D(ref['T'])-D(s['market_value'])),buy_SEED_all_in=-sum((D(t['cash_delta']) for t in tt if t['side']=='BUY_SEED'),Z),buy_ADD_all_in=-sum((D(t['cash_delta']) for t in tt if t['side']=='BUY_ADD'),Z),donor_net=sum((D(t['cash_delta']) for t in tt if t.get('transfer_rank')),Z),requested=len(req),filled=sum(r['executed_q']>0 for r in req),reference_rejections=sum('reference_cap' in r['violated_caps'] for r in req),cash_rejections=sum('cash_reserve' in r['violated_caps'] for r in req)))
save('KEYDAY_ALL50',key);csv('KEYDAY_ALL50',key)
# Same cohort definitions: original fine sector securities, both signal dates, includes never-filled tickets.
co=[]
for c in v['CANDIDATES']:
 if c['phase']!='CLOSE' or c['event'] not in ['A','B'] or c['day'] not in ['2024-09-06','2024-09-09'] or ro.loc[c['sid'],'sector_name']!='证券':continue
 a=next((a for a in v['ATTEMPTS'] if a['sid']==c['sid'] and a['signal_day']==c['day']),None);ts=[t for t in orders if a and t['round_id']==a['id']];closed=a is not None and a['final_qty']==0;net=D(a['cashflow'])+D(a['dividend']) if a else None
 co.append(dict(sid=c['sid'],name=ro.loc[c['sid'],'name'],signal_day=c['day'],close_decision=c['decision'],round_id=a['id'] if a else None,status='NOT_ENTERED' if a is None else 'CLOSED' if closed else 'UNFINISHED',final_qty=a['final_qty'] if a else 0,closed_net=net if closed else None,unfinished_marked=D(a['marked_net_pnl']) if a and not closed else None,fees=sum((D(t['fee']) for t in ts),Z)))
cs=dict(signals=len(co),actual_rounds=sum(r['status']!='NOT_ENTERED' for r in co),not_entered=sum(r['status']=='NOT_ENTERED' for r in co),closed=sum(r['status']=='CLOSED' for r in co),unfinished=sum(r['status']=='UNFINISHED' for r in co),closed_net=sum((r['closed_net'] for r in co if r['closed_net'] is not None),Z));save('SEP06_09_COHORT',cs);save('SEP06_09_ALL_SIGNALS',co);csv('SEP06_09_ALL_SIGNALS',co)
cf={r['round_id'] for r in v['INFORMATION_CONFIRMATIONS'] if r['decision']=='INFORMATION_CONFIRMED'};af={r['round_id'] for r in orders if r['side']=='BUY_ADD'};risk=v['ADD_FLOOR_RISK'];summary=dict(result='PASS_SELF_ACCOUNT_RECONSTRUCTION_PENDING_INDEPENDENT_AUDIT',last_day=out[-1]['day'],days=len(out),orders=len(orders),cohort=cs,confirmed_rounds=len(cf),ADD_rounds=len(af),confirmed_never_ADD=len(cf-af),ADD_fills=len(risk),ADD_floor_loss_exceeds_old_net=sum(r['not_profit_covered'] for r in risk),blockers=read(P/'BLOCKERS.json'))
save('ACCOUNT_SUMMARY',summary)
# Same-day comparisons only; M2 stops9/30, quantity-only ablation9/23.
comparisons=[]
for arm,path in [('M2_FACT_EXTENDED',O/'m2_fact_extension_20241008/account_20241008'),('UNCAPPED_SIZE_ONLY',R/'mainline_add_size_ablation_v1/uncapped_once_20240923')]:
 old={x['day']:x for x in read(path/'DAY_LEDGER.json')};oldsec={(x['day'],x['sector51']):x for x in read(path/'SECTOR_DAILY.json')}
 for l in out:
  if l['day'] not in keydays or l['day'] not in old:continue
  for r in [r for r in key if r['day']==l['day']]:
   s=oldsec[(r['day'],r['sector51'])];comparisons.append(dict(day=r['day'],sector51=r['sector51'],comparison_arm=arm,old_NAV=old[r['day']]['NAV'],M3_NAV=l['NAV'],old_sector_weight=s['account_weight_pct'],M3_sector_weight=r['account_weight_pct'],old_sector_net=s['marked_net_pnl'],M3_sector_net=r['marked_net_pnl']))
csv('SAME_DAY_COMPARISON',comparisons)
print(json.dumps(dict(summary=summary,endpoints={r['day']:r for r in out if r['day'] in keydays},focus=[r for r in key if r['sector51'] in ['证券保险','半导体','电池','软件开发','白酒']]),ensure_ascii=False,default=str))
