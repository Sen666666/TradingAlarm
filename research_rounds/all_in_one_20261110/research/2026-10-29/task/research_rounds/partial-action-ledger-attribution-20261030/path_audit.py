"""Recorded-role inventory and recovery funnel; no replay of decisions/trades."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import csv,json,gzip,time
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0);T0=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def csvrows(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def write(n,rs):
 if not rs:return
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rs for k in r)));w.writeheader();w.writerows(rs)
EP=[];ROLL=[];ROLE=[];TIMELINES=[];unknown=[];checks=[]
for sec,mode in [('TECH','I'),('DRUG','ACT')]:
 ar=RR/('pvr-local-finite-capital-20261029/baseline' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0')
 for stress in ['base','delay1']:
  root=W/'partial-action-full-account-20261030'/sec/'on' if stress=='base' else W/'partial-action-delay-repair-20261030'/sec/'full';aid=f'{mode}__B_S0_{stress}';obj=read(root/'accounts-v2'/f'{aid}.json');logs=obj['audit_log'];ds=[r for r in gz(root/'accounts-v2/daily.jsonl.gz') if r['account']==aid];dd={r['at'][:10]:r for r in ds};dsbyat={r['at']:r for r in ds};finalat=ds[-1]['at'];con={(r['date'],r['symbol']):r for r in csvrows(root/'analysis/contributions.csv') if r['account']==aid};names={r['symbol']:r['name'] for r in csvrows(root/'analysis/stocks.csv') if r['account']==aid};fills={r['receipt']['receipt_id']:r for r in logs if r['kind']=='fill'}
  pa={r['at']:r for r in logs if r['kind']=='partial_admission'};pi=defaultdict(list);act={r['at']:r for r in logs if r['kind']=='risk_checkpoint'}
  for r in logs:
   if r['kind']=='partial_input':pi[r['sid']].append(r)
  states={};reqs={};lastreq={};episodes={};wait={};fullreq=[];upgrades=[];livebuys={};rolepnl=defaultdict(D);rolefees=defaultdict(D);roleturn=defaultdict(D);counts=Counter();operations=[];lastphase={};monotone=0;role_day_checks=0;lastday=None
  def alloc(bucket,gross,fee,side):rolepnl[bucket]+=(gross if side=='sell' else -gross)-fee;rolefees[bucket]+=fee;roleturn[bucket]+=gross
  for idx,r in enumerate(logs):
   k=r['kind'];at=r.get('at');sid=r.get('sid');day=at[:10] if at else None
   if at and lastday and day!=lastday and lastday in dd:
    actual={s:z['K']+z['R'] for s,z in states.items() if z['K']+z['R']};assert actual==dd[lastday]['positions'],(sec,stress,lastday,'role day inventory');role_day_checks+=1
   if day:lastday=day
   if k=='reserve':
    livebuys[r['order_id']]=r
    if r['purpose']=='risk_restore':
     z=states[sid];assert r['target_shares']<=z['cap']-z['R'] and z['R']<z['cap'];counts['restore_target_cap_checks']+=1
     if sid in wait:wait[sid]['orders'].append(r['order_id'])
   elif k=='release_buy':livebuys.pop(r['order_id'],None)
   elif k=='exit_request':
    reqs[r['event_id']]=dict(r,cycle=states.get(sid,{}).get('cycle'),group=states.get(sid,{}).get('group'));lastreq[sid]=r['event_id']
   elif k in ['split','split_fraction_floor_proxy']:
    if sid in states:
     z=states[sid];ratio=D(r['ratio']);total=int(D(z['K']+z['R'])*ratio);kr=int(D(z['K'])*ratio);rr=int(D(z['R'])*ratio);z['K']=kr+total-kr-rr;z['R']=rr;z['cap']=int(D(z['cap'])*ratio);assert 0<=rr<=z['cap'];counts['actual_split_role_checks']+=1
   elif k=='partial_input':
    z=r['diagnostic'];p=z.get('protection_before');q=z.get('protection_after')
    if p is not None and q is not None:assert D(str(q))>=D(str(p));monotone+=1
    if not(r['price_known'] and r['event_known'] and r['source_unit_known']):unknown.append(dict(sector=sec,stress=stress,**r))
   elif k=='partial_event':
    e=r['detail'];kind=e['kind'];sid=e.get('sid');at=e.get('at');counts[kind]+=1
    if kind=='risk_trim_request':
     oid=lastreq[sid];assert not any(v['sid']==sid for v in livebuys.values()),'risk request retains pending buy';z=states[sid];ep=dict(sector=sec,stress=stress,symbol=sid,name=names.get(sid),order_id=oid,cycle=z['cycle'],group=z['group'],request_at=at,requested_shares=e['shares'],trim_fills=[],flat_at=None,restores=[],orders=[],applications=[],budget_checks=[],cycle_end=None);episodes[oid]=ep;operations.append(dict(at=at,sid=sid,kind=kind,cycle=z['cycle'],shares=e['shares']))
    elif kind=='upgrade_full_exit':upgrades.append(dict(at=at,sid=sid,cycle=states[sid]['cycle']))
    elif kind=='actual_role_buy':
     f=e['receipt'];z=states.get(sid)
     if z is None:z=dict(K=0,R=0,cap=0,cycle=f['receipt_id'],group=e['group'],risk_origin='risk_initial');states[sid]=z
     dk=e['K']-z['K'];dr=e['R']-z['R'];assert dk>=0 and dr>=0 and dk+dr==f['shares'];gross=D(f['gross_cny']);fee=D(f['fees_cny']);ck=gross*D(dk)/f['shares'];cf=fee*D(dk)/f['shares'];alloc('core',ck,cf,'buy');alloc('risk_restored' if e['action']=='risk_restore' else 'risk_initial',gross-ck,fee-cf,'buy')
     if e['action']=='risk_restore':
      assert dk==0;z['risk_origin']='risk_restored';assert sid in wait,'restore fill not connected to risk flat';wait[sid]['restores'].append(dict(receipt=f,order_id=fills[f['receipt_id']]['order_id']));reserve=next(t for t in logs if t['kind']=='reserve' and t['order_id']==fills[f['receipt_id']]['order_id']);assert reserve['candidate_id'].endswith('I='+reserve['decision_at'][:10]);assert reserve['decision_at']>wait[sid]['flat_at'];counts['restore_fresh_event_date_checks']+=1
     z.update(K=e['K'],R=e['R'],cap=e['cap']);assert z['K']+z['R']>=0 and z['R']<=z['cap'];operations.append(dict(at=at,sid=sid,kind=e['action'],cycle=z['cycle'],shares=f['shares'],gross=f['gross_cny'],fee=f['fees_cny']))
    elif kind=='actual_role_sell':
     f=e['receipt'];z=states[sid];dk=z['K']-e['K'];dr=z['R']-e['R'];assert dk>=0 and dr>=0 and dk+dr==f['shares'];gross=D(f['gross_cny']);fee=D(f['fees_cny']);ck=gross*D(dk)/f['shares'];cf=fee*D(dk)/f['shares'];alloc('core',ck,cf,'sell');alloc(z['risk_origin'],gross-ck,fee-cf,'sell');oid=fills[f['receipt_id']]['order_id']
     if e['action']=='risk_trim':
      assert dk==0;ep=episodes[oid];ep['trim_fills'].append(f)
      if e['R']==0:ep['flat_at']=at;wait[sid]=ep
     operations.append(dict(at=at,sid=sid,kind=e['action'],cycle=z['cycle'],shares=f['shares'],gross=f['gross_cny'],fee=f['fees_cny']));z.update(K=e['K'],R=e['R'])
     if z['K']+z['R']==0:
      for ep in episodes.values():
       if ep['cycle']==z['cycle']:ep['cycle_end']=at
      states.pop(sid);wait.pop(sid,None)
    elif kind=='restore_application':
     if sid in wait:wait[sid]['applications'].append(e)
    elif kind=='restore_budget_check':
     if sid in wait:wait[sid]['budget_checks'].append(e)
    elif kind=='role_dividend':
     z=states[sid];rolepnl['core']+=D(e['core']);rolepnl[z['risk_origin']]+=D(e['risk']);counts['dividend_role_checks']+=1
  if lastday in dd:assert {s:z['K']+z['R'] for s,z in states.items()}==dd[lastday]['positions'];role_day_checks+=1
  for sid,z in states.items():
   p=D(con[finalat[:10],sid]['market_value'])/D(z['K']+z['R']);rolepnl['core']+=D(z['K'])*p;rolepnl[z['risk_origin']]+=D(z['R'])*p
  bprofit=D(ds[-1]['nav'])-D(1000000);assert abs(sum(rolepnl.values(),Z)-bprofit)<D('1e-8'),(sec,stress,'role profit',sum(rolepnl.values(),Z),bprofit)
  for key in ['core','risk_initial','risk_restored']:ROLE.append(dict(sector=sec,stress=stress,bucket=key,actual_net_profit=rolepnl[key],actual_allocated_fees=rolefees[key],gross_turnover=roleturn[key],causal_increment=False))
  riskids=set(episodes);fullreq=[r for oid,r in reqs.items() if oid not in riskids]+upgrades;expiry={r['order_id']:r for r in logs if r['kind']=='buy_day_expiry'};opreject={r['order_id']:r['kind'] for r in logs if r['kind'] in ['open_support_reject','risk_open_reject']};reserve_by={r['order_id']:r for r in logs if r['kind']=='reserve'};reject_by=defaultdict(list)
  for r in pa.values():
   for s,reason in r['rejected']:reject_by[r['at'],s].append(reason)
  cat=Counter();partial_recovery=0
  for ep in episodes.values():
   sid=ep['symbol'];flat=ep['flat_at'];ends=[r['at'] for r in fullreq if r.get('cycle')==ep['cycle'] and (not flat or r['at']>=flat)];end=min(ends+[ep['cycle_end'] or finalat,finalat]);ep['window_end']=end;rr=ep['restores'];raw=[r for r in pi[sid] if flat and flat<r['at']<end];fresh=[r for r in raw if r['raw_i_buy']];bad=[r for r in raw if not(r['price_known'] and r['event_known'] and r['source_unit_known'])];ep['fresh_I_days']=len(fresh);ep['unknown_input_days']=len(bad);ep['actual_trim_shares']=sum(f['shares'] for f in ep['trim_fills']);ep['actual_trim_fee']=sum((D(f['fees_cny']) for f in ep['trim_fills']),Z);ep['actual_trim_net_cash']=sum((D(f['gross_cny'])-D(f['fees_cny']) for f in ep['trim_fills']),Z);ep['actual_restore_shares']=sum(r['receipt']['shares'] for r in rr);ep['actual_restore_buy_fee']=sum((D(r['receipt']['fees_cny']) for r in rr),Z);ep['actual_restore_gross']=sum((D(r['receipt']['gross_cny']) for r in rr),Z);ep['first_restore_at']=rr[0]['receipt']['at'] if rr else None
   if rr:category='restored';assert all(x['receipt']['at']<end or x['receipt']['at']==ep['cycle_end'] for x in rr)
   elif not flat:category='no_executed_trim' if not ep['trim_fills'] else 'risk_trim_not_flat_before_full_exit'
   elif ep['orders']:category='submitted_no_fill'
   elif ep['applications']:category='valid_application_no_order'
   elif fresh:
    known=[]
    for r in fresh:
     at=r['at'];a=pa.get(at);el=next((e for e in a['decisions'][-1]['eligibility'] if e['security_id']==sid),None) if a else None;known.append((act[at]['on'],el['q'] if el else None,at))
    if all(not x[0] for x in known):category='fresh_I_ACT_blocked'
    elif any(x[0] and x[1] is True for x in known):category='legal_I_Q_no_application_unknown'
    elif any(x[0] and x[1] is None for x in known):category='Q_unknown'
    else:category='fresh_I_Q_blocked'
   else:category='signal_history_unknown' if bad else 'no_fresh_I_before_exit_or_cutoff'
   reasons=[]
   for e in ep['budget_checks']:
    if e['reason']:reasons.append(e['reason'])
   for e in ep['applications']:reasons.extend(reject_by[e['at'],sid])
   execution_reasons=[]
   for oid in ep['orders']:
    if oid in opreject:execution_reasons.append(opreject[oid])
    elif oid in expiry:execution_reasons.append('day_expiry_'+('partial' if expiry[oid]['filled_shares'] else 'zero_fill'))
    elif not any(f['order_id']==oid for f in rr):execution_reasons.append('cancelled_or_pending_unknown')
   ep['classification']=category;ep['known_reject_reasons']='|'.join(sorted(set(reasons)));ep['execution_outcomes']='|'.join(sorted(set(execution_reasons)));cat[category]+=1
   out={k:v for k,v in ep.items() if k not in ['trim_fills','restores','budget_checks','applications','orders']};out.update(restore_fill_count=len(rr),restore_orders=len(ep['orders']),restore_applications=len(ep['applications']),first_trim_at=ep['trim_fills'][0]['at'] if ep['trim_fills'] else None,first_new_I=fresh[0]['at'] if fresh else None,all_order_ids='|'.join(ep['orders']));EP.append(out)
  for op in operations:TIMELINES.append(dict(sector=sec,stress=stress,**op))
  rec=dict(sector=sec,stress=stress,requests=len(episodes),requests_with_actual_trim=sum(bool(ep['trim_fills']) for ep in episodes.values()),risk_fully_empty=sum(bool(ep['flat_at']) for ep in episodes.values()),episodes_with_restore=sum(bool(ep['restores']) for ep in episodes.values()),restore_fills=sum(len(ep['restores']) for ep in episodes.values()),restore_buy_fees=sum((D(e['actual_restore_buy_fee']) for e in EP if e['sector']==sec and e['stress']==stress),Z),risk_trim_fees=sum((D(e['actual_trim_fee']) for e in EP if e['sector']==sec and e['stress']==stress),Z),categories=dict(cat),role_profit=rolepnl,bprofit=bprofit);ROLL.append(rec);checks.append(dict(sector=sec,stress=stress,role_inventory_days=role_day_checks,nondecreasing_protection_checks=monotone,restore_share_cap_checks=counts['restore_target_cap_checks'],fresh_event_date_checks=counts['restore_fresh_event_date_checks'],actual_split_checks=counts['actual_split_role_checks'],dividend_role_checks=counts['dividend_role_checks'],pending_buy_cancel_before_risk_request=True,role_funds_reconcile=True));print('RECOVERY',rec,flush=True)
write('RISK_TRIM_RECOVERY_EPISODES.csv',EP);write('ACTUAL_ROLE_PROFIT.csv',ROLE);write('RECORDED_TRANSACTION_TIMELINES.csv',TIMELINES);save('RECOVERY_SUMMARY.json',ROLL);save('RECORDED_EXECUTION_CHECKS.json',checks);save('INPUT_UNKNOWNS.json',unknown);save('PATH_AUDIT_TIME.json',dict(seconds=time.monotonic()-T0,no_account_or_signal_executed=True))
