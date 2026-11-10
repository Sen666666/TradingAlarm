"""Independent saved-JSON arithmetic only; no strategy/model/account imports."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import bisect,gzip,hashlib,json,time

O=Path(__file__).resolve().parent;C=O.parent
T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
R={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',
   'strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
Z=D(0);EPS=D('.0000001');SOURCES={}
def read(p):
 p=Path(p);SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if p.name.endswith('.gz'):
  with gzip.open(p,'rt')as f:return json.load(f)
 return json.loads(p.read_text())
def lines(p):
 p=Path(p);SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with gzip.open(p,'rt')as f:
  for l in f:yield json.loads(l)
def day(t):return str(t)[:10]
def eff(vs,d):
 xs=[x for x in vs if x['from']<=d and (x.get('to')is None or d<x['to'])]
 assert len(xs)==1;return xs[0]
def fee(q,p,par,cs,side='buy'):
 # New order only, so paid/accrued are both zero. No native fee function used.
 out=Z
 for c in cs:
  if c.get('side','both')not in('both',side):continue
  basis=c.get('amount_basis','notional')
  base=q*p if basis=='notional'else D(q)if basis=='shares'else D(q)*par
  x=max(D(c.get('minimum_local','0')),base*D(c['rate']))
  if c.get('maximum_local')is not None:x=min(x,D(c['maximum_local']))
  if c.get('rounding_unit')is not None:
   u=D(c['rounding_unit']);x=(x/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  out+=x
 return out
def eq(a,b):
 v=abs(D(str(a))-D(str(b)));assert v<EPS,(a,b,v);return v

def main():
 start=time.monotonic();rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 sums=read(C/'FULL_CASH_NECESSARY_BOUNDS_SUMMARY.json');expected={};result={};rawfees={}
 for label,root in R.items():
  b=read(root/'B.json.gz');daily=list(lines(root/'daily.jsonl.gz'));dd={day(x['at']):x for x in daily}
  funding=[x for x in lines(root/'funding.jsonl.gz')if'09:30:00'in x['at']]
  assert len({(x['at'],x['sid'],x['role'])for x in funding})==len(funding)
  assert all(D(x[k])==0 for x in daily for k in ['order_reserved','settlement_locked','payable','sale_receivable'])
  bytrade=defaultdict(list);buy=defaultdict(lambda:Z);buyq=defaultdict(int);first={}
  for t in b['trades']:
   assert'09:30:00'in t['at'];d=day(t['at']);bytrade[d].append(t)
   if t['side']=='buy':buy[d]+=D(t['gross_cny'])+D(t['fees_cny']);buyq[d,t['security_id']]+=t['shares'];first.setdefault(t['security_id'],d)
  cash=D('1000000');maxdelta=Z;s0={}
  for d,x in sorted(dd.items()):
   for t in bytrade[d]:cash+=D(t['gross_cny'])-D(t['fees_cny'])if t['side']=='sell'else-D(t['gross_cny'])-D(t['fees_cny'])
   maxdelta=max(maxdelta,eq(cash,x['available']));s0[d]=D(x['available'])+buy[d]
  eq(cash,b['ending_cash'])
  reserve={};ri=defaultdict(list);bi=defaultdict(list);releases={};relidx=defaultdict(list);settle={};types=Counter()
  for n,a in enumerate(b['audit']):
   types[a['kind']]+=1;k=a['kind']
   if k=='reserve':
    d=day(a['at']);key=(d,a['sid']);assert key not in reserve;reserve[key]=a;ri[d].append(n)
   if k=='fill'and a['receipt']['side']=='buy':bi[day(a['receipt']['at'])].append(n)
   if k=='release_buy':releases[a['order_id']]=a;relidx[day(a['at'])].append(n)
   if k=='settle':
    s=a['settlement'];assert D(s['fx_rate'])==1 and s['due_at']==a['at'];settle[s['settlement_id']]=(n,a)
  assert {x['order_id']for x in reserve.values()}==set(releases)
  for d,ii in ri.items():
   if bi[d]:assert max(ii)<min(bi[d])
   # Both same-OPEN cancellation and post-OPEN expiry occur after all reservations.
   if relidx[d]:assert max(ii)<min(relidx[d])
  for t in b['trades']:
   if t['side']=='sell':
    n,a=settle[t['settlement_id']];assert a['at']==t['at']and not a['settlement']['debit']
    eq(a['settlement']['cny_amount'],D(t['gross_cny'])-D(t['fees_cny']))
    if ri[day(t['at'])]:assert n<min(ri[day(t['at'])])
  assert all('15:10:00'in a['at']for a in b['journal']if a['kind']=='cancel_ack')
  assert types==Counter(sums[label]['audit_types'])
  permitted_types={'fill','settle','reserve','lot_risk_funded','release_buy','pilot_layer_exit','exit_request','risk_checkpoint','dividend_accrual','buy_day_expiry','split'}
  assert not set(types)-permitted_types
  dec={day(x['at']):x for x in b['decisions']};ds=sorted(dec);intents={d:{(i['sid'],i['role']):i for i in x['intents']}for d,x in dec.items()}
  pref=defaultdict(lambda:Z);reskeys=[];rkeys=[];expectedrole=Counter()
  for f in funding:
   d=day(f['at']);sid=f['sid'];role=f['role'];sig=ds[bisect.bisect_left(ds,d)-1]
   i=intents[sig][sid,role];A=s0[d]-pref[d];assert A>=-EPS
   if f['result']=='reserved':
    a=reserve[d,sid];assert day(a['decision_at'])==sig and a['target_shares']==f['shares']
    pref[d]+=D(a['gross_budget_cny'])+D(a['fee_reserved_cny']);reskeys.append((d,sid));continue
   if'cash_or_original_reserve'not in f['result']:continue
   key=(label,d,sid,role);assert key not in expected
   held=int(dd[d]['positions'].get(sid,0))-buyq[d,sid];assert held>=0
   kind='existing_hold_ADD'if held else'flat_reentry'if sid in first and first[sid]<d else'first_participation'
   expected[key]=dict(A=A,S0=s0[d],prefix=pref[d],nav=D(dec[sig]['nav']),signal=sig,raw=f['result'],held=held,kind=kind,on=dec[sig]['on'],i=i)
   expectedrole[role]+=1;rkeys.append(key)
  assert reskeys==[(day(a['at']),a['sid'])for a in b['audit']if a['kind']=='reserve']
  assert len(rkeys)==sums[label]['cash_rejected']['all']['events']
  result[label]=dict(original_days=len(daily),source_OPEN_rows=len(funding),cash_reject_rows=len(rkeys),all_cash_bridge_max_abs_residual=str(maxdelta),reserve_order_verified=len(reskeys),settlement_identity_and_order_verified=True,by_role=dict(expectedrole))
  del b,daily,funding
 actual=Counter();fee_keys=set();counts=defaultdict(Counter);unique=defaultdict(set);maxcosterr=Z;maxAerr=Z
 for row in lines(C/'ALL_ORIGINAL_CASH_REJECTS.jsonl.gz'):
  k=(row['window'],row['OPEN'],row['sid'],row['role']);e=expected.pop(k);w,d,sid,role=k
  maxAerr=max(maxAerr,eq(row['available_already_net_of_orders'],e['A']))
  for field,value in [('S0_available',e['S0']),('prior_real_submitted_reserve',e['prefix']),('original_decision_NAV',e['nav'])]:eq(row[field],value)
  assert row['signal_day']==e['signal']and row['original_raw_merged_reasons']==e['raw']
  assert row['held_quantity_before_fresh']==e['held']and row['entry_kind']==e['kind']and row['ACT_on']==e['on']
  assert row['known_extra_unreserved_liability_U']==0
  q=eff(rules['quantity_versions'][sid],d)['rule']['buy_minimum'];assert q==row['minimum_quantity']
  venue=eff(rules['venue_versions'][sid],d)['venue'];fs=eff(rules['fee_versions'][venue],d)['schedule'];par=D(rules['security_metadata'][sid]['par_value'])
  p=D(row['known_OPEN_buy_price']);independent_fee=fee(q,p,par,fs['components']);eq(independent_fee,row['minimum_buy_fee'])
  cost=D(q)*p+independent_fee;maxcosterr=max(maxcosterr,eq(cost,row['minimum_cash_required']));eq(q*p,row['minimum_gross'])
  cap=e['i']['cap'];budget=D(e['i']['budget']);assert q<=cap and D(q)*p<=budget
  Rbuf=e['nav']*D('.1');eq(Rbuf,row['original_extra10_buffer']);assert cost>e['A']-Rbuf-EPS
  physical=cost<=e['A']+EPS;assert row['physical_cash_can_afford_minimum']==physical
  eq(row['max_extra_buffer_cash_stock'],min(e['A'],Rbuf));eq(row['required_release_to_afford_minimum'],max(Z,cost-(e['A']-Rbuf)))
  eligible=e['on']and row['original_industry_stage']in['confirmed','expanded'];assert row['original_permission_eligible']==eligible
  fg,fi=row['F1_global_permit'],row['F1_industry_permit'];assert type(fg)in(bool,type(None))and type(fi)in(bool,type(None))
  joint=fg and fi if fg is not None and fi is not None else None;assert row['F1_joint_permit']==joint
  for rolekey in ['all',role]:
   a=counts[w,rolekey];a['events']+=1;a['physical']+=physical;a['eligible']+=eligible;a['joint']+=eligible and joint is True;a['cash_only']+=e['raw']=='cash_or_original_reserve'and physical
  actual[w]+=1;unique[w].add((d,sid));fee_keys.add((venue,fs['schedule_id'],q))
 assert not expected
 for (w,r),a in counts.items():
  want=sums[w]['cash_rejected'][r]
  for key,skey in [('events','events'),('physical','physical_cash_can_afford_min'),('eligible','actual_permission_eligible'),('joint','eligible_F1_joint'),('cash_only','raw_cash_only_physical_min')]:assert a[key]==want[skey],(w,r,key,a[key],want[skey])
 result.update(status='PASS_FULL_CASH_ALGEBRA_AND_STATIC_ENDPOINT_ADMISSION',all_saved_rows_independently_rejoined=sum(actual.values()),rows_by_window=dict(actual),unique_stock_OPEN_by_window={k:len(v)for k,v in unique.items()},all_saved_minimum_fees_recomputed_without_native_fee_function=True,dated_venue_schedule_minimum_combinations=sorted(fee_keys),max_abs_available_residual=str(maxAerr),max_abs_cost_residual=str(maxcosterr),no_counterfactual_fills_or_profits=True,source_files=len(SOURCES),seconds=time.monotonic()-start)
 (O/'FULL_CASH_BOUNDS_RESULT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 (O/'FULL_CASH_BOUNDS_AUDIT_SOURCES.json').write_text(json.dumps(SOURCES,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
