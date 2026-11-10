"""All frozen P events joined once to original No60 facts/actual account logs.
No Account/Runner, new order, reserve projection, or new economic path.
"""
from pathlib import Path
from collections import defaultdict,Counter
from types import SimpleNamespace,MethodType
from datetime import datetime
from decimal import Decimal as D
from bisect import bisect_right
import gzip,hashlib,json,sys,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent;WORK=ROOT.parent
sys.path.insert(0,str(WORK/'new_price_trend_v1/funding'))
import entry_adapter as E
J,LR=E.J,E.J.LR
F=J.M.E.FastMarket.__mro__[1];native=sys.modules[F.__module__]
SOURCES={};VIEWS={};OPEN_MARKS={}
def bind(p):
 p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def lines(p):
 with gzip.open(bind(p),'rt')as f:
  for x in f:yield json.loads(x)
def save(n,x):
 (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def num(v):return D(str(v))
def truth(v):return None if pd.isna(v)else bool(v)
def effective(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))

def main():
 started=time.monotonic();bind(__file__);events=read(ROOT/'P_EVENTS.json');assert len(events)==35699
 rules=read(J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
 protocol=read(J.BP.C.OLD/'inputs-v2/economic-protocol.json')
 records={r['series_id']:r for r in read(J.M.P/'manifest.json')['series']}
 sm={r['symbol']:r for r in read(E.L.U/'STOCK_MANIFEST.json')}
 meta=read(J.M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
 sessions={k:tuple(datetime.fromisoformat(x)for x in vs)for k,vs in rules['calendars'].items()}
 opens=list(sessions['A']);cash={(x['window'],x['OPEN']):x for x in read(WORK/'cash_release_v1/ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json')}
 assert read(WORK/'cash_release_v1/LEDGER_RECONSTRUCTION_AUDIT.json')['no_existing_reserved_settlement_payable_sale_AR_at_any_original_CLOSE']
 exact_s0={k[:10]:v['state']for k,v in read(WORK/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json').items()}
 bywindow=defaultdict(list)
 for p in events:bywindow[p['window']].append(p)
 books={};daily={};ops={};cp=defaultdict(list);buys=defaultdict(lambda:defaultdict(lambda:D(0)));core=defaultdict(list);daydiv={};competitors={}
 for w in ['long','strong']:
  root=WORK/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair'
  with gzip.open(bind(root/'B.json.gz'),'rt')as f:b=json.load(f)
  books[w]=b;daily[w]={r['at'][:10]:r for r in lines(root/'daily.jsonl.gz')}
  wanted={(p['day'],p['sid'])for p in bywindow[w]};ops[w]={}
  for r in lines(root/'opportunities.jsonl.gz'):
   if (r['day'],r['sid'])in wanted:ops[w][r['day'],r['sid']]=r
   if r['CP1_id']:cp[w,r['sid']].append((r['day'],r['CP1_id'],r['mobile_Q']))
  jfills={int(x['layer']):x for x in b['journal']if x['kind']=='real_buy_fill'}
  for t in b['trades']:
   if t['side']!='buy':continue
   sid=t['security_id'];day=t['at'][:10];buys[w,day][sid]+=num(t['shares'])
   j=jfills[int(t['layer'])];assert j['sid']==sid and num(j['shares'])==num(t['shares'])
   if j['role']=='core':
    assert t['kind']=='core' and t['epoch']is not None
    core[w,sid].append((datetime.fromisoformat(t['at']),tuple(t['epoch']),t['signal_at'][:10],int(t['layer'])))
  accrued=sorted((datetime.fromisoformat(x['receivable']['ex_at']),num(x['receivable']['net_local']))for x in b['audit']if x['kind']=='dividend_accrual')
  acc=D(0);pos=0;daydiv[w]={}
  for at in opens:
   while pos<len(accrued)and accrued[pos][0]<=at:acc+=accrued[pos][1];pos+=1
   daydiv[w][at.date().isoformat()]=acc
  for r in lines(root/'funding.jsonl.gz'):
   if r['result']=='reserved':competitors.setdefault(w+'|'+r['at'][:10],[]).append(r)
  assert len(ops[w])==len(wanted)

 def view(sid):
  if sid not in VIEWS:
   rec=records[sid];path=native.checked_ref(rec['raw'],J.M.P);bind(path)
   f=native.read_raw(path,rec);f['valid_price']=f.index.isin(native.eligible_prices(f).index);f['observed_bar']=native.boolean_column(f,'observed_bar',True)
   actions,_=native.read_actions(rec,J.M.P);bind(rec['adjustment']['actions']['path'])
   x=SimpleNamespace(raw={sid:f},bundle=SimpleNamespace(series={sid:SimpleNamespace(record=rec)}),lines={sid:SimpleNamespace(market='A')},sessions=sessions,actions={sid:actions},protocol=protocol)
   x.source_available=MethodType(F.source_available,x);x.rate=MethodType(F.rate,x);VIEWS[sid]=x
  return VIEWS[sid]
 def openmark(sid,day):
  key=sid,day
  if key not in OPEN_MARKS:OPEN_MARKS[key]=F.latest_mark(view(sid),sid,datetime.fromisoformat(day+'T09:30:00+08:00')).cny_price(datetime.fromisoformat(day+'T09:30:00+08:00'))
  return OPEN_MARKS[key]
 # Actual S0 quantities: saved same-day CLOSE quantities minus all actual OPEN
 # buy fills. Native source only mutates stock units at 00:00 actions and OPEN
 # fills, so all original protection sales/actions are already included.
 s0={};s0checks=[]
 for (w,day),c in cash.items():
  assert c['prior_existing_submitted_order_reserve']==0
  r=daily[w][day];q={s:num(v)-buys[w,day].get(s,D(0))for s,v in r['positions'].items()}
  assert all(v>=0 for v in q.values());q={s:v for s,v in q.items()if v}
  caps=defaultdict(lambda:D(0));total=D(0)
  for sid,qty in q.items():v=qty*openmark(sid,day);caps[meta[sid]['sector_id']]+=v;total+=v
  upper=num(c['S0_available'])+total+daydiv[w][day]
  s0[w,day]=dict(quantities=q,sector_capital=dict(caps),inventory=total,NAV_upper=upper,cash=c)
  if w=='strong'and day in exact_s0:
   z=exact_s0[day];knownq=defaultdict(lambda:D(0))
   for lot in z['lots']:knownq[lot['stock']]+=num(lot['qty'])
   assert dict(knownq)==q,(day,'S0 stock units mismatch')
   knowncap=sum((num(l['qty'])*num(z['prices'][l['stock']])for l in z['lots']),D(0))
   assert abs(knowncap-total)<D('.000001')and upper+ D('.000001')>=num(z['nav'])
   s0checks.append(dict(day=day,units_exact=True,capital_difference=str(total-knowncap),NAV_upper_above_exact=str(upper-num(z['nav']))))
 assert len(s0checks)==13

 result=[];facts={};epoch_checks=0;rulecache={};groups=defaultdict(Counter)
 def rules_at(sid,day):
  q=effective(rules['quantity_versions'][sid],day)['rule'];venue=effective(rules['venue_versions'][sid],day)['venue'];z=effective(rules['fee_versions'][venue],day)['schedule'];key=sid,json.dumps(q,sort_keys=True),z['schedule_id']
  if key not in rulecache:rulecache[key]=(LR.L.QuantityRule(**q),LR.L.FeeSchedule(z['schedule_id'],tuple(LR.L.FeeComponent(**c)for c in z['components'])))
  return rulecache[key]
 for sid,pe in __import__('itertools').groupby(sorted(events,key=lambda x:x['sid']),lambda x:x['sid']):
  path=bind(sm[sid]['refs']['facts']);assert SOURCES[str(path.resolve())]==sm[sid]['output_sha256'][str(path)]
  f=pd.read_parquet(path);warm=f.g_ready.eq(True)&f.g_grade.ge(2);fresh=f.g_fresh_up.eq(True);unknown=f[['g_ready','g_grade','g_fresh_up']].isna().any(axis=1)
  cw=(warm&fresh).cumsum().to_numpy();cu=unknown.cumsum().to_numpy();epochs={}
  for w in bywindow:
   prior=None;n=0;ed={}
   for day in daily[w]:
    ix=f.index.searchsorted(pd.Timestamp(day),side='right')-1
    key=(False,-1)if ix<0 else(bool(f.i_target.iloc[ix]),int(f.segment_id.iloc[ix]))
    if key!=prior:n+=1;prior=key
    ed[day]=(key[1],n)
   epochs[w]=ed
   for _,ep,signal,layer in core[w,sid]:assert ed[signal]==ep,(w,sid,signal,ep,ed[signal]);epoch_checks+=1
  for p in pe:
   w,day=p['window'],p['day'];r=daily[w][day];op=ops[w][day,sid];z=f.loc[day];i=f.index.get_loc(day);start=f.index.searchsorted(pd.Timestamp(p['e0_run_start']))
   at=datetime.fromisoformat(r['at']);oldcore=next((x for x in reversed(core[w,sid])if x[0]<=at),None);locked=oldcore is not None and oldcore[1]==epochs[w][day]
   assert bool(op['held'])==bool(r['positions'].get(sid,0))
   gr,gg,gf=truth(z.g_ready),None if pd.isna(z.g_grade)else float(z.g_grade),truth(z.g_fresh_up)
   gtag='G1_unknown'if gr is None or gg is None or gf is None else'G1_not_ready'if not gr else'G1_ready_below_warm'if gg<2 else'G1_warm_no_fresh'if not gf else'G1_warm_fresh'
   prior_count=int(cw[i]-(cw[start-1]if start else 0));unknown_count=int(cu[i]-(cu[start-1]if start else 0))
   cps=cp[w,sid];j=bisect_right([x[0]for x in cps],day);nextcp=cps[j]if j<len(cps)else None
   nextat=opens[bisect_right(opens,at)];od=nextat.date().isoformat();s=s0.get((w,od));nav=num(r['nav']);pending=[x for x in op['barriers']if x in ['exit_pending','buy_pending']]
   cohort=p['state']=='B_I_on_no_i_buy'and not op['held']and r['on']and not pending and not locked and op['mobile_Q']is True
   x=dict(window=w,sid=sid,day=day,state=p['state'],e0_run_start=p['e0_run_start'],sector=op['sector'],original_held=op['held'],original_quantity=r['positions'].get(sid,0),ACT_on=r['on'],original_barriers=op['barriers'],original_pending_barriers=pending,original_continuing_S0_Q=op['mobile_Q'],native_current_epoch=epochs[w][day],last_actual_CORE_fill=dict(at=str(oldcore[0]),epoch=oldcore[1],layer=oldcore[3])if oldcore else None,actual_CORE_epoch_consumed=locked,B_flat_ACT_S0_epoch_pending_intersection=cohort,
    original_CP_same_day=op['CP1_id'],next_original_CP=dict(day=nextcp[0],receipt=nextcp[1],original_continuing_Q=nextcp[2],same_native_I_epoch=epochs[w].get(nextcp[0])==epochs[w][day],natural_days=(pd.Timestamp(nextcp[0])-pd.Timestamp(day)).days)if nextcp else None,
    G1=dict(ready=gr,grade=gg,fresh_up=gf,current_category=gtag,warm_fresh_observations_since_E0_start=prior_count,unknown_G1_observations_since_E0_start=unknown_count,E0_start_warm=bool(warm.iloc[start]),original_I_target=truth(z.i_target),original_i_buy=truth(z.i_buy)),
    next_OPEN=od if s else None,additional_A_authorization_required=p['state'].startswith('A'),all_OPEN_risk_and_admission='UNKNOWN_NOT_PROJECTED',original_decision_intents=len(books[w]['decisions'][list(daily[w]).index(day)]['intents']))
   if s:
    sc=s['sector_capital'].get(op['sector'],D(0));x['original_S0']=dict(cash=s['cash']['S0_available'],decision_NAV=s['cash']['decision_NAV'],actual_sector_inventory_capital=str(sc),actual_inventory=str(s['inventory']),optimistic_NAV_upper=str(s['NAV_upper']),NAV_upper_definition='actual S0 cash+actual S0 inventory+all original net dividends accrued so far without deducting payments',sector_capital_already_exceeds_2pct_NAV_upper=sc>D('.02')*s['NAV_upper'],scope='before all original new admissions; same cash not independently reusable across P events')
   size=None
   if p['state']=='B_I_on_no_i_buy':
    if pd.notna(z.i_floor)and pd.notna(z.factor)and z.factor>0 and z.i_floor>0 and z.i_floor<z.close:
     qr,fees=rules_at(sid,day);q=qr.buy_minimum;raw=num(z.raw_close);floor=num(z.i_floor)/num(z.factor);ref=raw*(D(1)+LR.SLIP);par=num(rules['security_metadata'][sid]['par_value'])
     risk=LR.protection_risk(q,ref,floor,fees,par);ok=risk<=nav*D('.0025')and D(q)*ref<=nav*D('.02')
     size=dict(signal_minimum=q,signal_minimum_risk=str(risk),risk_budget=str(nav*D('.0025')),signal_minimum_gross=str(D(q)*ref),nominal_cap=str(nav*D('.02')),signal_minimum_risk_and_2pct_cap_pass=ok,scope='exact minimum-unit necessary test, not full frozen cap/budget or an order')
     if s:
      rawframe=view(sid).raw[sid];dt=pd.Timestamp(od)
      if dt in rawframe.index and np.isfinite(rawframe.loc[dt,'open'])and rawframe.loc[dt,'open']>0:
       rule,fee=rules_at(sid,od);oq=rule.buy_minimum;px=num(rawframe.loc[dt,'open'])*(D(1)+LR.SLIP);ii=f.index.searchsorted(dt,side='right')-1;fl=num(z.i_floor)/num(f.factor.iloc[ii]);cost=D(oq)*px+LR.fees(oq,px,fee,'buy',par);rr=LR.protection_risk(oq,px,fl,fee,par)
       opass=px/(D(1)+LR.SLIP)>fl and rr<=nav*D('.0025')and D(oq)*px<=nav*D('.02')
       available=num(s['cash']['S0_available']);free=available-nav*D('.1');sc=s['sector_capital'].get(op['sector'],D(0));sectorfail=sc+D(oq)*px>D('.02')*s['NAV_upper']
       size.update(OPEN_minimum=oq,OPEN_minimum_gross=str(D(oq)*px),OPEN_minimum_buy_fee=str(cost-D(oq)*px),OPEN_minimum_protection_risk=str(rr),OPEN_minimum_risk_and_2pct_necessary_pass=opass,original_S0_cash_after_cash10=str(free),isolated_original_S0_cash_can_pay_minimum=cost<=free,certified_sector_capital_failure_even_optimistic_NAV=sectorfail,full_original_frozen_max_and_OPEN_risk_unknown=True)
    else:size=dict(signal_minimum_risk_and_2pct_cap_pass=False,reason='original_I_floor_or_factor_invalid')
   x['B_minimum_unit_necessary_only']=size;result.append(x)
   c=groups[w+'|'+p['state']];c['events']+=1;c[gtag]+=1;c['original_held']+=bool(op['held']);c['ACT_on']+=bool(r['on']);c['CORE_epoch_consumed']+=locked;c['CP_same_day']+=op['CP1_id']is not None;c['B_flat_ACT_S0_epoch_pending_intersection']+=cohort
   if cohort:
    c['intersection_CP_same_day']+=op['CP1_id']is not None;c['intersection_no_same_CP']+=op['CP1_id']is None
    c['intersection_next_CP_same_I_epoch']+=nextcp is not None and epochs[w].get(nextcp[0])==epochs[w][day]
    if size:
     c['intersection_signal_minimum_pass']+=bool(size.get('signal_minimum_risk_and_2pct_cap_pass'))
     c['intersection_OPEN_minimum_necessary_pass']+=bool(size.get('OPEN_minimum_risk_and_2pct_necessary_pass'))
     c['intersection_isolated_S0_cash_minimum_pass']+=bool(size.get('isolated_original_S0_cash_can_pay_minimum'))
     c['intersection_certified_sector_capital_failure']+=bool(size.get('certified_sector_capital_failure_even_optimistic_NAV'))
 assert len(result)==len(events)
 with gzip.open(O/'P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz','wt')as out:
  for x in result:out.write(json.dumps(x,ensure_ascii=False,default=str,allow_nan=False)+'\n')
 save('ORIGINAL_OPEN_RESERVED_COMPETITORS.json',competitors)
 save('P_ORIGINAL_RESOURCE_SUMMARY.json',dict(events=len(result),groups={k:dict(v)for k,v in groups.items()},exact_S0_13_checks=s0checks,original_CORE_fill_epoch_identity_checks=epoch_checks,S0_quantity_method='saved same-CLOSE quantities minus actual same-OPEN buys; original actions/protection exits retained',sector_failure_scope='certified lower-bound obstruction against optimistic NAV upper, not all native gates or final permission',seconds=time.monotonic()-started,new_accounts=0,new_orders=0,new_reserve_projections=0))
 save('P_RESOURCE_SOURCE_SHA256.json',SOURCES)
 print(json.dumps(dict(events=len(result),seconds=time.monotonic()-started,CORE_epoch_checks=epoch_checks,groups={k:dict(v)for k,v in groups.items()}),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
