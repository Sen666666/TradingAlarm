"""Frozen M7 descriptive economic analysis. Reads completed artifacts only; never imports a strategy."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
from statistics import median
import json, csv, hashlib
ROOT=Path(__file__).resolve().parent.parent; OUT=Path(__file__).resolve().parent
RUN=ROOT/'mainline_m7_cash_batch_design_v6'; P=RUN/'once_20260630'
Z=D(0); INIT=D(1200000); ANCHOR='2024-10-31'; PV='光伏风电设备'
CASES=['000158.SZ','002261.SZ','300085.SZ','002049.SZ','002865.SZ']
hashes={}
def read(p):
 hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest(); return json.loads(p.read_text())
def save(n,x):
 (OUT/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (OUT/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def sd(rs,k):return sum((D(r.get(k,0)) for r in rs),Z)
assert (RUN/'RUN_STATUS.json').exists(), 'Refuse incomplete run'
status=read(RUN/'RUN_STATUS.json')
names=['DAY_LEDGER','SECTOR_DAILY','HOLDINGS','CAPITAL_LOTS','ORDERS','ATTEMPTS','TRANSFERS','REFERENCE_DAILY','ADD_FLOOR_RISK','SEED_FLOOR_RISK','EQUITY_EVENTS','BLOCKERS','UNCERTIFIED_DAY']
data={n:read(P/(n+'.json')) for n in names}; led=data['DAY_LEDGER']; END=led[-1]['day']; assert END==status['last']['day']
assert all(r['day']<=END for n in ['ORDERS','HOLDINGS','CAPITAL_LOTS','SECTOR_DAILY'] for r in data[n])
base=next(r for r in led if r['day']==ANCHOR); dates=[r['day'] for r in led]; ix={d:i for i,d in enumerate(dates)}
byday={r['day']:r for r in led}; sectors={(r['day'],r['sector51']):r for r in data['SECTOR_DAILY']}
hg=defaultdict(list); cg=defaultdict(list); og=defaultdict(list); od=defaultdict(list); rg=defaultdict(list)
for r in data['HOLDINGS']:hg[r['day']].append(r)
for r in data['CAPITAL_LOTS']:cg[r['day']].append(r);rg[r['round_id']].append(r)
for r in data['ORDERS']:og[r['round_id']].append(r);od[r['day']].append(r)
stocknames={r['sid']:r['name'] for r in data['ORDERS']}; ag={r['id']:r for r in data['ATTEMPTS']}
# Daily exposure and peak-to-trough account paths.
daily=[];peak=INIT;peakday=dates[0];drawdowns=[];previous=INIT
for r in led:
 day=r['day'];nav=D(r['NAV'])
 if nav>peak:peak=nav;peakday=day
 dd=(peak-nav)/peak*100
 row=dict(r,daily_pnl=nav-previous,daily_return_pct=(nav/previous-1)*100,running_peak=peak,running_peak_day=peakday,close_drawdown_amount=peak-nav,close_drawdown_pct=dd)
 for m,label in [(1,'M1'),(0,'M0'),(-1,'UNKNOWN')]:
  ss=[s for (d,k),s in sectors.items() if d==day and s['M']==m]
  row[label+'_sector_count']=len(ss); row[label+'_value']=sd(ss,'market_value');row[label+'_weight_pct']=row[label+'_value']/nav*100
 for role in ['INITIAL','EXPANSION']:
  lots=[c for c in cg[day] if c['capital_role']==role];row[role+'_value']=sd(lots,'market_value');row[role+'_weight_pct']=row[role+'_value']/nav*100
  for m,label in [(1,'M1'),(0,'M0'),(-1,'UNKNOWN')]:row[role+'_'+label+'_value']=sd([c for c in lots if c['M']==m],'market_value')
 row['close_to_known_floor_raw_pressure']=sum((D(h['qty'])*max(Z,D(h['raw_mark'])-D(h['protection_signal'])/D(h['factor'])) for h in hg[day]),Z)
 row['close_to_known_floor_raw_pressure_pct']=row['close_to_known_floor_raw_pressure']/nav*100
 row['seed_buy_cash']=-sd([o for o in od[day] if o['side']=='BUY_SEED'],'cash_delta');row['add_buy_cash']=-sd([o for o in od[day] if o['side']=='BUY_ADD'],'cash_delta');row['sell_cash']=sd([o for o in od[day] if o['side'].startswith('SELL')],'cash_delta')
 daily.append(row);previous=nav
worst=max(daily,key=lambda r:r['close_drawdown_pct']); recovery=next((r for r in daily if r['day']>worst['day'] and D(r['NAV'])>=D(worst['running_peak'])),None)
# Sector contribution is actual marked PnL difference, not a sum of market values.
contrib=[]; sector_daily=[]
for sec in sorted({r['sector51'] for r in data['SECTOR_DAILY']}):
 hist=[sectors[d,sec] for d in dates];a=sectors[ANCHOR,sec];b=sectors[END,sec];rs=[o for o in data['ORDERS'] if o['sector51']==sec and o['day']>ANCHOR]
 c=dict(sector51=sec,anchor_pnl=a['marked_net_pnl'],end_pnl=b['marked_net_pnl'],extension_pnl=D(b['marked_net_pnl'])-D(a['marked_net_pnl']),anchor_weight_pct=a['account_weight_pct'],end_weight_pct=b['account_weight_pct'],anchor_M=a['M'],end_M=b['M'],end_stocks=b['stocks'],extension_seed_cash=-sd([o for o in rs if o['side']=='BUY_SEED'],'cash_delta'),extension_add_cash=-sd([o for o in rs if o['side']=='BUY_ADD'],'cash_delta'),extension_sell_cash=sd([o for o in rs if o['side'].startswith('SELL')],'cash_delta'),extension_financing_sell_cash=sd([o for o in rs if o.get('transfer_rank')],'cash_delta'))
 for role in ['INITIAL','EXPANSION']:c['end_'+role+'_value']=sd([x for x in cg[END] if x['sector51']==sec and x['capital_role']==role],'market_value')
 for m,label in [(1,'M1'),(0,'M0'),(-1,'UNKNOWN')]:
  rows=[r for r in hist if r['day']>ANCHOR and r['M']==m];c[label+'_extension_days']=len(rows)
  c['daily_pnl_prior_'+label]=sum((D(hist[i]['marked_net_pnl'])-D(hist[i-1]['marked_net_pnl']) for i in range(1,len(hist)) if hist[i]['day']>ANCHOR and hist[i-1]['M']==m),Z)
 contrib.append(c)
 prevp=Z
 for r in hist:
  if r['day']>=ANCHOR:
   lots=[x for x in cg[r['day']] if x['sector51']==sec];ref=next(x for x in data['REFERENCE_DAILY'] if x['day']==r['day'] and x['sector51']==sec)
   sector_daily.append(dict(r,daily_net_contribution=D(r['marked_net_pnl'])-prevp,INITIAL_value=sd([x for x in lots if x['capital_role']=='INITIAL'],'market_value'),EXPANSION_value=sd([x for x in lots if x['capital_role']=='EXPANSION'],'market_value'),mobile_value=sd(lots,'mobile_value'),frozen_value=sd(lots,'frozen_value'),budget_target=ref['T'],new_buy_envelope=ref['buy_envelope'],legal_demand=ref['D'],expansion_budget=ref['X'],market_minus_target=D(r['market_value'])-D(ref['T'])))
  prevp=D(r['marked_net_pnl'])
contrib.sort(key=lambda r:r['extension_pnl'],reverse=True)
assert sum((r['extension_pnl'] for r in contrib),Z)==D(led[-1]['NAV'])-D(base['NAV'])
# Every actual round, no ex post mainline definitions.
rounds=[]
for rid,a in ag.items():
 os=og[rid];buy=[o for o in os if o['side'].startswith('BUY')];seed=next(o for o in os if o['side']=='BUY_SEED');rs=rg[rid]
 unique={r['day']:r for r in rs};rds=[unique[d] for d in sorted(unique)]
 finalnet=D(a['marked_net_pnl']) if a['final_qty']==0 else D(rds[-1]['round_net'])
 peakr=max(rds,key=lambda r:D(r['round_net'])) if rds else None
 row=dict(round_id=rid,sid=a['sid'],name=stocknames[a['sid']],sector51=a['sector51'],signal_day=a['signal_day'],seed_day=a['seed_day'],seed_M=seed.get('M'),seed_cash=-D(seed['cash_delta']),nav0=a['nav0'],seed_account_pct=-D(seed['cash_delta'])/D(a['nav0'])*100,add_count=a['add_count'],add_cash=-sd([o for o in os if o['side']=='BUY_ADD'],'cash_delta'),exit_day=a.get('exit_day'),exit_reason=(a.get('exit') or (next((o['reason'] for o in reversed(os) if o['side'].startswith('SELL')),None) if not a['final_qty'] else None)),final_qty=a['final_qty'],final_marked_net=a['marked_net_pnl'],final_liquidation_net=finalnet,fees=a['fees'],ever_M1=any(r['M']==1 for r in rs),ever_confirmed=any(r['confirmed_history'] for r in rs),peak_close_net=D(peakr['round_net']) if peakr else None,peak_close_day=peakr['day'] if peakr else None,peak_qty=sum(r['qty'] for r in rs if peakr and r['day']==peakr['day']),peak_to_final_giveback=D(peakr['round_net'])-finalnet if peakr else None,trading_intervals_held=ix[a.get('exit_day') or END]-ix[a['seed_day']],max_position_value=max((sd([r for r in rs if r['day']==d],'market_value') for d in unique),default=Z))
 rounds.append(row)
def cohort(label,rs):
 gains=sum((max(Z,D(r['final_marked_net'])) for r in rs),Z);loss=-sum((min(Z,D(r['final_marked_net'])) for r in rs),Z);dur=sorted(r['trading_intervals_held'] for r in rs)
 return dict(cohort=label,count=len(rs),net=sd(rs,'final_marked_net'),gross_winning_pnl=gains,gross_losing_cost=loss,fees=sd(rs,'fees'),seed_cash=sd(rs,'seed_cash'),median_seed_cash=median([r['seed_cash'] for r in rs]) if rs else 0,median_intervals_held=median(dur) if dur else 0,p90_intervals_held=dur[min(len(dur)-1,int(len(dur)*.9))] if dur else 0,max_intervals_held=max(dur,default=0),loss_count=sum(D(r['final_marked_net'])<0 for r in rs),exit_reasons=dict(Counter(r['exit_reason'] for r in rs)))
cohorts=[]
for prefix,rs in [('ALL_CLOSED',[r for r in rounds if not r['final_qty']]),('EXTENSION_BORN_CLOSED',[r for r in rounds if not r['final_qty'] and r['seed_day']>ANCHOR]),('EXTENSION_EXITED',[r for r in rounds if not r['final_qty'] and r['exit_day']>ANCHOR])]:
 cohorts.append(cohort(prefix,rs));cohorts.append(cohort(prefix+'_NO_ADD',[r for r in rs if r['add_count']==0]));cohorts.append(cohort(prefix+'_NO_ADD_NEVER_M1',[r for r in rs if r['add_count']==0 and not r['ever_M1']]));cohorts.append(cohort(prefix+'_ADDED',[r for r in rs if r['add_count']>0]))
# PV funds release and simultaneous recipients: pooled cash, no invented exact donor/receiver pairing.
funding=[]
for day in dates:
 if day<=ANCHOR:continue
 os=od[day];pv=[o for o in os if o['sector51']==PV];pvsell=[o for o in pv if o['side'].startswith('SELL')]
 if not pvsell:continue
 allbuy=[o for o in os if o['side'].startswith('BUY')];buysecs=[]
 for sec in sorted({o['sector51'] for o in allbuy}):
  bs=[o for o in allbuy if o['sector51']==sec];buysecs.append(dict(sector51=sec,buy_cash=-sd(bs,'cash_delta'),add_cash=-sd([o for o in bs if o['side']=='BUY_ADD'],'cash_delta')))
 funding.append(dict(day=day,pv_sell_cash=sd(pvsell,'cash_delta'),pv_financing_sell_cash=sd([o for o in pvsell if o.get('transfer_rank')],'cash_delta'),pv_sell_reasons=dict(Counter(o['reason'] for o in pvsell)),all_sells=sd([o for o in os if o['side'].startswith('SELL')],'cash_delta'),all_buys=-sd(allbuy,'cash_delta'),cash_start=byday[dates[ix[day]-1]]['cash'],cash_end=byday[day]['cash'],simultaneous_buy_sectors=sorted(buysecs,key=lambda r:r['buy_cash'],reverse=True)))
# Executed sales: raw opening gap on sold shares. Exclude action days from comparable totals.
lotprev={(h['day'],h['lot_id']):h for h in data['HOLDINGS']};evpairs={(e['day'],e['sid']) for e in data['EQUITY_EVENTS'] if e['event'] in ['FACTOR_BRIDGE','ACCRUE_NET80']}
gaps=[]
for o in data['ORDERS']:
 if not o['side'].startswith('SELL') or ix[o['day']]==0:continue
 prior=dates[ix[o['day']]-1];qmap=o.get('lot_quantities') or {l:lotprev[(prior,l)]['qty'] for l in o.get('lots',[]) if (prior,l) in lotprev};hs=[(lotprev.get((prior,l)),q) for l,q in qmap.items()];hs=[(h,q) for h,q in hs if h]
 if not hs or sum(q for h,q in hs)!=o['qty']:continue
 prevclose=D(hs[0][0]['raw_mark']);rawopen=D(o['price'])/D('.9995');comparable=(o['day'],o['sid']) not in evpairs
 gaps.append(dict(day=o['day'],prior_close_day=prior,sid=o['sid'],name=o['name'],sector51=o['sector51'],round_id=o['round_id'],side=o['side'],reason=o['reason'],qty=o['qty'],previous_raw_close=prevclose,raw_open=rawopen,actual_fill=o['price'],raw_open_gap_pct=(rawopen/prevclose-1)*100,raw_open_gap_on_sold_shares=(rawopen-prevclose)*o['qty'],fill_minus_prior_close_on_sold_shares=(D(o['price'])-prevclose)*o['qty'],fee=o['fee'],corporate_action_on_day=not comparable,below_prior_protection_raw_loss=sum((max(Z,D(h['protection_signal'])/D(h['factor'])-rawopen)*q for h,q in hs),Z),prior_lot_protections=[dict(lot_id=h['lot_id'],qty=q,protection_raw=D(h['protection_signal'])/D(h['factor']),locked_exit=h['locked_exit']) for h,q in hs]))
# Actual stock paths for fixed original five winners, no selection by new results.
focus=[]
for sid in CASES:
 os=[o for o in data['ORDERS'] if o['sid']==sid];rr=[r for r in rounds if r['sid']==sid];hs=[h for h in data['HOLDINGS'] if h['sid']==sid]
 ah=[h for h in hs if h['day']==ANCHOR];eh=[h for h in hs if h['day']==END]
 flow=sd([o for o in os if o['day']>ANCHOR],'cash_delta');equity=sum((D(e.get('receivable_delta',0)) for e in data['EQUITY_EVENTS'] if e['sid']==sid and e['day']>ANCHOR and e['event']=='ACCRUE_NET80'),Z)
 focus.append(dict(sid=sid,name=stocknames[sid],anchor_qty=sum(h['qty'] for h in ah),end_qty=sum(h['qty'] for h in eh),anchor_value=sd(ah,'market_value'),end_value=sd(eh,'market_value'),extension_actual_marked_pnl=flow+equity+sd(eh,'market_value')-sd(ah,'market_value'),all_rounds=rr,extension_orders=[o for o in os if o['day']>ANCHOR]))
# Top actual contributors by stock in extension, and complete PV stock chain.
stockflows=[]
for sid in stocknames:
 os=[o for o in data['ORDERS'] if o['sid']==sid];a=[h for h in hg[ANCHOR] if h['sid']==sid];b=[h for h in hg[END] if h['sid']==sid];new=[o for o in os if o['day']>ANCHOR]
 div=sum((D(e.get('receivable_delta',0)) for e in data['EQUITY_EVENTS'] if e['sid']==sid and e['day']>ANCHOR and e['event']=='ACCRUE_NET80'),Z)
 stockflows.append(dict(sid=sid,name=stocknames[sid],sector51=os[0]['sector51'],anchor_qty=sum(h['qty'] for h in a),end_qty=sum(h['qty'] for h in b),anchor_value=sd(a,'market_value'),end_value=sd(b,'market_value'),extension_pnl=sd(new,'cash_delta')+div+sd(b,'market_value')-sd(a,'market_value'),extension_buy_cash=-sd([o for o in new if o['side'].startswith('BUY')],'cash_delta'),extension_sell_cash=sd([o for o in new if o['side'].startswith('SELL')],'cash_delta'),extension_financing_sell_cash=sd([o for o in new if o.get('transfer_rank')],'cash_delta')))
stockflows.sort(key=lambda r:r['extension_pnl'],reverse=True)
assert sum((r['extension_pnl'] for r in stockflows),Z)==D(led[-1]['NAV'])-D(base['NAV'])
comparable=[g for g in gaps if not g['corporate_action_on_day']]; extg=[g for g in comparable if g['day']>ANCHOR]
summary=dict(status=status,certified_through=END,initial=INIT,final_nav=led[-1]['NAV'],return_pct=(D(led[-1]['NAV'])/INIT-1)*100,anchor=ANCHOR,anchor_nav=base['NAV'],extension_pnl=D(led[-1]['NAV'])-D(base['NAV']),extension_return_pct=(D(led[-1]['NAV'])/D(base['NAV'])-1)*100,max_close_drawdown=dict(peak_day=worst['running_peak_day'],peak_nav=worst['running_peak'],trough_day=worst['day'],trough_nav=worst['NAV'],amount=worst['close_drawdown_amount'],pct=worst['close_drawdown_pct'],recovery_day=recovery['day'] if recovery else None),last_exposure=daily[-1],max_floor_pressure=max(daily,key=lambda r:r['close_to_known_floor_raw_pressure_pct']),max_M0_exposure=max(daily,key=lambda r:r['M0_weight_pct']),cohorts=cohorts,extension_gap_summary=dict(comparable_sale_orders=len(extg),negative_open_gap_on_executed_shares=-sum((min(Z,r['raw_open_gap_on_sold_shares']) for r in extg),Z),positive_open_gap_on_executed_shares=sum((max(Z,r['raw_open_gap_on_sold_shares']) for r in extg),Z),excluded_action_day_orders=sum(g['day']>ANCHOR and g['corporate_action_on_day'] for g in gaps)),caveats=['Frozen retrospective, non-PIT universe/classification and selected parameters; not live trading or native out of sample.','Directory planned horizon is not certified last day.','M=-1 is unknown, not failure. OPEN orders depend on completed prior CLOSE.','INITIAL and EXPANSION are actual capital roles; reference target T is funding constraint, not mandatory rebalance.','No-add closed rounds are observational trial proxy, not ex post proof every market was ordinary. Extension-exited PnL spans entire round; extension-born cohort is separate.','Close-to-floor raw pressure excludes fees, slippage, gaps, nontradability and future changes; not execution or maximum loss. Principal risk is not intrinsically an error.','Gap PnL covers only sold shares, not all overnight account risk. Actions excluded; raw gap itself is not a causal strategy comparison.','PV sale proceeds enter pooled cash; simultaneous buys do not identify exclusive donor/receiver mapping.','Round peaks occur on different dates and cannot be summed as attainable NAV.'])
for n,rows in [('DAILY_ACCOUNT',daily),('SECTOR_CONTRIBUTIONS',contrib),('SECTOR_DAILY_PATH',sector_daily),('ACTUAL_ROUNDS',rounds),('TRIAL_COHORTS',cohorts),('PV_FUND_RELEASE_DAYS',funding),('EXECUTED_SALE_GAPS',gaps),('FIXED_FIVE_WINNERS',focus),('STOCK_CONTRIBUTIONS',stockflows),('PV_STOCK_CONTRIBUTIONS',[r for r in stockflows if r['sector51']==PV]),('SUMMARY',summary)]:save(n,rows)
save('SOURCE_HASHES',hashes)
print(json.dumps({'summary':summary,'top_sector_contributions':contrib[:12],'bottom_sector_contributions':contrib[-8:],'focus':[dict(sid=r['sid'],extension_actual_marked_pnl=r['extension_actual_marked_pnl'],anchor_qty=r['anchor_qty'],end_qty=r['end_qty']) for r in focus]},ensure_ascii=False,default=str))
