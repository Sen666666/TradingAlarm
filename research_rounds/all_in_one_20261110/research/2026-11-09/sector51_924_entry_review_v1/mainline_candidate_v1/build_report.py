"""Read-only account reconstruction and report packaging after the frozen M run."""
from pathlib import Path
import json,hashlib,sys
from decimal import Decimal as D
import pandas as pd
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;P=O/'full_20241031_once';B=O.parent/'joint51_candidate_v9_facts'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def dec(v):return D(str(v))
orders=read(P/'ORDERS.json');ledger=read(P/'DAY_LEDGER.json');hold=read(P/'HOLDINGS.json');attempts=read(P/'ATTEMPTS.json');equity=read(P/'EQUITY_EVENTS.json');sectors=read(P/'SECTOR_DAILY.json');transfers=read(P/'TRANSFERS.json');proof=read(P/'INFORMATION_CONFIRMATIONS.json');req=read(P/'FUNDING_REQUESTS.json');rules=pd.read_csv(B/'CLASSIFICATION_ALL1709.csv').set_index('symbol');Z=D(0);INITIAL=D(1200000)
# Independently reconstruct signed cash, receivables, positions, fees and NAV.
cash=INITIAL;receivable=Z;shares={};lotcost={};fees=Z;qa=[];peak=INITIAL;maxdd=Z;dd=[];buy=Z;sell=Z;slippage=Z;prevnav=INITIAL;one=Z;two=Z
for d in ledger:
 day=d['day'];ts=[t for t in orders if t['day']==day];es=[e for e in equity if e['day']==day];dailybuy=Z;dailysell=Z
 for t in ts:
  q=int(t['qty']);s=t['sid'];cash+=dec(t['cash_delta']);fees+=dec(t['fee']);isbuy=t['side'].startswith('BUY');shares[s]=shares.get(s,0)+(q if isbuy else -q);assert shares[s]>=0
  notional=dec(t['notional']);raw=dec(t['price'])/(D('1.0005') if isbuy else D('.9995'));slippage+=abs(dec(t['price'])-raw)*q
  if isbuy:buy-=dec(t['cash_delta']);dailybuy+=notional;lotcost[t['lot_id']]=(q,-dec(t['cash_delta']))
  else:sell+=dec(t['cash_delta']);dailysell+=notional
 for e in es:cash+=dec(e.get('cash_delta',0));receivable+=dec(e.get('receivable_delta',0))
 hh=[h for h in hold if h['day']==day];mv=sum((dec(h['market_value']) for h in hh),Z);actualshares={}
 for h in hh:actualshares[h['sid']]=actualshares.get(h['sid'],0)+int(h['qty'])
 assert {s:q for s,q in shares.items() if q}==actualshares,('SHARES',day)
 nav=cash+receivable+mv;assert nav==dec(d['NAV']) and cash==dec(d['cash']) and receivable==dec(d['receivable']) and fees==dec(d['fees_paid']),('LEDGER',day)
 contribution=sum((dec(s['marked_net_pnl']) for s in sectors if s['day']==day),Z);assert contribution==nav-INITIAL,('ATTRIBUTION',day)
 peak=max(peak,nav);current=nav/peak-1;maxdd=min(maxdd,current);one+=max(dailybuy,dailysell)/prevnav;two+=(dailybuy+dailysell)/prevnav;prevnav=nav
 basis=sum((lotcost[h['lot_id']][1]*int(h['qty'])/lotcost[h['lot_id']][0] for h in hh),Z)
 secday=[s for s in sectors if s['day']==day];maxsec=max(secday,key=lambda x:dec(x['account_weight_pct']));row=dict(**d,return_pct=100*(nav/INITIAL-1),drawdown_pct=100*current,running_max_drawdown_pct=100*maxdd,cumulative_buy_all_in=buy,cumulative_sell_net=sell,net_trade_cash_investment=buy-sell,holding_lot_all_in_basis=basis,cumulative_slippage_proxy=slippage,cumulative_total_cost=slippage+fees,cumulative_one_way_turnover=one,cumulative_two_way_turnover=two,max_industry=maxsec['sector51'],max_industry_weight_pct=maxsec['account_weight_pct']);qa.append(row)
