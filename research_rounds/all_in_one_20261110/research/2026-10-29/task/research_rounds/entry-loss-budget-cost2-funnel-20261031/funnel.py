"""Read-only actual-account post-budget-exit funnel. No strategy replay."""
from pathlib import Path
import sys,json,gzip,time,collections
from decimal import Decimal as D,ROUND_FLOOR
from datetime import datetime
import pandas as pd
OLD=Path(__file__).resolve().parent.parent/'entry-loss-budget-full-account-20261031'
sys.path.insert(0,str(OLD));import wire as w
O=Path(__file__).resolve().parent;Z=D(0)
def dt(x):return datetime.fromisoformat(str(x))
def save(p,x):w.K.save(p,x)
def export(p,x):w.K.export(p,x)
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

def main(sec):
 start=time.monotonic();root=OLD/sec/'on';prep=Path(w.read(w.RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path']) if sec=='TECH' else w.RR/'innovative-drug-sfw3-20261028/prepared'
 # Original quote/fee/quantity reader only, no Runner.run or account paths.
 tmp=O/(sec+'-quote-context');tmp.mkdir(exist_ok=True)
 import shutil
 shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',tmp/'execution-rules-v2.json')
 R,E,core,_,mode=w.setup(sec,tmp,False);bundle,market=R.context();facts={};epochs={};native_facts=R.Facts(bundle,market);native_q_cache={};q_checks=[]
 def native_q(s,t):
  key=(s,t)
  if key not in native_q_cache:
   clock,stocks,sectors=native_facts.packet(dt(t),'I');stock=next(z for z in stocks if z.security_id==s);e=E.admission.eligibility(stock,{z.sector_id:z for z in sectors},clock,'S0');native_q_cache[key]=dict(security_id=s,issuer_id=e.issuer_id,sector_id=e.sector_id,q=e.q,reasons=list(e.reasons))
  return native_q_cache[key]
 def fact(s):
  if s not in facts:
   f=pd.read_parquet(prep/'facts'/f'{s}.parquet');facts[s]=f
   known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);starts=on&~on.groupby(f.segment_id).shift(fill_value=False);label=pd.Series(None,index=f.index,dtype=object)
   for t in f.index[starts]:label.loc[t]=f'{s}|source={int(f.loc[t,"segment_id"])}|E0={t.date()}'
   epochs[s]=label.groupby(f.segment_id).ffill().where(on,None)
  return facts[s]
 def row(s,at):
  f=fact(s);day=pd.Timestamp(dt(at).date())
  return f.loc[day] if day in f.index else None
 def epoch(s,at):
  fact(s);day=pd.Timestamp(dt(at).date());return epochs[s].get(day)
 def funding(s,l,after=False):
  b=l['before'];pending=Z;q=market.quote(s,dt(l['at']))
  if q is None:return dict(feasible=None,reason='decision_quote_unknown')
  if D(b['order_reserved'])!=0:return dict(feasible=None,reason='pending_gross_not_logged_separately',available=b['available'])
  if after:
   b=daily[l['at']];rs=[r for r in reserves if r['at']==l['at'] and r['sid'] in b['pending_buys']];pending=sum((D(r['gross_budget_cny']) for r in rs),Z)
   if sum((D(r['gross_budget_cny'])+D(r['fee_reserved_cny']) for r in rs),Z)!=D(b['order_reserved']):return dict(feasible=None,reason='post_commit_pending_reservation_not_fully_identified',available=b['available'])
  nav=D(b['nav']);price=q.read_price(dt(l['at']));fx=q.fx.read(dt(l['at']));cap=max(Z,min(D('.15')*nav,D('.9')*nav-D(b['inventory'])-pending,D(b['available'])));lo,hi=0,int((cap*100).to_integral_value(rounding=ROUND_FLOOR))
  while lo<hi:
   mid=(lo+hi+1)//2;v=D(mid)/100;fee=sum(q.fees.incremental('buy',v/fx,{}, {},D(1),shares=v/(price*fx),par_value=q.par_value).values(),Z)*fx
   if v+fee<=D(b['available']):lo=mid
   else:hi=mid-1
  budget=D(lo)/100;qty=q.quantity.buy_floor(int(budget/(price*fx)))
  return dict(feasible=qty>0,max_shares=qty,gross_budget=budget,available=b['available'],reason='original_ledger_budget_formula_no_order_created')
 all_daily=gz(root/'accounts-v2/daily.jsonl.gz');episodes=[];applications=[];intents=[];releases=[];checks=[]
 for policy in ['C10','C20','C30']:
  for stress in ['base','delay1']:
   aid=f'{mode}__{policy}_S0_{stress}';a=w.read(root/'accounts-v2'/f'{aid}.json');logs=a['audit_log'];adm=[x for x in logs if x['kind']=='loss_admission'];byat={x['at']:x for x in adm};cp={x['at']:x for x in logs if x['kind']=='risk_checkpoint'};daily={x['at']:x for x in all_daily if x['account']==aid};starts=[x for x in logs if x['kind']=='loss_start'];ends=[x for x in logs if x['kind']=='loss_end'];budget=[x for x in ends if x['reason']=='loss_budget'];reserves=[x for x in logs if x['kind']=='reserve'];fills=a['fills'];unknown=[x for x in logs if x['kind']=='loss_checkpoint' and not x['known']]
   for e in budget:
    sid=e['sid'];eid=f'{aid}|{e["cycle"]}';fact(sid);next_entry=next((s for s in starts if s['sid']==sid and dt(s['at'])>dt(e['at'])),None);group=e['group'];later=[l for l in adm if dt(l['at'])>=dt(e['at'])];window=[];unknown_dates=[];termination='data_cutoff';stop_at=adm[-1]['at']
    for l in later:
     t=l['at'];r=row(sid,t)
     if next_entry and dt(t)>=dt(next_entry['at']):termination='next_actual_entry';stop_at=next_entry['at'];break
     if r is None or not bool(r.e0_ready) or pd.isna(r.e0_target):unknown_dates.append(t)
     if r is not None and bool(r.e0_ready) and not pd.isna(r.e0_target) and epoch(sid,t)!=group:termination='original_E0_ended_or_source_changed';stop_at=t;break
     if epoch(sid,t)==group:window.append(l)
    recovered=bool(next_entry and next_entry['group']==group and dt(next_entry['at'])<=dt(stop_at))
    apps=[]
    for l in window:
     t=l['at'];r=row(sid,t)
     if r is None or pd.isna(r.i_buy) or not bool(r.i_buy):continue
     dd=l['decisions'];first=dd[0];last=dd[-1];el=next((x for x in first['eligibility'] if x['security_id']==sid),None);mem=next((x for x in last['memories'] if x['security_id']==sid),None);ack=[x[1] for x in l['rejected'] if x[0]==sid];slot=[x[1] for x in last['rejected'] if x[0]==sid];selected=any(sid in d['selected'] for d in dd);accepted=sid in l['accepted'];act=cp[t]['on'];fund=funding(sid,l);q_source='original_logged'
     if act and (el is None or len(q_checks)<3):
      ee=native_q(sid,t)
      if el is not None:
       assert ee==el,(aid,t,sid,'native cached eligibility differs from logged');q_checks.append(dict(account=aid,at=t,symbol=sid,exact=True))
      else:el=ee;q_source='same_frozen_cache_original_native_eligibility_only'
     if not act:primary='ACT_paused'
     elif el is None:primary='Q_not_true_components_unlogged'
     elif el['q'] is not True:primary='Q_unknown' if el['q'] is None else 'Q_false'
     elif accepted:primary='order_submitted'
     elif ack:primary=ack[0]
     elif slot:primary=slot[0]
     elif sid in daily[t]['pending_buys']:primary='existing_pending_buy'
     elif mem and not mem['waiting']:primary='no_waiting_intent'
     else:primary='unknown_no_logged_rejection'
     occ=[]
     for o in l['occupancy']:
      rr=row(o['security_id'],t);occ.append(dict(o,shares=daily[t]['positions'].get(o['security_id'],0),i_buy=None if rr is None or pd.isna(rr.i_buy) else bool(rr.i_buy),i_target=None if rr is None or pd.isna(rr.i_target) else bool(rr.i_target),e0_target=None if rr is None or pd.isna(rr.e0_target) else bool(rr.e0_target)))
     concurrent=list(ack+slot)
     if fund['feasible'] is False:concurrent.append('also_no_cash_exposure_or_minimum_quantity')
     if not act:concurrent.append('ACT_paused')
     fund_after=funding(sid,l,True)
     if fund_after['feasible'] is False:concurrent.append('after_actual_reservations_no_cash_exposure_or_minimum_quantity')
     ar=dict(sector=sec,account=aid,policy=policy,pressure=stress,episode=eid,symbol=sid,group=group,exit_at=e['at'],at=t,fresh_I=True,ACT=act,Q=el['q'] if el else None,Q_detail=el['reasons'] if el else ['omitted_when_not_true_and_flat'],Q_source=q_source,primary=primary,other_recorded_or_formula_conditions=sorted(set(concurrent)),selected=selected,accepted=accepted,memory=mem,waiting=mem['waiting'] if mem else None,funding=fund,funding_after_actual_reservations=fund_after,occupancy=occ,accepted_new=l['accepted'])
     applications.append(ar);apps.append(ar)
    actual_orders=[]
    for z in reserves:
     if z['sid']!=sid or dt(z['at'])<dt(e['at']) or dt(z['at'])>dt(stop_at) or epoch(sid,z['at'])!=group:continue
     fs=[f for f in logs if f['kind']=='fill' and f.get('order_id')==z['order_id']];ex=[x for x in logs if x.get('order_id')==z['order_id'] and x['kind'] in ['buy_day_expiry','open_support_reject','release_buy']];actual_orders.append(dict(reserve=z,fills=fs,execution_logs=ex))
    if recovered:outcome='same_structure_actual_reentry'
    elif not apps:outcome='no_same_structure_fresh_I' if not unknown_dates else 'no_observed_fresh_I_history_unknown'
    elif any(x['accepted'] for x in apps):outcome='submitted_without_same_structure_fill'
    else:outcome='fresh_I_without_submitted_order'
    detail=collections.Counter(x['primary'] for x in apps);episodes.append(dict(sector=sec,account=aid,policy=policy,pressure=stress,episode=eid,symbol=sid,group=group,cycle=e['cycle'],exit_at=e['at'],window_end=stop_at,termination=termination,outcome=outcome,next_actual_entry=next_entry['at'] if next_entry else None,next_entry_same_structure=recovered,observed_days=len(window),unknown_dates=unknown_dates,fresh_I_days=len(apps),Q_ACT_true_days=sum(x['Q'] is True and x['ACT'] for x in apps),first_primary=apps[0]['primary'] if apps else None,primary_counts=dict(detail),submitted_orders=len(actual_orders),orders=actual_orders,loss_unknown_before_exit=[x['at'] for x in unknown if x['cycle']==e['cycle']]))
    # Original intent identity, not a new queue. Only Q=True rows can expose a legal slot window.
    ib=collections.defaultdict(list)
    for ar in apps:
     m=ar['memory']
     if m and m.get('created_at') and ar['Q'] is True:ib[(m['created_at'],m['origin'])].append(ar)
    for ik,ars in ib.items():
     blocked=[x for x in ars if x['primary'] in ['total_slots_full','sector_slots_full','sector_issuer_slots_full']];exclusive=[x for x in blocked if x['ACT'] and x['funding']['feasible'] is True and x['funding_after_actual_reservations']['feasible'] is True]
     if not blocked:continue
     eligible_release=[]
     for ar in ars:
      if dt(ar['at'])<dt(blocked[0]['at']) or not ar['ACT']:continue
      old=next((x for x in reversed(adm) if dt(x['at'])<dt(ar['at'])),None)
      if old is None:continue
      cleared=[x for x in ends if dt(old['at'])<dt(x['at'])<=dt(ar['at'])]
      for x in cleared:
       if x['sid']==sid:continue
       original_occ=[o for o in ar['occupancy'] if o['security_id'] not in ar['accepted_new']]
       sect=next((z['sector_id'] for z in ar['occupancy'] if z['security_id']==sid),None)
       # Target sector is available from the cached native eligibility record.
       ll=byat[ar['at']];ee=next((z for z in ll['decisions'][0]['eligibility'] if z['security_id']==sid),None);sect=ee['sector_id'] if ee else sect
       cnt=collections.Counter(o['sector_id'] for o in original_occ);capacity=len(original_occ)<6 and cnt[sect]<2 and (sect in cnt or len(cnt)<3)
       rr=dict(sector=sec,account=aid,episode=eid,intent_id=f'{sid}|{ik[0]}|{ik[1]}',at=ar['at'],release_at=x['at'],released_symbol=x['sid'],release_reason=x['reason'],target=sid,Q=True,ACT=True,matching_capacity_before_new_acceptances=capacity,funding=ar['funding'],target_primary=ar['primary'],new_acceptances=ar['accepted_new'],occupancy_after=ar['occupancy'],batch_id=f'{aid}|{ar["at"]}')
       releases.append(rr);eligible_release.append(rr)
     intents.append(dict(sector=sec,account=aid,policy=policy,pressure=stress,episode=eid,symbol=sid,intent_id=f'{sid}|{ik[0]}|{ik[1]}',created_at=ik[0],origin=ik[1],first_slot_block=blocked[0]['at'],last_Q_true_same_intent=ars[-1]['at'],slot_block_days=len(blocked),exclusively_observable_slot_block_days=len(exclusive),natural_release_Q_true_rows=len(eligible_release),matching_and_funded_release_rows=sum(x['matching_capacity_before_new_acceptances'] and x['funding']['feasible'] is True for x in eligible_release),unknown_funding_release_rows=sum(x['funding']['feasible'] is None for x in eligible_release)))
   checks.append(dict(account=aid,budget_completed=len(budget),episode_rows=sum(x['account']==aid for x in episodes),same_structure_reentries=sum(x['account']==aid and x['next_entry_same_structure'] for x in episodes)))
 save(O/f'{sec}-FUNNEL_EPISODES.json',episodes);save(O/f'{sec}-FUNNEL_APPLICATIONS.json',applications);save(O/f'{sec}-FUNNEL_INTENTS.json',intents);save(O/f'{sec}-NATURAL_RELEASES.json',releases);summary=[]
 for c in checks:
  ep=[x for x in episodes if x['account']==c['account']];ap=[x for x in applications if x['account']==c['account']];summary.append(dict(**c,outcomes=dict(collections.Counter(x['outcome'] for x in ep)),first_primary=dict(collections.Counter(x['first_primary'] or 'no_observed_fresh_I' for x in ep)),fresh_I_days=len(ap),application_primary=dict(collections.Counter(x['primary'] for x in ap)),history_unknown_episode_count=sum(bool(x['unknown_dates'] or x['loss_unknown_before_exit']) for x in ep),Q_unknown_episode_count=len(set(x['episode'] for x in ap if x['primary']=='Q_unknown')),funding_unknown_application_days=sum(x['funding']['feasible'] is None or x['funding_after_actual_reservations']['feasible'] is None for x in ap)))
 save(O/f'{sec}-FUNNEL_SUMMARY.json',dict(seconds=time.monotonic()-start,rows=summary,all_episodes=len(episodes),all_application_days=len(applications),all_slot_intents=len(intents),natural_release_batches=len(set(x['batch_id'] for x in releases)),native_eligibility_log_identity_checks=q_checks));print(json.dumps(summary,ensure_ascii=False,default=str));print('funnel_seconds',time.monotonic()-start)
if __name__=='__main__':main(sys.argv[1])
