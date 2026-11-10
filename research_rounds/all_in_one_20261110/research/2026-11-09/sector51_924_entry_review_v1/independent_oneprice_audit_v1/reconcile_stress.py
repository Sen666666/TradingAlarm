"""Independent ledger and capital audit. Reads executed outputs; never runs strategy."""
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_CEILING
from collections import defaultdict,Counter
import json,sys,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;run=Path(sys.argv[1]);OUT=O/run.parent.name;OUT.mkdir(exist_ok=False);read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
rules=read(B/'inputs-v2/market-rules.json');manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
ro=pd.read_csv(P/'joint51_candidate_v1/CLASSIFICATION_ALL1709.csv');mapping=ro[ro.eligible].set_index('symbol').sector51.to_dict();sectors=sorted(set(mapping.values()))
orders=read(run/'ORDERS.json');ledger=read(run/'DAY_LEDGER.json');holdings=read(run/'HOLDINGS.json');equity=read(run/'EQUITY_EVENTS.json');candidates=read(run/'CANDIDATES.json');sector_daily=read(run/'SECTOR_DAILY.json');attempts={x['id']:x for x in read(run/'ATTEMPTS.json')};cpcreated={x['cp_id']:x for x in read(run/'CP_EVENTS.json') if x['event']=='CREATED_AFTER_SEED'}
facts=Path(read(run.parent/'FREEZE.json')['source_facts'])
reservations=read(run/'OPEN_RESERVATIONS.json');nofills=read(run/'NO_FILLS.json');intents=read(run/'OPEN_INTENTS.json')
rd={};nd={};idc={};ido={}
for x in reservations:rd.setdefault(x['day'],[]).append(x)
for x in nofills:nd.setdefault(x['day'],[]).append(x)
for x in intents:(idc if x['row_type']=='ALLOCATION' else ido).setdefault(x['day'],[]).append(x)
events=read(E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+read(P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')+read(facts/'ADDITIONAL_REVIEWED_EVENTS.json');events=[e for e in events if e['sid'] in mapping and ledger[0]['day']<=e['ex_date']<=ledger[-1]['day']]
assert len({(e['sid'],e['ex_date']) for e in events})==len(events)
used={r['sid'] for r in orders}|{r['sid'] for r in candidates if r['phase']=='OPEN'};raw={s:pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'))) for s in used}
checks=Counter();errors=[];lots={};cash=D(1200000);recv=D(0);fees=D(0);claims={};snaps={};cf=defaultdict(lambda:D(0));div=defaultdict(lambda:D(0));prev_state={};daily=[];capital_stats=Counter();min_cash_pct=None
byday=lambda rows: {d:[x for x in rows if x['day']==d] for d in {x['day'] for x in rows}}
od=byday(orders);hd=byday(holdings);sd=byday(sector_daily);cd=byday(candidates);ed=byday(equity);ld={x['day']:x for x in ledger};seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
def equal(label,x,y,ctx):
 checks[label]+=1
 if x!=y:errors.append(dict(check=label,context=ctx,actual=str(x),expected=str(y)))
def version(vs,dt):
 z=[v for v in vs if v['from']<=dt and (v.get('to') is None or dt<v['to'])];assert len(z)==1;return z[0]
def fee(s,dt,q,p,side):
 if not q:return D(0)
 venue=version(rules['venue_versions'][s],dt)['venue'];comps=version(rules['fee_versions'][venue],dt)['schedule']['components'];total=D(0)
 for c in comps:
  if c.get('side','both') not in ('both',side):continue
  basis=c.get('amount_basis','notional');base=q*p if basis=='notional' else D(q) if basis=='shares' else q*D(rules['security_metadata'][s]['par_value'])
  v=max(D(c.get('minimum_local','0')),base*D(c['rate']))
  if c.get('maximum_local') is not None:v=min(v,D(c['maximum_local']))
  if c.get('rounding_unit') is not None:
   unit=D(c['rounding_unit']);v=(v/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
  total+=v
 return total
def size(s,dt,p,budget,cap):
 qr=version(rules['quantity_versions'][s],dt)['rule'];q=min(int(max(D(0),budget)/p),int(cap));q=0 if q<qr['buy_minimum'] else qr['buy_minimum']+((q-qr['buy_minimum'])//qr['buy_step'])*qr['buy_step']
 while q and q*p+fee(s,dt,q,p,'buy')>budget:q=0 if q-qr['buy_step']<qr['buy_minimum'] else q-qr['buy_step']
 return q
def price(s,t,f):return D(str(raw[s].at[pd.Timestamp(t),f]))
def inv(s=None,rid=None):return sum(x['q'] for x in lots.values() if (s is None or x['sid']==s) and (rid is None or x['rid']==rid))
for row in ledger:
 dt=row['day'];today=od.get(dt,[]);oc=[x for x in cd.get(dt,[]) if x['phase']=='OPEN'];before_cash=cash;expected_equity=[]
 for ev in events:
  if ev['ex_date']==dt:
   q,rid=snaps.get((ev['sid'],ev['record_date']),(0,None))
   if q:
    amount=D(q)*D(ev['d_cash'])*D('.8');recv+=amount;div[rid]+=amount;claims[(ev['sid'],ev['ex_date'])]=(amount,rid)
    expected_equity.append(('ACCRUE_NET80',ev['sid'],rid,str(amount),str(D(0))))
 equal('exits_before_any_buy', [x['side'].startswith('BUY') for x in today],sorted(x['side'].startswith('BUY') for x in today),dt)

 # Rebuild the ordinary full-batch intent from the actual previous inventory and
 # hypothetical proceeds of its intended exits. No raw H/L/C gate is used here.
 original={(x['sid'],x['event']):x for x in idc.get(dt,[])}
 shadow_lots={k:dict(v) for k,v in lots.items()};shadow_cash=cash
 for t0 in [x for x in ido.get(dt,[]) if x['side'].startswith('SELL')]:
  p0=price(t0['sid'],dt,'raw_open')*D('.9995');f0=fee(t0['sid'],dt,t0['qty'],p0,'sell');q0=sum(shadow_lots[l]['q'] for l in t0['lots'])
  equal('intent_sell_inventory_quantity',t0['qty'],q0,[dt,t0['sid']]);equal('intent_sell_T1',all(shadow_lots[l]['bought']<dt for l in t0['lots']),True,[dt,t0['sid']])
  shadow_cash+=q0*p0-f0
  for lid in t0['lots']:del shadow_lots[lid]
 snav=shadow_cash+recv+sum((l['q']*price(l['sid'],dt,'raw_open') for l in shadow_lots.values()),D(0));ssv=defaultdict(lambda:D(0));ssec=defaultdict(lambda:D(0))
 for l in shadow_lots.values():ssv[l['sid']]+=l['q']*price(l['sid'],dt,'raw_open');ssec[mapping[l['sid']]]+=l['q']*price(l['sid'],dt,'raw_open')
 for it in idc.get(dt,[]):
  s=it['sid'];t=it['signal_day'];typ=it['event'];rid=it.get('round_id');p=price(s,dt,'raw_open')*D('1.0005')
  if typ=='ADD':
   n0=D(attempts[rid]['nav0']);closebudget=min(D('.02')*n0,max(D(0),D('.04')*n0-prev_state[t]['q'].get(rid,0)*price(s,t,'raw_close')));qq=sum(l['q'] for l in shadow_lots.values() if l['rid']==rid);budget=min(closebudget,max(D(0),D('.04')*n0-qq*price(s,dt,'raw_open')))
  else:budget=D('.02')*D(ld[t]['NAV'])
  caps0=dict(attempt_budget=budget,stock_cap=max(D(0),D('.10')*snav-ssv[s]),sector_cap=max(D(0),D('.10')*snav-ssec[mapping[s]]),cash_reserve=max(D(0),shadow_cash-D('.10')*snav))
  for k,v in caps0.items():equal('original_intent_'+k,D(it[k]),v,[dt,s,typ])
  q0=version(rules['quantity_versions'][s],dt)['rule']['buy_minimum'] if typ=='SEED' else size(s,dt,p,min(caps0.values()),it['planned_q'])
  if it['decision']=='PASS':
   equal('original_intent_exact_quantity',it['executed_q'],q0,[dt,s,typ]);cost=q0*p+fee(s,dt,q0,p,'buy');equal('original_intent_capital_allowed',cost<=min(caps0.values()),True,[dt,s,typ]);shadow_cash-=cost;ssv[s]+=cost;ssec[mapping[s]]+=cost
  elif 'CAPITAL_REJECT:' in it['decision']:equal('original_intent_reject_justified',q0*p+fee(s,dt,q0,p,'buy')>min(caps0.values()),True,[dt,s,typ])
  elif 'ADD_NO_LEGAL_Q:' in it['decision']:equal('original_intent_ADD_zero_quantity',q0,0,[dt,s,typ])
 sell_orders=[x for x in today if x['side'].startswith('SELL')]
 equal('global_exit_symbol_order',[x['sid'] for x in sell_orders],sorted(x['sid'] for x in sell_orders),dt)
 for tr in sell_orders:
  s=tr['sid'];q=tr['qty'];rid=tr['round_id'];p=price(s,dt,'raw_open')*D('.9995');f=fee(s,dt,q,p,'sell');flow=q*p-f
  for k,v in {'price':p,'fee':f,'notional':q*p,'cash_delta':flow}.items():equal('sell_'+k,D(tr[k]),v,tr['order_seq'])
  named=[lots[lid] for lid in tr['lots']];equal('sold_lot_sum',sum(x['q'] for x in named),q,tr['order_seq']);equal('T1_sellable',all(x['bought']<dt for x in named),True,tr['order_seq'])
  for lid in tr['lots']:del lots[lid]
  cf[rid]+=flow;cash+=flow;fees+=f
 # Frozen account state after exits; conservative reservations affect only local cash/exposure.
 mvopen=sum((x['q']*price(x['sid'],dt,'raw_open') for x in lots.values()),D(0));open_nav=cash+recv+mvopen;rcash=cash;sv={s:inv(s=s)*price(s,dt,'raw_open') for s in {x['sid'] for x in lots.values()}};sec=defaultdict(lambda:D(0))
 for s,v in sv.items():sec[mapping[s]]+=v
 keys=[(0,cpcreated[x['cp_id']]['day'],x['sid']) if x['event']=='ADD' else (1,x['signal_day'],x['sid']) for x in oc]
 equal('global_ADD_then_SEED_queue',keys,sorted(keys),dt);equal('allocation_ranks',[x['allocation_rank'] for x in oc],list(range(1,len(oc)+1)),dt)
 buys={(x['sid'],x['side'][4:]):x for x in today if x['side'].startswith('BUY')};filled=[]
 for x in oc:
  s=x['sid'];t=x['signal_day'];rid=x.get('round_id');typ=x['event'];p=price(s,dt,'raw_open')*D('1.0005');capital_stats[x['decision']]+=1
  if typ=='ADD':
   a=attempts[rid];n0=D(a['nav0']);pre=prev_state[t];qclose=pre['q'].get(rid,0);closebudget=min(D('.02')*n0,max(D(0),D('.04')*n0-qclose*price(s,t,'raw_close')));budget=min(closebudget,max(D(0),D('.04')*n0-inv(rid=rid)*price(s,dt,'raw_open')))
  else:n0=D(ld[t]['NAV']);budget=D('.02')*n0
  caps=dict(attempt_budget=budget,stock_cap=max(D(0),D('.10')*open_nav-sv.get(s,D(0))),sector_cap=max(D(0),D('.10')*open_nav-sec[mapping[s]]),cash_reserve=max(D(0),rcash-D('.10')*open_nav))
  for k,v in caps.items():equal('reservation_'+k,D(x[k]),v,[dt,s,typ])
  eligible_cap=int(raw[s].raw_volume[raw[s].raw_volume.gt(0)].loc[:pd.Timestamp(t)].tail(20).mean()*.01);qr=version(rules['quantity_versions'][s],dt)['rule']
  plan=qr['buy_minimum'] if typ=='SEED' else size(s,t,price(s,t,'raw_close')*D('1.0005'),closebudget,eligible_cap)
  equal('close_planned_quantity',x['planned_q'],plan,[dt,s,typ])
  qexpect=qr['buy_minimum'] if typ=='SEED' else size(s,dt,p,min(caps.values()),min(plan,eligible_cap,original[(s,typ)]['executed_q']))
  if x['decision'] in ['PASS','NO_FILL_ONEPRICE_EXPOST']:
   tr=buys.get((s,typ));rr=next(r for r in rd.get(dt,[]) if r['sid']==s and r['kind']==typ);q=rr['reserved_q'];before=rcash;cost=q*p+fee(s,dt,q,p,'buy')
   equal('original_PASS_required',original[(s,typ)]['decision'],'PASS',[dt,s,typ]);equal('reserved_qty_at_most_original',q<=original[(s,typ)]['executed_q'],True,[dt,s,typ]);equal('reserved_qty_exact',q,qexpect,[dt,s,typ]);equal('cost_within_all_caps',cost<=min(caps.values()),True,[dt,s,typ])
   rcash-=cost;sec[mapping[s]]+=cost;sv[s]=sv.get(s,D(0))+cost
   for k,v in dict(original_q=original[(s,typ)]['executed_q'],reserved_q=q,reserved_cost=cost,cash_before=before,cash_after=rcash,rank=x['allocation_rank']).items():equal('reservation_record_'+k,D(str(rr[k])),D(str(v)),[dt,s,typ])
   equal('reserved_cash_10pct',rcash>=D('.10')*open_nav,True,[dt,s,typ])
   if x['decision']=='PASS':
    equal('one_fill_per_pass',tr is not None,True,[dt,s,typ]);equal('exact_allocated_quantity',tr['qty'],q,[dt,s,typ]);filled.append(tr['order_seq'])
   else:
    equal('nofill_has_no_trade',tr is None,True,[dt,s,typ]);nn=next(n for n in nd.get(dt,[]) if n['sid']==s and n['side']=='BUY_'+typ);equal('nofill_qty_matches_reservation',nn['qty'],q,[dt,s,typ]);equal('nofill_reservation_cost',D(nn['reserved_cost']),cost,[dt,s,typ])
  elif 'CAPITAL_REJECT:' in x['decision']:
   equal('capital_reject_limiter',x['decision'].split(':')[-1],min(caps,key=caps.get),[dt,s]);equal('capital_reject_minlot_too_large',qexpect*p+fee(s,dt,qexpect,p,'buy')>min(caps.values()),True,[dt,s]);equal('rejected_no_trade',(s,typ) not in buys,True,[dt,s])
  elif 'ADD_NO_LEGAL_Q:' in x['decision']:
   equal('ADD_no_legal_quantity',qexpect,0,[dt,s]);equal('ADD_reject_limiter',x['decision'].split(':')[-1],min(caps,key=caps.get),[dt,s]);equal('rejected_no_trade',(s,typ) not in buys,True,[dt,s])
  else:equal('rejected_no_trade',(s,typ) not in buys,True,[dt,s])
 equal('fill_order_equals_reservation_order',[x['order_seq'] for x in today if x['side'].startswith('BUY')],filled,dt)
 for tr in [x for x in today if x['side'].startswith('BUY')]:
  s=tr['sid'];q=tr['qty'];rid=tr['round_id'];p=price(s,dt,'raw_open')*D('1.0005');f=fee(s,dt,q,p,'buy');flow=-(q*p+f)
  for k,v in {'price':p,'fee':f,'notional':q*p,'cash_delta':flow,'all_in_cost':-flow}.items():equal('buy_'+k,D(tr[k]),v,tr['order_seq'])
  qr=version(rules['quantity_versions'][s],dt)['rule'];equal('legal_buy_quantity',q>=qr['buy_minimum'] and (q-qr['buy_minimum'])%qr['buy_step']==0,True,tr['order_seq']);equal('frozen_attempt_NAV',D(tr['frozen_attempt_NAV']),D(ld[seed[rid]['signal_day']]['NAV']),tr['order_seq'])
  if tr['side']=='BUY_SEED':equal('minimum_seed',q,qr['buy_minimum'],tr['order_seq'])
  else:
   oldq=inv(rid=rid);sp=price(s,dt,'raw_open')*D('.9995');net=cf[rid]+div[rid]+oldq*sp-fee(s,dt,oldq,sp,'sell');prev=prev_state[tr['signal_day']];psp=price(s,tr['signal_day'],'raw_close')*D('.9995');pq=prev['q'].get(rid,0);pnet=prev['cf'].get(rid,D(0))+prev['div'].get(rid,D(0))+pq*psp-fee(s,tr['signal_day'],pq,psp,'sell')
   equal('ADD_open_net',D(tr['open_net']),net,tr['order_seq']);equal('ADD_close_net',D(tr['close_net']),pnet,tr['order_seq']);equal('ADD_positive_both',net>0 and pnet>0,True,tr['order_seq']);equal('ADD_2pct_buy_budget',-flow<=D('.02')*D(tr['frozen_attempt_NAV']),True,tr['order_seq']);equal('ADD_4pct_capital_slot',-flow+oldq*price(s,dt,'raw_open')<=D('.04')*D(tr['frozen_attempt_NAV']),True,tr['order_seq'])
  lots[tr['lot_id']]=dict(q=q,sid=s,rid=rid,bought=dt);cf[rid]+=flow;cash+=flow;fees+=f
 released=sum((D(n['reserved_cost']) for n in nd.get(dt,[]) if n['side'].startswith('BUY')),D(0))
 equal('cash_equals_reservations_plus_end_batch_release',cash,rcash+released,dt)
 for it in idc.get(dt,[]):
  if it['decision']!='PASS':equal('original_reject_never_revived',(it['sid'],it['event']) not in buys and not any(r['sid']==it['sid'] and r['kind']==it['event'] for r in rd.get(dt,[])),True,[dt,it['sid']])
 for tr in today:
  px=[price(tr['sid'],dt,k) for k in ['raw_open','raw_high','raw_low','raw_close']];equal('actual_fill_gate_finite_positive',all(p.is_finite() and p>0 for p in px),True,tr['order_seq']);equal('actual_fill_not_equal_bar',len(set(px))!=1,True,tr['order_seq'])
 for nf in nd.get(dt,[]):
  s=nf['sid'];px=[price(s,dt,k) for k in ['raw_open','raw_high','raw_low','raw_close']];equal('no_fill_exact_positive_equal_bar',all(p.is_finite() and p>0 for p in px) and len(set(px))==1,True,[dt,s]);equal('no_fill_no_matching_actual_trade',not any(tr['sid']==s and tr['side']==nf['side'] for tr in today),True,[dt,s])
  if nf['side']=='BUY_SEED':
   equal('unfilled_seed_no_new_attempt',not any(a['sid']==s and a['seed_day']==dt for a in attempts.values()),True,[dt,s]);equal('unfilled_seed_no_inventory',inv(s=s),0,[dt,s])
  elif nf['side']=='BUY_ADD':equal('unfilled_ADD_no_CP_consumption',not any(x['event']=='CONSUMED_ON_FILL' and x['cp_id']==nf['cp_id'] and x['day']==dt for x in read(run/'CP_EVENTS.json')),True,[dt,s])
  else:
   equal('unfilled_sell_lots_retained',all(l in lots for l in nf['lots']),True,[dt,s]);equal('unfilled_sell_T1',all(lots[l]['bought']<dt for l in nf['lots']),True,[dt,s])
 for ev in events:
  if ev['record_date']==dt:
   ls=[x for x in lots.values() if x['sid']==ev['sid']];rids={x['rid'] for x in ls};assert len(rids)<=1;snaps[(ev['sid'],dt)]=(sum(x['q'] for x in ls),next(iter(rids)) if rids else None)
  claim=claims.get((ev['sid'],ev['ex_date']))
  if ev['pay_date']==dt and claim:
   cash+=claim[0];recv-=claim[0];expected_equity.append(('PAY_CLOSE_NET80',ev['sid'],claim[1],str(-claim[0]),str(claim[0])))
 actual_equity=[(x['event'],x['sid'],x['round_id'],x['receivable_delta'],x['cash_delta']) for x in ed.get(dt,[]) if x['event']!='FACTOR_BRIDGE'];equal('independent_record_based_entitlements',actual_equity,expected_equity,dt)
 mv=sum((x['q']*price(x['sid'],dt,'raw_close') for x in lots.values()),D(0));nav=cash+recv+mv;marks={s:inv(s=s) for s in {x['sid'] for x in lots.values()}};netliq=cash+recv+sum((q*price(s,dt,'raw_close')*D('.9995')-fee(s,dt,q,price(s,dt,'raw_close')*D('.9995'),'sell') for s,q in marks.items()),D(0))
 for k,v in dict(cash=cash,receivable=recv,market_value=mv,NAV=nav,net_liquidation_NAV=netliq,fees_paid=fees,shares=sum(x['q'] for x in lots.values()),stocks=len(marks)).items():equal('daily_'+k,D(str(row[k])),v,dt)
 hs={h['lot_id']:h for h in hd.get(dt,[])};equal('holding_lot_id_set',set(hs),set(lots),dt)
 for lid,x in lots.items():equal('holding_quantity',hs[lid]['qty'],x['q'],[dt,lid]);equal('holding_mark',D(hs[lid]['market_value']),x['q']*price(x['sid'],dt,'raw_close'),[dt,lid])
 ss={x['sector51']:x for x in sd.get(dt,[])};equal('all_50_sectors_daily',set(ss),set(sectors),dt)
 for secname,x in ss.items():
  smv=sum((l['q']*price(l['sid'],dt,'raw_close') for l in lots.values() if mapping[l['sid']]==secname),D(0));scf=sum((v for rid,v in cf.items() if mapping[attempts[rid]['sid']]==secname),D(0));sdiv=sum((v for rid,v in div.items() if mapping[attempts[rid]['sid']]==secname),D(0))
  for k,v in dict(market_value=smv,trade_cashflow=scf,net80_entitlement=sdiv,marked_net_pnl=scf+sdiv+smv).items():equal('sector_'+k,D(x[k]),v,[dt,secname])
 equal('sector_pnl_sums_to_account_pnl',sum((D(x['marked_net_pnl']) for x in ss.values()),D(0)),nav-D(1200000),dt)
 prev_state[dt]=dict(q={rid:inv(rid=rid) for rid in cf},cf=dict(cf),div=dict(div));daily.append(dict(day=dt,cash=str(cash),receivable=str(recv),market_value=str(mv),NAV=str(nav),net_liquidation_NAV=str(netliq),stocks=len(marks),shares=sum(marks.values())));min_cash_pct=min(min_cash_pct if min_cash_pct is not None else D(100),100*cash/nav)
equal('all_orders_in_certified_ledger',all(x['day'] in ld for x in orders),True,run.name);cps=[x['cp_id'] for x in orders if x['side']=='BUY_ADD'];equal('CP_consumption_unique',len(cps),len(set(cps)),run.name);equal('all_trades_mapped',all(x['sid'] in mapping for x in orders),True,run.name)
for rid,a in attempts.items():
 equal('attempt_cashflow',D(a['cashflow']),cf[rid],rid);equal('attempt_dividend',D(a['dividend']),div[rid],rid);equal('attempt_final_quantity',a['final_qty'],inv(rid=rid),rid)
report=dict(status='PASS' if not errors else 'FAIL',run=str(run),basis='Stress audit adapted from independently reviewed arithmetic, with newly independent original-intent, reservation, no-fill, end-batch release and exact OHLC gate checks. Independent order replay and dated fee arithmetic, without importing or running strategy engine. Corporate entitlements rebuilt from record-close inventory. Queue reservations rebuilt from one shared cash/NAV plus separate industry buckets.',days=len(ledger),orders=len(orders),nofills=len(nofills),reservations=len(reservations),intents=len(intents),checks=dict(checks),error_count=len(errors),errors=errors,capital_decisions=dict(capital_stats),minimum_close_cash_percent=str(min_cash_pct),last=daily[-1],source_hashes={str(p):sha(p) for p in [Path(__file__),run/'ORDERS.json',run/'DAY_LEDGER.json',run/'HOLDINGS.json',run/'CANDIDATES.json',run/'SECTOR_DAILY.json']},limitations=['OPEN +/- 5bp is a cost proxy, not literal exchange matching.','2% ADD budget and 4% round capital slot are not loss limits.','Positive whole-round net profit need not cover incremental downside.','Fixed current universe and current classification are not PIT.'])
(OUT/'RECONCILIATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(OUT/'REBUILT_LEDGER.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