pd.DataFrame(qa).to_csv(O/'DAILY_ACCOUNT_METRICS.csv',index=False)
endpoints={r['day']:r for r in qa if r['day'] in ['2024-09-13','2024-09-23','2024-09-27','2024-10-08','2024-10-25','2024-10-31']};save(O/'ENDPOINTS.json',endpoints)
# Actual September23 security lots and lifetime funds, never opportunity proxies.
sep='2024-09-23';seps=[]
for s in sorted({x['sid'] for x in orders if x['day']<=sep and rules.loc[x['sid'],'sector_name']=='证券'}):
 tt=[x for x in orders if x['sid']==s and x['day']<=sep];hh=[h for h in hold if h['sid']==s and h['day']==sep];seps.append(dict(sid=s,name=rules.loc[s,'name'],seed_buy_all_in=-sum((dec(t['cash_delta']) for t in tt if t['side']=='BUY_SEED'),Z),add_buy_all_in=-sum((dec(t['cash_delta']) for t in tt if t['side']=='BUY_ADD'),Z),sell_net=sum((dec(t['cash_delta']) for t in tt if t['side'].startswith('SELL')),Z),seed_qty=sum(h['qty'] for h in hh if h['kind']=='SEED'),add_qty=sum(h['qty'] for h in hh if h['kind']=='ADD'),market_value=sum((dec(h['market_value']) for h in hh),Z),lot_cost_basis=sum((lotcost[h['lot_id']][1]*int(h['qty'])/lotcost[h['lot_id']][0] for h in hh),Z)))
pd.DataFrame(seps).to_csv(O/'SEP23_ACTUAL_SECURITIES.csv',index=False)
# All original September6 securities attempt outcomes, realized vs unfinished separated.
cohort=[a for a in attempts if a['signal_day']=='2024-09-06' and rules.loc[a['sid'],'sector_name']=='证券'];pd.DataFrame(cohort).to_csv(O/'SEP06_SECURITIES_ATTEMPTS.csv',index=False)
closed=[a for a in cohort if a['final_qty']==0];opened=[a for a in cohort if a['final_qty']];net=lambda a:dec(a['cashflow'])+dec(a['dividend']);save(O/'SEP06_SECURITIES_COHORT.json',dict(attempts=len(cohort),closed=len(closed),unfinished=len(opened),closed_total_net=sum((net(a) for a in closed),Z),closed_negative_loss=sum((net(a) for a in closed if net(a)<0),Z),closed_positive_gain=sum((net(a) for a in closed if net(a)>0),Z),unfinished_marked=sum((dec(a['marked_net_pnl']) for a in opened),Z),all_cohort_marked=sum((dec(a['marked_net_pnl']) for a in cohort),Z)))
# Fungible funding bridge, no fabricated earmarks.
fund={}
for day in ['2024-09-23','2024-09-27','2024-10-08','2024-10-25','2024-10-31']:
 rows=[x for x in qa if x['day']==day]
 if not rows:continue
 i=next(i for i,r in enumerate(qa) if r['day']==day);tt=[t for t in orders if t['day']==day];donor=[t for t in tt if t['reason'] in ['UNCONFIRMED_NON_MAINLINE_SEED','WEAK_SECTOR_ADD_LAYER']];semi=[t for t in tt if t['sector51']=='半导体'];fund[day]=dict(start_cash=INITIAL if i==0 else dec(qa[i-1]['cash']),mandatory_sell_net=sum((dec(t['cash_delta']) for t in tt if t['side'].startswith('SELL') and t not in donor),Z),donor_sell_net=sum((dec(t['cash_delta']) for t in donor),Z),semiconductor_seed_cost=-sum((dec(t['cash_delta']) for t in semi if t['side']=='BUY_SEED'),Z),semiconductor_add_cost=-sum((dec(t['cash_delta']) for t in semi if t['side']=='BUY_ADD'),Z),semiconductor_orders=semi,semiconductor_requests=[r for r in req if r['day']==day and rules.loc[r['sid'],'sector51']=='半导体'],end_cash=dec(rows[0]['cash']),fungible_cash_not_earmarked=True)
