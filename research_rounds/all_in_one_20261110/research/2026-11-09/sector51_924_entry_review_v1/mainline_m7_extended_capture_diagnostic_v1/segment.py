from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
from statistics import median
import json,csv,hashlib
O=Path(__file__).resolve().parent;R=O.parent/'mainline_m7_cash_batch_design_v6/once_20260630';Z=D(0);A='2024-11-06'
def rd(n):return json.loads((R/(n+'.json')).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def sm(rs,k):return sum((D(r.get(k,0)) for r in rs),Z)
led=rd('DAY_LEDGER');orders=rd('ORDERS');holds=rd('HOLDINGS');events=rd('EQUITY_EVENTS');attempts=rd('ATTEMPTS');sectors=rd('SECTOR_DAILY');caps=rd('CAPITAL_LOTS');E=led[-1]['day'];dateix={x['day']:i for i,x in enumerate(led)}
rounds=json.loads((O/'ACTUAL_ROUNDS.json').read_text());rindex={r['round_id']:r for r in rounds};od=defaultdict(list);hd=defaultdict(list);ed=defaultdict(list)
for o in orders:od[o['round_id']].append(o)
for h in holds:hd[h['round_id']].append(h)
for e in events:
 if e.get('round_id') and e['event']=='ACCRUE_NET80':ed[e['round_id']].append(e)
rows=[]
for a in attempts:
 rid=a['id'];os=od[rid];hs=hd[rid];es=ed[rid];ar=[h for h in hs if h['day']==A];er=[h for h in hs if h['day']==E];ab=[o for o in os if o['day']<=A];ae=[e for e in es if e['day']<=A]
 baseline=sm(ab,'cash_delta')+sm(ae,'receivable_delta')+sm(ar,'market_value');final=D(a['marked_net_pnl']);part=final-baseline
 if a['seed_day']<=A and not ar:
  assert part==0;continue
 seed=next(o for o in os if o['side']=='BUY_SEED');r=rindex[rid];cohort='OLD_HELD_1106' if a['seed_day']<=A else 'NEW_AFTER_1106';adds=[o for o in os if o['side']=='BUY_ADD']
 row=dict(round_id=rid,sid=a['sid'],name=r['name'],sector51=a['sector51'],cohort=cohort,seed_day=a['seed_day'],seed_M=seed.get('M'),seed_role=seed['capital_role'],seed_cash=-D(seed['cash_delta']),seed_account_pct=r['seed_account_pct'],add_count=len(adds),had_ADD_by_anchor=any(o['day']<=A for o in adds),final_qty=a['final_qty'],exit_day=a.get('exit_day'),exit_reason=r['exit_reason'],baseline_marked_net=baseline,final_marked_net=final,segment_pnl=part,segment_fees=sm([o for o in os if o['day']>A],'fee'),ever_M1=r['ever_M1'],trading_intervals_held=r['trading_intervals_held'],peak_close_net=r['peak_close_net'],peak_close_day=r['peak_close_day'],final_liquidation_net=r['final_liquidation_net'])
 rows.append(row)
base=next(x for x in led if x['day']==A);delta=D(led[-1]['NAV'])-D(base['NAV']);assert sm(rows,'segment_pnl')==delta
summary=[]
def group(label,rs):
 closed=[r for r in rs if not r['final_qty']];return dict(group=label,rounds=len(rs),closed=len(closed),open=len(rs)-len(closed),segment_pnl=sm(rs,'segment_pnl'),loss_cost=-sum((min(Z,r['segment_pnl']) for r in rs),Z),gain=sum((max(Z,r['segment_pnl']) for r in rs),Z),segment_fees=sm(rs,'segment_fees'),closed_segment_pnl=sm(closed,'segment_pnl'),open_segment_pnl=sm([r for r in rs if r['final_qty']],'segment_pnl'),closed_losing_count=sum(r['segment_pnl']<0 for r in closed),median_closed_intervals=median([r['trading_intervals_held'] for r in closed]) if closed else None,closed_exit_reasons=dict(Counter(r['exit_reason'] for r in closed)),median_seed_cash=median([r['seed_cash'] for r in rs]) if rs else None)
for cohort in ['OLD_HELD_1106','NEW_AFTER_1106']:
 rs=[r for r in rows if r['cohort']==cohort];summary.append(group(cohort,rs))
 for tag,sel in [('NO_ADD',[r for r in rs if not r['add_count']]),('ADDED',[r for r in rs if r['add_count']]),('NO_ADD_NEVER_M1',[r for r in rs if not r['add_count'] and not r['ever_M1']]),('NO_ADD_EVER_M1',[r for r in rs if not r['add_count'] and r['ever_M1']])]:summary.append(group(cohort+'_'+tag,sel))
 for role in ['INITIAL','EXPANSION']:summary.append(group(cohort+'_SEED_ROLE_'+role,[r for r in rs if r['seed_role']==role]))
oldrs=[r for r in rows if r['cohort']=='OLD_HELD_1106'];summary.extend(group('OLD_BY_ANCHOR_'+str(added),[r for r in oldrs if r['had_ADD_by_anchor']==added]) for added in [False,True])
sector=[]
for sec in sorted({r['sector51'] for r in rows}):
 rs=[r for r in rows if r['sector51']==sec];r=dict(sector51=sec,segment_pnl=sm(rs,'segment_pnl'))
 for c in ['OLD_HELD_1106','NEW_AFTER_1106']:
  for add in [False,True]:r[c+('_ADDED' if add else '_NO_ADD')]=sm([x for x in rs if x['cohort']==c and bool(x['add_count'])==add],'segment_pnl')
 sector.append(r)
sector.sort(key=lambda r:r['segment_pnl'])
repeats=[]
new=[r for r in rows if r['cohort']=='NEW_AFTER_1106']
for sid in sorted({r['sid'] for r in new}):
 rs=[r for r in new if r['sid']==sid]
 if len(rs)<2:continue
 repeats.append(dict(sid=sid,name=rs[0]['name'],sector51=rs[0]['sector51'],rounds=len(rs),no_add_rounds=sum(not r['add_count'] for r in rs),net=sm(rs,'segment_pnl'),fees=sm(rs,'segment_fees'),seed_days=[r['seed_day'] for r in rs],round_paths=[dict(seed_day=r['seed_day'],exit_day=r['exit_day'],net=r['segment_pnl'],add_count=r['add_count'],exit_reason=r['exit_reason']) for r in rs]))
repeats.sort(key=lambda r:r['net'])
months=[]
for month in sorted({x['day'][:7] for x in led if x['day']>A}):
 dates=[x for x in led if x['day'][:7]==month and x['day']>A];first=dates[0]['day'];last=dates[-1]['day'];prior=led[dateix[first]-1];end=dates[-1]
 months.append(dict(month=month,start_anchor=prior['day'],end=last,start_nav=prior['NAV'],end_nav=end['NAV'],pnl=D(end['NAV'])-D(prior['NAV']),return_pct=(D(end['NAV'])/D(prior['NAV'])-1)*100,seed_orders=sum(o['side']=='BUY_SEED' and first<=o['day']<=last for o in orders),add_orders=sum(o['side']=='BUY_ADD' and first<=o['day']<=last for o in orders),fees=D(end['fees_paid'])-D(prior['fees_paid'])))
snapshot=[]
for day in [A,'2024-11-14','2024-11-15','2024-11-29','2024-12-13','2024-12-31','2025-01-13','2025-01-17',E]:
 ss=[r for r in sectors if r['day']==day];ss.sort(key=lambda r:D(r['market_value']),reverse=True)
 snapshot.append(dict(day=day,NAV=next(x['NAV'] for x in led if x['day']==day),top_holdings=[{k:s[k] for k in ['sector51','M','stocks','market_value','account_weight_pct']} for s in ss[:8]],all_M1_sectors=[s['sector51'] for s in ss if s['M']==1]))
result=dict(anchor=A,end=E,delta=delta,return_pct=(D(led[-1]['NAV'])/D(base['NAV'])-1)*100,groups=summary,monthly=months,repeated_stock_count=len(repeats),repeat_rounds=sum(r['rounds'] for r in repeats),repeat_net=sm(repeats,'net'),top_repeats=repeats[:15],snapshots=snapshot,notes=['OLD_HELD baseline mark is subtracted so profit made before 11/6 is not counted in this segment.','No ADD and ever M1 are realized path labels, never used as entry predictors. EXPANSION buy role includes MATURE SEED, not only BUY_ADD.','Pnl includes actual fees; segment fees are descriptive and must not be subtracted a second time.','Open cohorts include positions too recent to conclude success or failure. All end at certified 1/20.'])
for n,x in [('SEGMENT_1106',result),('SEGMENT_1106_ROUNDS',rows),('SEGMENT_1106_SECTORS',sector),('SEGMENT_1106_REPEATED_STOCKS',repeats)]:save(n,x)
print(json.dumps(result,ensure_ascii=False,default=str))
