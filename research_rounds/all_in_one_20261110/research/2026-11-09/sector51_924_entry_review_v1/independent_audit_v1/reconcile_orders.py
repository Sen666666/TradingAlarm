from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_CEILING
from collections import defaultdict, Counter
import json, sys, hashlib
import pandas as pd
O=Path(__file__).resolve().parent
run=Path(sys.argv[1])
read=lambda p: json.loads(Path(p).read_text())
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
rules=read(B/'inputs-v2/market-rules.json')
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
orders=read(run/'ORDERS.json'); ledger=read(run/'DAY_LEDGER.json'); holdings=read(run/'HOLDINGS.json'); equity=read(run/'EQUITY_EVENTS.json')
events=read(O/'REVIEWED_CASH_EVENTS_14.json')
raw={s:pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'))) for s in {r['sid'] for r in orders}}
lots={}; cash=D(1200000); recv=D(0); fees=D(0); claims={}; snaps={}; cf=defaultdict(lambda:D(0)); div=defaultdict(lambda:D(0)); checks=Counter(); errors=[]; daily=[]
def equal(label,x,y,ctx):
 checks[label]+=1
 if x!=y:errors.append(dict(check=label,context=ctx,actual=str(x),expected=str(y)))
def version(vs,dt):
 z=[v for v in vs if v['from']<=dt and (v.get('to') is None or dt<v['to'])]
 assert len(z)==1
 return z[0]
def fee(s,dt,q,p,side):
 venue=version(rules['venue_versions'][s],dt)['venue']
 comps=version(rules['fee_versions'][venue],dt)['schedule']['components']; total=D(0)
 for c in comps:
  if c.get('side','both') not in ('both',side):continue
  basis=c.get('amount_basis','notional')
  base=q*p if basis=='notional' else D(q) if basis=='shares' else q*D(rules['security_metadata'][s]['par_value'])
  v=max(D(c.get('minimum_local','0')),base*D(c['rate']))
  if c.get('maximum_local') is not None:v=min(v,D(c['maximum_local']))
  if c.get('rounding_unit') is not None:
   unit=D(c['rounding_unit']);v=(v/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
  total+=v
 return total
prev_state={}
for row in ledger:
 dt=row['day'];t=pd.Timestamp(dt);today=[x for x in orders if x['day']==dt]
 # Independently recognize own record-close quantities before opening trades.
 for ev in events:
  if ev['ex_date']==dt:
   q,rid=snaps.get((ev['sid'],ev['record_date']),(0,None))
   if q:
    amount=D(q)*D(ev['d_cash'])*D('.8');recv+=amount;div[rid]+=amount;claims[(ev['sid'],ev['ex_date'])]=(amount,rid)
 for tr in today:
  s=tr['sid'];q=tr['qty'];rid=tr['round_id'];buy=tr['side'].startswith('BUY');side='buy' if buy else 'sell'
  p=D(str(raw[s].at[t,'raw_open']))*(D('1.0005') if buy else D('.9995'));f=fee(s,dt,q,p,side);flow=-(q*p+f) if buy else q*p-f
  equal('raw_open_slippage',D(tr['price']),p,tr['order_seq']);equal('fee_components',D(tr['fee']),f,tr['order_seq']);equal('notional',D(tr['notional']),q*p,tr['order_seq']);equal('cash_delta',D(tr['cash_delta']),flow,tr['order_seq'])
  if buy:
   qr=version(rules['quantity_versions'][s],dt)['rule'];equal('legal_buy_quantity',q>=qr['buy_minimum'] and (q-qr['buy_minimum'])%qr['buy_step']==0,True,tr['order_seq'])
   equal('next_open_after_signal',dt>tr['signal_day'],True,tr['order_seq'])
   if tr['side']=='BUY_SEED':equal('minimum_seed',q,qr['buy_minimum'],tr['order_seq'])
   if tr['side']=='BUY_ADD':
    oldq=sum(x['q'] for x in lots.values() if x['rid']==rid);sp=D(str(raw[s].at[t,'raw_open']))*D('.9995')
    net=cf[rid]+div[rid]+oldq*sp-fee(s,dt,oldq,sp,'sell')
    equal('ADD_open_net',D(tr['open_net']),net,tr['order_seq']);equal('ADD_positive_open',net>0,True,tr['order_seq'])
    prev=prev_state[tr['signal_day']];psp=D(str(raw[s].at[pd.Timestamp(tr['signal_day']),'raw_close']))*D('.9995');pq=prev['q'].get(rid,0)
    pnet=prev['cf'].get(rid,D(0))+prev['div'].get(rid,D(0))+pq*psp-fee(s,tr['signal_day'],pq,psp,'sell')
    equal('ADD_close_net',D(tr['close_net']),pnet,tr['order_seq']);equal('ADD_positive_close',pnet>0,True,tr['order_seq'])
    equal('ADD_2pct_budget',q*p+f<=D('.02')*D(tr['frozen_attempt_NAV']),True,tr['order_seq'])
    equal('ADD_4pct_remaining_slot',q*p+f+oldq*D(str(raw[s].at[t,'raw_open']))<=D('.04')*D(tr['frozen_attempt_NAV']),True,tr['order_seq'])
   lots[tr['lot_id']]={'q':q,'sid':s,'rid':rid,'bought':dt}
  else:
   named=[lots[lid] for lid in tr['lots']]
   equal('sold_lot_sum',sum(x['q'] for x in named),q,tr['order_seq'])
   equal('T1_sellable',all(x['bought']<dt for x in named),True,tr['order_seq'])
   for lid in tr['lots']:del lots[lid]
  cf[rid]+=flow;cash+=flow;fees+=f
 for ev in events:
  if ev['record_date']==dt:
   ls=[x for x in lots.values() if x['sid']==ev['sid']];rids={x['rid'] for x in ls};assert len(rids)<=1
   snaps[(ev['sid'],dt)]=(sum(x['q'] for x in ls),next(iter(rids)) if rids else None)
  claim=claims.get((ev['sid'],ev['ex_date']))
  if ev['pay_date']==dt and claim:cash+=claim[0];recv-=claim[0]
 mv=sum((x['q']*D(str(raw[x['sid']].at[t,'raw_close'])) for x in lots.values()),D(0));nav=cash+recv+mv
 marks={s:sum(x['q'] for x in lots.values() if x['sid']==s) for s in {x['sid'] for x in lots.values()}}
 netliq=cash+recv+sum((q*D(str(raw[s].at[t,'raw_close']))*D('.9995')-fee(s,dt,q,D(str(raw[s].at[t,'raw_close']))*D('.9995'),'sell') for s,q in marks.items()),D(0))
 for k,v in {'cash':cash,'receivable':recv,'market_value':mv,'NAV':nav,'net_liquidation_NAV':netliq,'fees_paid':fees,'shares':sum(x['q'] for x in lots.values()),'stocks':len(marks)}.items():equal('daily_'+k,D(str(row[k])),v,dt)
 hs={h['lot_id']:h for h in holdings if h['day']==dt}
 equal('holding_lot_id_set',set(hs),set(lots),dt)
 for lid,x in lots.items():
  h=hs[lid];equal('holding_quantity',h['qty'],x['q'],[dt,lid]);equal('holding_mark',D(h['market_value']),x['q']*D(str(raw[x['sid']].at[t,'raw_close'])),[dt,lid])
 prev_state[dt]={'q':{rid:sum(x['q'] for x in lots.values() if x['rid']==rid) for rid in cf},'cf':dict(cf),'div':dict(div)}
 daily.append({'day':dt,'cash':str(cash),'receivable':str(recv),'market_value':str(mv),'NAV':str(nav),'net_liquidation_NAV':str(netliq),'stocks':len(marks),'shares':sum(marks.values())})
equal('all_orders_inside_certified_ledger',all(x['day'] in prev_state for x in orders),True,run.name)
cps=[x['cp_id'] for x in orders if x['side']=='BUY_ADD'];equal('CP_consumption_unique',len(cps),len(set(cps)),run.name)
report={'run':str(run),'status':'PASS' if not errors else 'FAIL','basis':'Independent recomputation from order quantities and raw source prices; no strategy or economic account rerun. Fee arithmetic reimplemented from dated JSON without importing candidate or fee engine. Corporate entitlements reconstructed from record-close inventory and independently reviewed events.','days':len(ledger),'orders':len(orders),'checks':dict(checks),'errors':errors,'last':daily[-1],'input_sha256':{str(p):sha(p) for p in [Path(__file__),O/'REVIEWED_CASH_EVENTS_14.json',run/'ORDERS.json',run/'DAY_LEDGER.json',run/'HOLDINGS.json',run/'EQUITY_EVENTS.json']}}
(O/(run.name+'_RECONCILIATION.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
(O/(run.name+'_REBUILT_LEDGER.json')).write_text(json.dumps(daily,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