save(O/'KEYDAY_FUNDING_BRIDGE.json',fund)
# All donor price paths, good and bad, only adjusted price opportunity evaluation.
manifest={m['symbol']:m for m in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))};paths=[];summary=[];end=pd.Timestamp('2024-10-31');price_calendar=pd.read_parquet('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet',columns=[]).index
for t in orders:
 if t['reason'] not in ['UNCONFIRMED_NON_MAINLINE_SEED','WEAK_SECTOR_ADD_LAYER']:continue
 s=t['sid'];source=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));assert sha(Path(source))==manifest[s]['source_sha256'][source];z=pd.read_parquet(source);dt=pd.Timestamp(t['day']);ref=z.loc[dt];adjusted_exit=dec(t['price'])*dec(ref.adjustment_factor);vals=[]
 for d,r in z.reindex(price_calendar[(price_calendar>=dt)&(price_calendar<=end)]).iterrows():
  same=all(str(r[c])==str(ref[c]) for c in ['source_kind','source_path','segment_id']);valid=all(r[c]==True for c in ['observed_bar','price_eligible','volume_eligible']) and r.source_invalid==False and r.synthetic_event_bar==False
  ret=float(dec(r.raw_close)*dec(r.adjustment_factor)/adjusted_exit-1) if same and valid and pd.notna(r.raw_close) and r.raw_close>0 else None
  paths.append(dict(order_seq=t['order_seq'],sid=s,sell_day=t['day'],reason=t['reason'],day=str(d.date()),price_change_from_net_slippage_sell=ret,certified_same_source_price=ret is not None,not_counterfactual_account_return=True));
  if ret is not None:vals.append((d,ret))
 summary.append(dict(order_seq=t['order_seq'],sid=s,sell_day=t['day'],qty=t['qty'],reason=t['reason'],net_cash=t['cash_delta'],last_supported_day=str(vals[-1][0].date()) if vals else None,last_price_change=vals[-1][1] if vals else None,max_rebound=max((r[1] for r in vals),default=None),min_price_change=min((r[1] for r in vals),default=None),not_counterfactual_account_return=True))
pd.DataFrame(paths).to_csv(O/'ALL_DONOR_SUBSEQUENT_PRICE_PATHS.csv',index=False);pd.DataFrame(summary).to_csv(O/'ALL_DONOR_OPPORTUNITY_EVALUATION.csv',index=False)
openrows=read(P/'OPEN_SECTOR_EXPOSURE.json');maxopen=max(openrows,key=lambda r:dec(r['weight_pct'])) if openrows else None;maxclose=max(sectors,key=lambda r:dec(r['account_weight_pct'])) if sectors else None;conf_rounds={p['round_id'] for p in proof if p['decision']=='INFORMATION_CONFIRMED'};addrounds={t['round_id'] for t in orders if t['side']=='BUY_ADD'}
status=dict(result='PASS_INDEPENDENT_LEDGER_RECONSTRUCTION_NOT_EXTERNAL_AUDIT',days=len(ledger),orders=len(orders),last_day=ledger[-1]['day'],endpoints=endpoints,peak_OPEN_industry=maxopen,peak_CLOSE_industry=maxclose,confirmed_rounds=len(conf_rounds),actual_add_rounds=len(addrounds),confirmed_never_funded_ADD_rounds=len(conf_rounds-addrounds),donor_sales=len(summary),blockers=read(P/'BLOCKERS.json'),baseline_same_day_comparison_only=True,non_PIT=True,conditional_OPEN_cost_proxy=True);save(O/'ACCOUNT_QA_AND_SUMMARY.json',status)
save(O/'REPORT_OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='REPORT_OUTPUT_HASHES.json'})
print(json.dumps(status,ensure_ascii=False,default=str))
