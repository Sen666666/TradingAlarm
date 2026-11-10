from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,hashlib,importlib.util,sys
A=Path(__file__).resolve().parent;P=A.parent/'mainline_m7_cash_batch_design_v6';F=P/'once_20260630';checks=[];errors=[]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ok(n,v):
 checks.append(n)
 if not v:errors.append(n)
status=read(P/'RUN_STATUS.json');ledger=read(F/'DAY_LEDGER.json');orders=read(F/'ORDERS.json');holdings=read(F/'HOLDINGS.json');equity=read(F/'EQUITY_EVENTS.json')
for directory in [F,P/'checkpoint_20241106',P/'checkpoint_20241107']:
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
ok('status_matches_ledger',status['last']==ledger[-1] and len(ledger)==status['days'] and len(orders)==status['orders'])
# Check committed log day fields, not legitimate future order-plan dates or inventory metadata.
log_counts={}
for n in manifest['comparison_families']:
 if n in ['BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY']:continue
 rows=read(F/(n+'.json'))
 if isinstance(rows,list):
  dated=[r for r in rows if isinstance(r,dict) and 'day' in r];ok('no_uncertified_committed_day_'+n,all(r['day']<=ledger[-1]['day'] for r in dated));log_counts[n]=len(dated)

m7=read(P/'CERTIFIED_NOV7_MANIFEST.json');base7=P.parent/'mainline_m7_cash_batch_design_v5/once_20260630';cp=P/'checkpoint_20241107'
ok('Nov7_exact_family_set',{p.stem for p in cp.glob('*.json')}==set(m7['required_json_families']))
for n in m7['comparison_families']:
 a=read(cp/(n+'.json'));b=read(base7/(n+'.json'));same=a==b
 if n=='AVAILABILITY_EVENTS':same=Counter(json.dumps(r,sort_keys=True) for r in a)==Counter(json.dumps(r,sort_keys=True) for r in b)
 ok('exact_Nov7_'+n,same)
for n,h in m7['files'].items():ok('sealed_v5_'+n,sha(base7/n)==h)
unc=read(F/'UNCERTIFIED_DAY.json');last=ledger[-1]['day']
if unc:
 ok('blocked_day_after_last',unc['day']>last);ok('blocked_no_partial_orders',not unc['partial_orders'])
scan=read(F/'ALL_TARGETS_BLOCKER_SCAN.json');pending=read(F/'PENDING_AT_END.json');tickets=read(F/'TICKET_STATE.json')
pause=read(F/'PAUSED_NEW_REQUESTS.json');logs=read(F/'EXECUTION_BOUNDARY_LOG.json');original=next(r for r in read(P/'checkpoint_20241106/PENDING_AT_END.json') if r['sid']=='002602.SZ')
ok('halt_original_identity_exact',pause['002602.SZ']['original']==original);ok('boundary_logs_committed_only',all(r['day']<=last for r in logs));ok('no_halt_day_trade',not any(r['sid']=='002602.SZ' and r['day']=='2024-11-07' for r in orders))
# Independently derive exact batch NET80 entitlement from exported record-date holdings.
cash_event_results=[]
for ev in read(P/'EXACT_CASH_BATCH_MANIFEST.json')['events']:
 sid=ev['sid'];ex=ev['ex_date'];record=ev['record_date'];pay=ev['pay_date']
 if ex>last:continue
 q=sum(h['qty'] for h in holdings if h['sid']==sid and h['day']==record);expected=D(q)*D(ev['d_cash'])*D('.8')
 accr=[r for r in equity if r['sid']==sid and r['day']==ex and r['event']=='ACCRUE_NET80'];paid=[r for r in equity if r['sid']==sid and r['day']==pay and r['event']=='PAY_CLOSE_NET80']
 ok('exact_cash_accrual_'+sid+'_'+ex,sum((D(r['receivable_delta']) for r in accr),D(0))==expected)
 ok('record_quantity_'+sid+'_'+ex,sum(r['record_qty'] for r in accr)==q)
 if pay<=last:ok('exact_cash_payment_'+sid+'_'+ex,sum((D(r['cash_delta']) for r in paid),D(0))==expected)
 if not q:ok('no_Q0_claim_'+sid+'_'+ex,not accr and not paid)
 cash_event_results.append(dict(sid=sid,ex_date=ex,record_date=record,record_qty=q,d_source=ev['d_source'],d_cash=ev['d_cash'],d_ref=ev['d_ref'],NET80=str(expected),accruals=accr,payments=paid))
report=dict(verdict='PASS' if not errors else 'FAIL',scope='Independent export integrity, complete Nov6/Nov7 economic/state prefixes, Decimal accounting, exact batch official-cash NET80 entitlements and committed-day rollback evidence. No historical run; no external quote or fee-tariff certification.',checks=len(checks),errors=errors,days=len(ledger),orders=len(orders),last=ledger[-1],nov6_families=len(prefix_counts),nov7_families=len(m7['comparison_families']),uncertified_day=unc,target_scan=scan,engine_sha256=sha(P/'engine.py'),contract_sha256=sha(P/'CONTRACT.md'),history_run=False,paused_state=pause,execution_boundary_log=logs,cash_event_results=cash_event_results,completed_horizon=status['completed_horizon'])
(A/'POST_RUN_INDEPENDENT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['verdict','checks','errors','days','orders','last']}));assert not errors
