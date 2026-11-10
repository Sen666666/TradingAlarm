"""Post-run descriptive evaluation only. Never imported by strategy."""
from pathlib import Path
from decimal import Decimal as D
import json, pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent;Z=D(0);INIT=D(1200000)
ARMS={'M3':'mainline_candidate_v3_core_reference','M4_original':'mainline_candidate_v4_event_representatives','M4_fixed':'mainline_candidate_v4_known_sector_fix_v2','M5':'mainline_candidate_v5_expansion_competition','M6':'mainline_candidate_v6_mature_round_cap'}
def read(p):return json.loads(p.read_text())
def save(n,v):
 (O/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str))
 if isinstance(v,list):pd.DataFrame(v).to_csv(O/(n+'.csv'),index=False)
summary=[];allsec=[];allcost=[];allfund=[];focus=[];arms={};roles=[]
for arm,name in ARMS.items():
 p=ROOT/name/'once_20241008';data={n:read(p/(n+'.json')) for n in ['DAY_LEDGER','ORDERS','HOLDINGS','CAPITAL_LOTS','ATTEMPTS','SECTOR_DAILY','EQUITY_EVENTS','FUNDING_REQUESTS','REFERENCE_DAILY','ADD_FLOOR_RISK','SEED_FLOOR_RISK','TRANSFERS','BLOCKERS'] if (p/(n+'.json')).exists()};arms[arm]=data;ledger=data['DAY_LEDGER'];orders=data['ORDERS'];cash=INIT;recv=Z;fees=Z;peak=INIT;maxdd=Z;turn=Z;prev=INIT;slip=Z;quant={};sold_lots={};rebuys=[]
 for l in ledger:
  ds=l['day'];ts=[t for t in orders if t['day']==ds]
  for t in ts:
   cash+=D(t['cash_delta']);fees+=D(t['fee']);sgn=1 if t['side'].startswith('BUY') else -1;quant[t['sid']]=quant.get(t['sid'],0)+sgn*t['qty'];slip+=abs(D(t['price'])-D(t['price'])/(D('1.0005') if sgn==1 else D('.9995')))*t['qty'];turn+=D(t['notional'])/prev
  for e in data['EQUITY_EVENTS']:
   if e['day']==ds:cash+=D(e.get('cash_delta',0));recv+=D(e.get('receivable_delta',0))
  hs=[h for h in data['HOLDINGS'] if h['day']==ds];hquant={}
  for h in hs:hquant[h['sid']]=hquant.get(h['sid'],0)+h['qty']
  assert hquant=={s:q for s,q in quant.items() if q};nav=cash+recv+sum((D(h['market_value']) for h in hs),Z);assert nav==D(l['NAV']) and cash==D(l['cash']) and recv==D(l['receivable']) and fees==D(l['fees_paid']);assert sum((D(s['marked_net_pnl']) for s in data['SECTOR_DAILY'] if s['day']==ds),Z)==nav-INIT;peak=max(peak,nav);maxdd=min(maxdd,nav/peak-1);prev=nav
  if ds in ['2024-09-23','2024-09-24','2024-09-27','2024-09-30','2024-10-08']:
   lr=[x for x in data['CAPITAL_LOTS'] if x['day']==ds];base=next(D(x['NAV']) for x in ledger if x['day']=='2024-09-23')
   summary.append(dict(arm=arm,**l,return_pct=100*(nav/INIT-1),since_0923_return_pct=100*(nav/base-1),running_max_drawdown_pct=100*maxdd,slippage_proxy=slip,total_cost=fees+slip,two_way_turnover=turn,core_value=sum((D(x['core_value']) for x in lr),Z),mobile_value=sum((D(x['mobile_value']) for x in lr),Z),fixed_value=sum((D(x['frozen_value']) for x in lr),Z)))
   refs={r['sector51']:r for r in data['REFERENCE_DAILY'] if r['day']==ds}
   for ss in [x for x in data['SECTOR_DAILY'] if x['day']==ds]:
    sec=ss['sector51'];r=refs[sec];tr=[t for t in orders if t['sector51']==sec and t['day']<=ds];old=next(x for x in data['SECTOR_DAILY'] if x['day']=='2024-09-23' and x['sector51']==sec)
    rr=dict(ss,arm=arm,since_0923_net_pnl=D(ss['marked_net_pnl'])-D(old['marked_net_pnl']),T=r['T'],buy_envelope=r['buy_envelope'],fixed=r['fixed'],core=r['core'],reference_E=r['E'],expansion_W=r.get('W'),positive_E_increment=r.get('positive_E_increment'),first_seed=min((t['day'] for t in tr if t['side']=='BUY_SEED'),default=None),first_add=min((t['day'] for t in tr if t['side']=='BUY_ADD'),default=None),seed_fills=sum(t['side']=='BUY_SEED' for t in tr),add_fills=sum(t['side']=='BUY_ADD' for t in tr));allsec.append(rr)
    if sec in ['证券保险','半导体','软件与IT服务','动力电池','白酒']:focus.append(rr)
   for role in ['INITIAL','EXPANSION']:
    rows=[r for r in lr if r.get('capital_role')==role];roles.append(dict(arm=arm,day=ds,role=role,value=sum((D(r['market_value']) for r in rows),Z),core=sum((D(r['core_value']) for r in rows),Z),mobile=sum((D(r['mobile_value']) for r in rows),Z)))
 for period in ['through_0923','through_1008']:
  end='2024-09-23' if period=='through_0923' else '2024-10-08';closed=[a for a in data['ATTEMPTS'] if a['final_qty']==0 and a.get('exit_day','9999')<=end];trial=[a for a in closed if a['add_count']==0];losers=[a for a in trial if D(a['marked_net_pnl'])<0]
  for group,aa in [('all_closed',closed),('closed_no_ADD',trial),('losing_closed_no_ADD',losers)]:
   ids={a['id'] for a in aa};tt=[t for t in orders if t['round_id'] in ids];allcost.append(dict(arm=arm,period=period,group=group,rounds=len(aa),net=sum((D(a['marked_net_pnl']) for a in aa),Z),fees=sum((D(t['fee']) for t in tt),Z),worst=min((D(a['marked_net_pnl']) for a in aa),default=None)))
 donors=[t for t in orders if t.get('transfer_rank')];adds=data['ADD_FLOOR_RISK'];allfund.append(dict(arm=arm,donor_sales=len(donors),net_released=sum((D(t['cash_delta']) for t in donors),Z),donor_fees=sum((D(t['fee']) for t in donors),Z),ADD_orders=len(adds),ADD_risk_exceeds_existing_profit=sum(x['not_profit_covered'] for x in adds),ADD_max_known_floor_loss=max((D(x['incremental_known_floor_loss']) for x in adds),default=Z),not_stop_fill_guarantee=True,blockers=data['BLOCKERS']))
 # Original CP and profit gates at actual OPEN, including zero capital allocations.
 save(arm+'_PURPLE_GATES',[r for r in data['FUNDING_REQUESTS'] if r['sid']=='002049.SZ'])
 save(arm+'_PURPLE_ORDERS',[r for r in orders if r['sid']=='002049.SZ'])
