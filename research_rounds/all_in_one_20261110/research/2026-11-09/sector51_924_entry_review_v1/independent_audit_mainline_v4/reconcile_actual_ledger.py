# Prepared from the previously independently reconciled M3 ledger auditor.
# ONLY changed minimum-SEED equality to 2%-of-original-NAV check; q_econ is audited separately.
# No engine import. Run only against an already produced account path.
"""Independent ledger and capital audit. Reads executed outputs; never runs strategy."""
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_CEILING
from collections import defaultdict,Counter
import json,sys,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;run=Path(sys.argv[1]);arm='M';tag=run.parent.name+'_'+run.name;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
rules=read(B/'inputs-v2/market-rules.json');manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
ro=pd.read_csv(P/'joint51_candidate_v1/CLASSIFICATION_ALL1709.csv');mapping=ro[ro.eligible].set_index('symbol').sector51.to_dict();sectors=sorted(set(mapping.values()))
orders=read(run/'ORDERS.json');ledger=read(run/'DAY_LEDGER.json');holdings=read(run/'HOLDINGS.json');equity=read(run/'EQUITY_EVENTS.json');candidates=read(run/'CANDIDATES.json');sector_daily=read(run/'SECTOR_DAILY.json');attempts={x['id']:x for x in read(run/'ATTEMPTS.json')};cpcreated={x['cp_id']:x for x in read(run/'CP_EVENTS.json') if x['event']=='CREATED_AFTER_SEED'}
events=read(E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json')+read(P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json')+read(P/'joint51_candidate_v9_facts/ADDITIONAL_REVIEWED_EVENTS.json')+read(P/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_603083_V1.json')+read(P/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20240930_RETAINED_THREE_V1.json')+read(P/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_300870_V1.json');events=[e for e in events if e['sid'] in mapping and ledger[0]['day']<=e['ex_date']<=ledger[-1]['day']]
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
 sell_orders=[x for x in today if x['side'].startswith('SELL')]
 normal=[x for x in sell_orders if not x.get('transfer_rank')];trans=[x for x in sell_orders if x.get('transfer_rank')];equal('mandatory_exit_symbol_order',[x['sid'] for x in normal],sorted(x['sid'] for x in normal),dt);equal('mandatory_exits_before_transfer',sell_orders,normal+trans,dt);equal('frozen_transfer_rank_order',[x['transfer_rank'] for x in trans],sorted(x['transfer_rank'] for x in trans),dt);transfer_loss=D(0)
 for tr in sell_orders:
  s=tr['sid'];q=tr['qty'];rid=tr['round_id'];p=price(s,dt,'raw_open')*D('.9995');f=fee(s,dt,q,p,'sell');flow=q*p-f
  for k,v in {'price':p,'fee':f,'notional':q*p,'cash_delta':flow}.items():equal('sell_'+k,D(tr[k]),v,tr['order_seq'])
  named=[lots[lid] for lid in tr['lots']];sold=tr.get('lot_quantities') or {lid:lots[lid]['q'] for lid in tr['lots']};equal('sold_lot_sum',sum(sold.values()),q,tr['order_seq']);equal('T1_sellable',all(x['bought']<dt for x in named),True,tr['order_seq'])
  for lid in tr['lots']:
   equal('sold_within_existing_lot',0<sold[lid]<=lots[lid]['q'],True,[tr['order_seq'],lid]);lots[lid]['q']-=sold[lid]
   if not lots[lid]['q']:del lots[lid]
  if tr.get('transfer_rank'):transfer_loss+=q*price(s,dt,'raw_open')-flow
  cf[rid]+=flow;cash+=flow;fees+=f
 for tr in [x for x in today if x['side'].startswith('BUY')]:
  s=tr['sid'];q=tr['qty'];rid=tr['round_id'];p=price(s,dt,'raw_open')*D('1.0005');f=fee(s,dt,q,p,'buy');flow=-(q*p+f)
  for k,v in {'price':p,'fee':f,'notional':q*p,'cash_delta':flow,'all_in_cost':-flow}.items():equal('buy_'+k,D(tr[k]),v,tr['order_seq'])
  qr=version(rules['quantity_versions'][s],dt)['rule'];equal('legal_buy_quantity',q>=qr['buy_minimum'] and (q-qr['buy_minimum'])%qr['buy_step']==0,True,tr['order_seq']);equal('frozen_attempt_NAV',D(tr['frozen_attempt_NAV']),D(ld[seed[rid]['signal_day']]['NAV']),tr['order_seq'])
  if tr['side']=='BUY_SEED':equal('SEED_2pct_buy_budget',-flow<=D('.02')*D(tr['frozen_attempt_NAV']),True,tr['order_seq'])
  else:
   oldq=inv(rid=rid);sp=price(s,dt,'raw_open')*D('.9995');net=cf[rid]+div[rid]+oldq*sp-fee(s,dt,oldq,sp,'sell');prev=prev_state[tr['signal_day']];psp=price(s,tr['signal_day'],'raw_close')*D('.9995');pq=prev['q'].get(rid,0);pnet=prev['cf'].get(rid,D(0))+prev['div'].get(rid,D(0))+pq*psp-fee(s,tr['signal_day'],pq,psp,'sell')
   equal('ADD_open_net',D(tr['open_net']),net,tr['order_seq']);equal('ADD_close_net',D(tr['close_net']),pnet,tr['order_seq']);equal('ADD_positive_both',net>0 and pnet>0,True,tr['order_seq']);equal('ADD_2pct_buy_budget',-flow<=D('.02')*D(tr['frozen_attempt_NAV']),True,tr['order_seq']);equal('ADD_4pct_capital_slot',-flow+oldq*price(s,dt,'raw_open')<=D('.04')*D(tr['frozen_attempt_NAV']),True,tr['order_seq'])
  lots[tr['lot_id']]=dict(q=q,sid=s,rid=rid,bought=dt);cf[rid]+=flow;cash+=flow;fees+=f
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
report=dict(status='PASS' if not errors else 'FAIL',run=str(run),basis='Independent actual-order ledger replay and dated fee arithmetic, without importing or running strategy engine. Corporate entitlements rebuilt from record-close inventory. This pass checks accounting, T+1, exact fees, lots, whole-round positive dual-time ADD profit, SEED 2% cap, ADD 2%/4% slots and full industry attribution only. M4 frozen economic seed quantity, event identity/priority/spend, reference targets, queue and transfer causality are a separate pass. This ledger audit does not certify those strategy states.',days=len(ledger),orders=len(orders),checks=dict(checks),error_count=len(errors),errors=errors,capital_decisions=dict(capital_stats),minimum_close_cash_percent=str(min_cash_pct),last=daily[-1],source_hashes={str(p):sha(p) for p in [Path(__file__),run/'ORDERS.json',run/'DAY_LEDGER.json',run/'HOLDINGS.json',run/'CANDIDATES.json',run/'SECTOR_DAILY.json']},limitations=['OPEN +/- 5bp is a cost proxy, not literal exchange matching.','2% ADD budget and 4% round capital slot are not loss limits.','Positive whole-round net profit need not cover incremental downside.','Fixed current universe and current classification are not PIT.'])
(O/(tag+'_RECONCILIATION.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(O/(tag+'_REBUILT_LEDGER.json')).write_text(json.dumps(daily,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
