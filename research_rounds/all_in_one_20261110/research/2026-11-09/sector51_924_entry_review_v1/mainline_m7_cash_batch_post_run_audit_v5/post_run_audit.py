from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,hashlib,importlib.util,sys
A=Path(__file__).resolve().parent;P=A.parent/'mainline_m7_cash_batch_design_v5';F=P/'once_20260630';checks=[];errors=[]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ok(n,v):
 checks.append(n)
 if not v:errors.append(n)
status=read(P/'RUN_STATUS.json');ledger=read(F/'DAY_LEDGER.json');orders=read(F/'ORDERS.json');holdings=read(F/'HOLDINGS.json');equity=read(F/'EQUITY_EVENTS.json')
for directory in [F,P/'checkpoint_20241106']:
 h=read(directory/'OUTPUT_HASHES.json');ok(str(directory.name)+'_inventory',set(h)=={p.name for p in directory.iterdir()}-{'OUTPUT_HASHES.json'})
 for n,x in h.items():ok(directory.name+'_sha_'+n,sha(directory/n)==x)
manifest=read(P.parent/'mainline_m7_november_boundary_design_v4/BASELINE_MANIFEST.json');base=P.parent/'mainline_m7_long_horizon_sealed_v2/once_20260630';prefix_counts={}
for n in manifest['comparison_families']:
 a=read(P/'checkpoint_20241106'/(n+'.json'));b=read(base/(n+'.json'));same=a==b
 if n=='AVAILABILITY_EVENTS':same=Counter(json.dumps(r,sort_keys=True) for r in a)==Counter(json.dumps(r,sort_keys=True) for r in b)
 ok('exact_Nov6_'+n,same);prefix_counts[n]=len(a) if hasattr(a,'__len__') else None
# Recompute account and per-security position from actual exported orders/equity.
cash=D(1200000);receivable=D(0);fees=D(0);qty=defaultdict(int)
for row in ledger:
 day=row['day']
 for o in orders:
  if o['day']!=day:continue
  n=D(o['notional']);fee=D(o['fee']);buy=o['side'].startswith('BUY')
  ok('order_notional_'+str(o['order_seq']),n==D(o['price'])*o['qty'])
  ok('order_cash_'+str(o['order_seq']),D(o['cash_delta'])==(-n-fee if buy else n-fee))
  cash+=D(o['cash_delta']);fees+=fee;qty[o['sid']]+=o['qty'] if buy else -o['qty']
 for ev in equity:
  if ev['day']==day:cash+=D(ev.get('cash_delta','0'));receivable+=D(ev.get('receivable_delta','0'))
 hs=[h for h in holdings if h['day']==day];mv=sum((D(h['market_value']) for h in hs),D(0));hqty=defaultdict(int)
 for h in hs:
  hqty[h['sid']]+=h['qty'];ok('holding_mark_'+day+'_'+h['lot_id'],D(h['market_value'])==D(h['raw_mark'])*h['qty'])
 ok('position_rollforward_'+day,{s:q for s,q in qty.items() if q}==dict(hqty))
 for key,actual in [('cash',cash),('receivable',receivable),('fees_paid',fees),('market_value',mv),('NAV',cash+receivable+mv)]:ok(key+'_'+day,D(row[key])==actual)
 ok('shares_'+day,row['shares']==sum(hqty.values()));ok('stocks_'+day,row['stocks']==len(hqty))
ok('status_matches_ledger',status['last']==ledger[-1] and len(ledger)==42 and len(orders)==1716 and ledger[-1]['day']=='2024-11-07')
# Check committed log day fields, not legitimate future order-plan dates or inventory metadata.
log_counts={}
for n in manifest['comparison_families']:
 if n in ['BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY']:continue
 rows=read(F/(n+'.json'))
 if isinstance(rows,list):
  dated=[r for r in rows if isinstance(r,dict) and 'day' in r];ok('no_uncertified_committed_day_'+n,all(r['day']<=ledger[-1]['day'] for r in dated));log_counts[n]=len(dated)
unc=read(F/'UNCERTIFIED_DAY.json');ok('blocked_preflight_no_partial_orders',unc==dict(day='2024-11-08',reason='2024-11-08 688016.SH UNADMITTED_EQUITY_EVENT',partial_orders=[]))
sid='688016.SH';pending=[r for r in read(F/'PENDING_AT_END.json') if r['sid']==sid];ticket=read(F/'TICKET_STATE.json').get(sid);scan=[r for r in read(F/'ALL_TARGETS_BLOCKER_SCAN.json') if r['sid']==sid]
ok('target_never_traded_or_held',not any(r['sid']==sid for r in orders+holdings));ok('new_seed_pending',len(pending)==1 and pending[0]['signal_day']=='2024-11-07' and pending[0]['kind']=='SEED' and pending[0]['econ_q']==200)
pause=read(F/'PAUSED_NEW_REQUESTS.json');logs=read(F/'EXECUTION_BOUNDARY_LOG.json');original=next(r for r in read(P/'checkpoint_20241106/PENDING_AT_END.json') if r['sid']=='002602.SZ')
ok('halt_original_identity_exact',pause['002602.SZ']['original']==original);ok('halt_still_paused',pause['002602.SZ']['status']=='PAUSED');ok('halt_no_trade',not any(r['sid']=='002602.SZ' for r in orders));ok('halt_log_only_committed',len(logs)==1 and logs[0]['day']=='2024-11-07' and logs[0]['event']=='REQUEST_PRESERVED_NO_CASH_RESERVATION')
new_eq=[r for r in equity if r['day']=='2024-11-07'];ok('newday_only_zero_entitlement_bridges',len(new_eq)==3 and all(r['event']=='FACTOR_BRIDGE' and r['record_qty']==0 and D(r['cash_delta'])==0 and D(r['receivable_delta'])==0 for r in new_eq))
ok('300760_cash_not_invented',any(r['sid']=='300760.SZ' for r in new_eq))
report=dict(verdict='PASS' if not errors else 'FAIL',scope='Export integrity, fixed November6 30-family prefix, Decimal daily cash/receivable/fees/positions/marked-NAV accounting and committed-day rollback evidence. No historical rerun, no independent market-price or fee-tariff certification.',checks=len(checks),errors=errors,days=len(ledger),orders=len(orders),last=ledger[-1],prefix_family_count=len(prefix_counts),prefix_families=prefix_counts,committed_day_counts=log_counts,uncertified_day=unc,target_pending=pending,target_previous_ticket=ticket,target_scan=scan,engine_sha256=sha(P/'engine.py'),contract_sha256=sha(P/'CONTRACT.md'),history_run=False,paused_state=pause,execution_boundary_log=logs,new_day_equity=new_eq,completed_horizon=status['completed_horizon'])
(A/'POST_RUN_INDEPENDENT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['verdict','checks','errors','days','orders','last']}))
assert not errors