save('ACCOUNT_COMPARISON',summary);save('ALL50_CAPITAL_COMPARISON',allsec);save('FIVE_FOCUS_COMPARISON',focus);save('TRIAL_COST_COMPARISON',allcost);save('FUNDING_AND_PRINCIPAL_RISK',allfund);save('CAPITAL_ROLES_COMPARISON',roles)
ev=pd.read_csv(ROOT/'sector_strength_evidence_v1/extension_1022/ALL50_DAILY_EVIDENCE.csv');cols=['sector51','m3_state','m3_n','m3_N','return5_K','return5_median','rs5_median_pp'];market=ev[ev.day=='2024-09-30'][cols].sort_values('return5_median',ascending=False);market['interpretation']='Descriptive current-universe median adjusted 2024-09-23 to 09-30 return; not investable index, not selection input';save('ALL50_0924_RALLY_DESCRIPTIVE',market.to_dict('records'))
seals={str(p.relative_to(ROOT)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for a in ARMS.values() for p in (ROOT/a/'once_20241008').glob('*.json')};save('COMPARISON_QA',dict(result='PASS_ALL_ARMS_DAILY_ACCOUNT_RECONSTRUCTION',arms=list(ARMS),source_hashes=seals))
print(json.dumps(dict(endpoints=[r for r in summary if r['day']=='2024-10-08'],cost=[r for r in allcost if r['period']=='through_1008'],funding=allfund),ensure_ascii=False,default=str))
