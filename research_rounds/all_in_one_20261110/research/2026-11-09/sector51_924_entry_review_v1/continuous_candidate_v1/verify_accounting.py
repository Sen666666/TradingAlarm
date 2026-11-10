"""Independent read-only transaction replay. Writes only new verification artifacts."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'full_20241031_once'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.dont_write_bytecode=True;sys.path.insert(0,str(B/'code'))
from sector_account import QuantityRule,FeeComponent,FeeSchedule
from market_rules import version_on,market_identity_on
read=lambda p:json.loads(Path(p).read_text());rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');manifest={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')}
orders=read(R/'ORDERS.json');ledger=read(R/'DAY_LEDGER.json');held=read(R/'HOLDINGS.json');eq=read(R/'EQUITY_EVENTS.json');attempts=read(R/'ATTEMPTS.json');am={a['id']:a for a in attempts};raw={};lots={};sq=defaultdict(int);cash=D(1200000);receivable=D(0);fees=D(0);cf=defaultdict(lambda:D(0));div=defaultdict(lambda:D(0));bought=defaultdict(int);rows=[];coh=[]
for s in {x['sid'] for x in orders}:raw[s]=pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')))
def meta(s,day):
 ident=market_identity_on(rules,s,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule'];return QuantityRule(**version_on(rules['quantity_versions'][s],day,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(rules['security_metadata'][s]['par_value']))
def fee(s,day,q,p,side):
 _,fs,pa=meta(s,day);return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=pa).values(),D(0))
for rec in ledger:
 dt=rec['day'];td=pd.Timestamp(dt);phase=-1
 for t in [t for t in orders if t['day']==dt]:
  s=t['sid'];q=t['qty'];p=D(t['price']);f=D(t['fee']);rid=t['round_id'];buy=t['side'].startswith('BUY');qr,_,_=meta(s,dt)
  rank=2 if t['side']=='BUY_SEED' else 1 if t['side']=='BUY_ADD' else 0;assert rank>=phase;phase=rank
  assert p==D(str(raw[s].at[td,'raw_open']))*(D('1.0005') if buy else D('.9995'))
  assert f==fee(s,dt,q,p,'buy' if buy else 'sell')
  expected=-(q*p+f) if buy else q*p-f;assert expected==D(t['cash_delta']);cash+=expected;fees+=f;cf[rid]+=expected
  if buy:
   assert qr.buy_floor(q)==q
   if t['side']=='BUY_SEED':assert q==qr.buy_minimum
   assert q*p+f<=D('.02')*D(t['frozen_attempt_NAV'])
   assert t['lot_id'] not in lots;lots[t['lot_id']]={'sid':s,'q':q,'bought':dt,'round':rid};sq[s]+=q;bought[(rid,dt)]+=q
   if t['side']=='BUY_ADD':assert D(t['close_net'])>0 and D(t['open_net'])>0
  else:
   assert sum(lots[i]['q'] for i in t['lots'])==q
   for lid in t['lots']:assert lid in lots and lots[lid]['bought']<dt;del lots[lid]
   sq[s]-=q;assert sq[s]>=0
 for e in [x for x in eq if x['day']==dt]:
  cash+=D(e['cash_delta']);receivable+=D(e['receivable_delta'])
  if e['event']=='ACCRUE_NET80':div[e['round_id']]+=D(e['receivable_delta'])
 hv=[h for h in held if h['day']==dt];assert {h['lot_id'] for h in hv}==set(lots)
 for h in hv:
  assert h['qty']==lots[h['lot_id']]['q'];assert D(h['raw_mark'])==D(str(raw[h['sid']].at[td,'raw_close']))
 mv=sum((q*D(str(raw[s].at[td,'raw_close'])) for s,q in sq.items() if q),D(0));nav=cash+receivable+mv
 assert cash==D(rec['cash']) and receivable==D(rec['receivable']) and mv==D(rec['market_value']) and nav==D(rec['NAV']) and fees==D(rec['fees_paid'])
 assert sum(sq.values())==rec['shares'];assert sum(q>0 for q in sq.values())==rec['stocks'];assert cash>=0
 liq=cash+receivable+sum((q*D(str(raw[s].at[td,'raw_close']))*D('.9995')-fee(s,dt,q,D(str(raw[s].at[td,'raw_close']))*D('.9995'),'sell') for s,q in sq.items() if q),D(0));assert liq==D(rec['net_liquidation_NAV'])
 rows.append(dict(day=dt,cash=str(cash),receivable=str(receivable),shares=sum(sq.values()),NAV=str(nav),residual='0',fees=str(fees)))
 for cohort in ['Sep06_episode','Sep18_and_later']:
  ids={a['id'] for a in attempts if (a['signal_day']<'2024-09-18')==(cohort=='Sep06_episode')};val=sum((h['qty']*D(h['raw_mark']) for h in hv if h['round_id'] in ids),D(0));cashflow=sum((cf[i] for i in ids),D(0));dv=sum((div[i] for i in ids),D(0));coh.append(dict(day=dt,cohort=cohort,market_value=str(val),trade_cashflow=str(cashflow),dividend=str(dv),marked_net_pnl=str(val+cashflow+dv)))
assert len({t['cp_id'] for t in orders if t['side']=='BUY_ADD'})==sum(t['side']=='BUY_ADD' for t in orders)
for a in attempts:
 assert cf[a['id']]==D(a['cashflow']);assert sum(t['side']=='BUY_SEED' for t in orders if t['round_id']==a['id'])==1
 assert sum(l['q'] for l in lots.values() if l['round']==a['id'])==a['final_qty']
# First computed 9/23 prefix must match the extended run. Only bridge diagnostic field was corrected.
pref=O/'prefix_20240923_once';prefix={}
for name in ['ORDERS','DAY_LEDGER','HOLDINGS','CP_EVENTS','CANDIDATES']:
 x=read(pref/(name+'.json'));y=[r for r in read(R/(name+'.json')) if r['day']<='2024-09-23'];assert x==y,name;prefix[name]=len(x)
pd.DataFrame(rows).to_csv(O/'ACCOUNT_RECONCILIATION.csv',index=False);pd.DataFrame(coh).to_csv(O/'COHORT_DAILY.csv',index=False)
summary=dict(result='PASS',ledger_days=len(ledger),orders=len(orders),attempts=len(attempts),T1_per_lot=True,exact_dated_fees=True,raw_OPEN_proxy_exact=True,buy_quantities_legal=True,seed_minimum_unit=True,all_add_close_and_open_net_positive=True,CP_unique_actual_consumption=True,exit_ADD_SEED_order=True,cash_shares_receivable_NAV_exact=True,per_attempt_cashflow_exact=True,prefix_20240923_exact=prefix,no_real_execution_certification=True)
(O/'INDEPENDENT_ACCOUNTING_QA.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));print(pd.DataFrame(ledger)[lambda x:x.day.isin(['2024-09-23','2024-09-30','2024-10-08','2024-10-31'])].to_string(index=False));print(pd.DataFrame(coh)[lambda x:x.day.isin(['2024-09-23','2024-09-30','2024-10-08','2024-10-31'])].to_string(index=False))
