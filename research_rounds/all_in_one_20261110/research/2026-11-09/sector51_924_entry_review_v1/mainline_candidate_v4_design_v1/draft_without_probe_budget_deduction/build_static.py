from pathlib import Path
import sys,importlib.util,json,copy,hashlib
from decimal import Decimal as D
from collections import defaultdict
import pandas as pd
import numpy as np
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;P=R/'mainline_candidate_v3_core_reference/once_20241008';spec=importlib.util.spec_from_file_location('m4_frozen_m3',R/'mainline_candidate_v3_core_reference/engine.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
Z=D(0);S=m.SLIP;DATES=['2024-09-20','2024-09-23','2024-09-26','2024-09-27']
read=lambda p:json.loads(p.read_text())
def save(n,x):(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
def B(x):
 assert x in [True,False,'True','False'];return x is True or x=='True'
logs={n:read(P/(n+'.json')) for n in ['ORDERS','DAY_LEDGER','HOLDINGS','CAPITAL_LOTS','REFERENCE_REQUESTS','CANDIDATES','SECTOR_DAILY']};data=m.Data('2024-10-08');navs={r['day']:D(r['NAV']) for r in logs['DAY_LEDGER']};ledger={r['day']:r for r in logs['DAY_LEDGER']};buys={r['lot_id']:r for r in logs['ORDERS'] if r['side'].startswith('BUY')}
# All snapshots use only dates <= snapshot. No next-OPEN quotes read.
def sur(s,dt,q,C):
 _,fs,pa=data.getmeta(s,dt);total=Z
 for side,p in [('buy',C*(1+S)),('sell',C*(1-S))]:
  actual=fs.incremental(side,q*p,{}, {},1,shares=q,par_value=pa);proportional=fs.rate_accrual(side,q*p,1,shares=q,par_value=pa)
  for c in fs.components:
   if D(c.minimum_local)>0 and c.side in ('both',side):total+=max(Z,actual[c.name]-proportional[c.name])
 return total

def qecon(s,dt,C,cap,budget):
 qr=data.getmeta(s,dt)[0];p=C*(1+S);maxq=data.size(s,dt,p,budget,cap)
 if maxq<qr.buy_minimum:return 0,'ORIGINAL_BUDGET_OR_CAPACITY'
 def ok(q):return sur(s,dt,q,C)<=2*S*q*C
 if not ok(maxq):return 0,'ECONOMIC_UNIT_EXCEEDS_ORIGINAL_CAPS'
 lo=0;hi=(maxq-qr.buy_minimum)//qr.buy_step
 while lo<hi:
  mid=(lo+hi)//2
  if ok(qr.buy_minimum+mid*qr.buy_step):hi=mid
  else:lo=mid+1
 return qr.buy_minimum+lo*qr.buy_step,'PASS'

def score(s,dt):
 ix=data.cal.get_loc(dt);ds=data.cal[ix-5:ix+1];z=data.raw[s].reindex(ds)
 if len(z)!=6:return None
 origin=None
 for _,r in z.iterrows():
  if not m.valid(r) or not all(m.finite(r.get(c)) and r[c]>0 for c in ['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']):return None
  if origin is None:origin=m.lineage(r)
  if m.lineage(r)!=origin:return None
  if abs(D(str(r.raw_close))*D(str(r.adjustment_factor))/D(str(r.close))-1)>D('1e-10'):return None
 ret=D(str(z.iloc[-1].close))/D(str(z.iloc[0].close))-1;sec=data.sid_sector[s];median=data.main[sec].loc[dt].return5_median
 if not m.finite(median):return None
 streak=0
 for x in reversed(data.stock.loc[:dt,s].tolist()):
  if x!=1:break
  streak+=1
 return ret-D(str(median)),streak

allreq=[];allsector=[];allchosen=[];alldonors=[];allbudget=[];allevents=[];alllots=[]
for day in DATES:
 dt=pd.Timestamp(day);nxt=data.cal[data.cal.get_loc(dt)+1];ld=ledger[day];nav=D(ld['NAV']);cash=D(ld['cash']);reserve=nav*D('.1');sects={r['sector51']:r for r in logs['SECTOR_DAILY'] if r['day']==day};lots=[dict(r) for r in logs['CAPITAL_LOTS'] if r['day']==day];qheld=defaultdict(int)
 for r in lots:qheld[r['sid']]+=r['qty']
 seedonly={sid:all(r['kind']=='SEED' for r in lots if r['sid']==sid) for sid in qheld};events={};mature={}
 for sec,ss in sects.items():
  fr=data.sectors[sec].loc[:dt];births=fr.index[(fr.state==1)&(fr.state.shift()==0)];birth=births[-1] if len(births) else None
  if birth is not None and (fr.loc[birth:].state==0).any():birth=None
  born=m.day(birth) if birth is not None else None;eventnav=navs.get(born);spent=sum((-D(t['cash_delta']) for t in logs['ORDERS'] if t['sector51']==sec and t['side']=='BUY_SEED' and born is not None and born<=t['day']<=day),Z)
  remaining=max(Z,D('.02')*eventnav-spent) if eventnav is not None else Z
  mature[sec]=ss['M']==1 and ss['E'] is not None and ss['E']>0 and any(B(r['current_winner']) for r in lots if r['sector51']==sec)
  events[sec]=dict(snapshot_day=day,sector51=sec,event_id=sec+'|'+born if born else None,birth_day=born,birth_NAV=eventnav,capital_cap=D('.02')*eventnav if eventnav else Z,actual_prior_SEED_consumption=spent,remaining=remaining,current_mature=bool(mature[sec]),state=ss['state'],M=ss['M'],n=ss['n'],N=ss['N'],diff=ss['diff'])
 allevents.extend(events.values())
 # Build real request candidates, preserving identity and original NAV.
 req=[]
 for src in [r for r in logs['REFERENCE_REQUESTS'] if r['day']==day]:
  r=dict(src);s=r['sid'];sec=r['sector51'];ss=sects[sec];C=D(str(data.z(s,dt)['raw_close']));p=C*(1+S);r.update(snapshot_day=day,next_known_trade_day=m.day(nxt),C=C,unit_q=0,unit_cost=Z,stock_excess5=None,stock_TRUE_streak=None)
  if r['kind']=='SEED':
   oldnav=navs[r['signal_day']];budget=min(D('.02')*oldnav,D('.1')*nav);cap=data.cap[s].get(dt);sc=score(s,dt);r['original_ticket_NAV']=oldnav
   if sc is None:reason='REPRESENTATIVE_SCORE_UNKNOWN'
   elif not m.finite(cap):reason='CAPACITY_UNKNOWN'
   else:
    q,reason=qecon(s,nxt,C,int(cap),budget);r['unit_q']=q;r['stock_excess5']=sc[0];r['stock_TRUE_streak']=sc[1];r['capacity_value']=int(cap)*C
   if mature[sec]:phase='MATURE'
   elif ss['state']==1 and ss['M']!=-1 and events[sec]['birth_NAV'] is not None:phase='EVENT'
   else:phase='PAUSED'
   r['phase']=phase;r['unit_reason']=reason;r['unit_cost']=r['unit_q']*p+data.fee(s,nxt,r['unit_q'],p,'buy') if r['unit_q'] else Z
   r['one_lot_cost']=data.getmeta(s,nxt)[0].buy_minimum*p+data.fee(s,nxt,data.getmeta(s,nxt)[0].buy_minimum,p,'buy')
   r['surcharge']=sur(s,nxt,r['unit_q'],C) if r['unit_q'] else None;r['proxy_roundtrip_slip']=2*S*r['unit_q']*C if r['unit_q'] else None
  else:
   r['phase']='MATURE';roundlots=[x for x in lots if x['sid']==s];seedorder=next(t for t in logs['ORDERS'] if t['side']=='BUY_SEED' and t['round_id']==roundlots[0]['round_id']);oldnav=D(seedorder['frozen_attempt_NAV']);value=sum((D(x['market_value']) for x in roundlots),Z);budget=min(D('.02')*oldnav,max(Z,D('.04')*oldnav-value),max(Z,D('.1')*nav-value));q=data.size(s,nxt,p,budget,r['base_planned_q']);r['unit_q']=q;r['unit_cost']=q*p+data.fee(s,nxt,q,p,'buy') if q else Z;r['unit_reason']='PASS' if q else 'ORIGINAL_ADD_CAPS'
  req.append(r)
 # Sector provisional probe receivers cannot simultaneously donate old positions.
 probe_sec={r['sector51'] for r in req if r['phase']=='EVENT' and r['unit_q']>0 and r['unit_cost']<=events[r['sector51']]['remaining']}
 fixed={sec:D(ss['market_value']) for sec,ss in sects.items()};stress=Z;mandatory=Z;released_dormant=Z
 for r in lots:
  s=r['sid'];sec=r['sector51'];C=D(r['raw_mark']);qr=data.getmeta(s,nxt)[0];oldmobile=r['mobile_qty'];known=not r['unknown'];locked=B(r['locked']);sellable=nxt>pd.Timestamp(r['bought']);newrole=seedonly[s] and r['M']==0 and known
  r['new_current_trial_retirement']=bool(newrole);r['old_mobile_qty']=oldmobile;r['static_new_exit']=bool(newrole and sects[sec]['state']==0)
  if locked or r['static_new_exit']:
   q=qr.sell_floor(r['qty'],qheld[s]) if sellable else 0
   if q:mandatory+=q*C*(1-S)-data.fee(s,nxt,q,C*(1-S),'sell')
   mobile=0;reason='MANDATORY_EXIT_OR_LOCK'
  else:
   mobile=qr.sell_floor(r['qty'],qheld[s]) if newrole and sellable else oldmobile;reason='CURRENT_NON_M_SEED_RETIREMENT' if newrole else r['donor_reason']
  if sec in probe_sec:mobile=0;reason='PROBE_RECEIVER_SECTOR_FROZEN'
  r['mobile_qty_m4']=mobile;r['donor_reason_m4']=reason;fixed[sec]-=mobile*C
  if mobile:stress+=mobile*C-(mobile*C*(1-S)-data.fee(s,nxt,mobile,C*(1-S),'sell'))
  if newrole and mobile>oldmobile:released_dormant+=(mobile-oldmobile)*C
  alllots.append(r)
 es={sec:D(str(ss['E'])) for sec,ss in sects.items() if ss['M']==1 and ss['E'] is not None and ss['E']>0};outside=sum((v for sec,v in fixed.items() if sec not in es),Z);budget=nav-reserve-D(ld['receivable'])-outside-stress;targets,lam,status=m.water({sec:fixed[sec] for sec in es},es,budget);T=dict(fixed);T.update(targets);envelope={sec:max(Z,T[sec]-D(sects[sec]['market_value'])) if status=='PASS' and sec in es else Z for sec in sects}
 # First event rounds: one economic unit per industry per round, no guaranteed funding.
 def stockkey(r):return (-r['stock_excess5'], -r['stock_TRUE_streak'], -r.get('capacity_value',Z),r['signal_day'],r['sid'])
 queues={sec:sorted([r for r in req if r['phase']=='EVENT' and r['sector51']==sec and r['unit_q']>0],key=stockkey) for sec in events};rem={sec:e['remaining'] for sec,e in events.items()};chosen=[];eventround=0
 while any(queues.values()):
  eventround+=1;progress=False
  secorder=sorted([s for s in queues if queues[s]],key=lambda sec:(events[sec]['birth_day'] or '9999',-D(sects[sec]['n'])/D(sects[sec]['N']),-D(sects[sec]['diff'])/D(sects[sec]['N']),sec))
  for sec in secorder:
   accepted=None
   while queues[sec]:
    r=queues[sec].pop(0)
    if r['unit_cost']<=rem[sec]:accepted=r;break
    r['plan_reject']='EVENT_CAP_REMAINDER'
   if accepted:
    r=accepted;r.update(planned_q=r['unit_q'],planned_cost=r['unit_cost'],event_round=eventround);chosen.append(r);rem[sec]-=r['unit_cost'];progress=True
  if not progress:break
 # Mature T allocation, one request then re-evaluate gaps, ADD head then seed representative.
 spent=defaultdict(lambda:Z);remaining=[r for r in req if r['phase']=='MATURE' and r['unit_q']>0];initialMV={sec:D(ss['market_value']) for sec,ss in sects.items()}
 while remaining:
  heads=[]
  for sec in sorted({r['sector51'] for r in remaining}):
   rs=[r for r in remaining if r['sector51']==sec];adds=[r for r in rs if r['kind']=='ADD'];heads.append(min(adds,key=lambda r:(r['signal_day'],r['sid'])) if adds else min(rs,key=stockkey))
  r=min(heads,key=lambda r:(-max(Z,T[r['sector51']]-initialMV[r['sector51']]-spent[r['sector51']]),-sects[r['sector51']]['M_streak'],-D(str(sects[r['sector51']]['E'] or 0)),r['signal_day'],r['sid']));remaining.remove(r);sec=r['sector51'];gap=max(Z,envelope[sec]-spent[sec]);s=r['sid'];p=r['C']*(1+S)
  q=r['unit_q'] if r['kind']=='SEED' and r['unit_cost']<=gap else 0 if r['kind']=='SEED' else data.size(s,nxt,p,gap,r['unit_q']);cost=q*p+data.fee(s,nxt,q,p,'buy') if q else Z
  if q:r.update(planned_q=q,planned_cost=cost,event_round=None);chosen.append(r);spent[sec]+=cost
  else:r['plan_reject']='REFERENCE_CAP_ECONOMIC_UNIT' if r['kind']=='SEED' else 'REFERENCE_CAP'
 # Exact legal donor upper bounds and actual needed planned sales, with same-industry direction lock.
 receiving={r['sector51'] for r in chosen};sectorleft=dict(initialMV);pool=[r for r in lots if r['mobile_qty_m4']>0 and r['sector51'] not in receiving];desired=sum((r['planned_cost'] for r in chosen),Z);gap=max(Z,desired+reserve-cash-mandatory) if desired else Z;initialgap=gap;net=Z;sale_upper=Z;don=[]
 def dkey(r):
  why=r['donor_reason_m4'];tier=0 if r['kind']=='SEED' else 1 if why=='WEAK_SECTOR_ADD_LAYER' else 2;sec=r['sector51'];surplus=max(Z,sectorleft[sec]-max(fixed[sec],T[sec]))
  return (tier,r['stock_state']!=0 if tier==0 else False,D(r['E']) if tier==0 else -surplus if tier==2 else Z,D(r['E']) if tier==2 else Z,r['bought'],r['sid'],r['lot_id'])
 while pool:
  r=min(pool,key=dkey);pool.remove(r);s=r['sid'];sec=r['sector51'];C=D(r['raw_mark']);p=C*(1-S);qr=data.getmeta(s,nxt)[0];surplus=max(Z,sectorleft[sec]-max(fixed[sec],T[sec]));maxq=qr.sell_floor(min(r['mobile_qty_m4'],int(surplus/C)),qheld[s]);maxq=maxq if r['kind']!='SEED' or maxq==r['qty'] else 0
  if not maxq:continue
  upper=maxq*p-data.fee(s,nxt,maxq,p,'sell');sale_upper+=upper
  if gap<=0:continue
  if r['kind']=='SEED':q=maxq
  else:
   q=qr.sell_floor(min(maxq,max(qr.sell_step,int(gap/p))),qheld[s])
   while q<maxq and q*p-data.fee(s,nxt,q,p,'sell')<gap:q=qr.sell_floor(min(maxq,q+qr.sell_step),qheld[s])
  proceeds=q*p-data.fee(s,nxt,q,p,'sell');net+=proceeds;gap=max(Z,gap-proceeds);sectorleft[sec]-=q*C;don.append(dict(snapshot_day=day,sid=s,sector51=sec,lot_id=r['lot_id'],qty=q,reason=r['donor_reason_m4'],net_cash=proceeds,prior_information_confirmed=B(r['confirmed_history']),current_winner=B(r['current_winner'])))
 # Funding is now real-close conditional cash; no future OPEN assumptions or guarantees.
 available=cash+mandatory+net;funded=Z;fc=defaultdict(int);fn=defaultdict(int);costsec=defaultdict(lambda:Z)
 for rank,r in enumerate(chosen,1):
  s=r['sid'];p=r['C']*(1+S);room=max(Z,available-reserve);q=r['planned_q'] if r['kind']=='SEED' and r['planned_cost']<=room else 0 if r['kind']=='SEED' else data.size(s,nxt,p,room,r['planned_q']);cost=q*p+data.fee(s,nxt,q,p,'buy') if q else Z;available-=cost;funded+=cost;sec=r['sector51'];fc[sec]+=q>0;fn[sec]+=r['kind']=='SEED' and q>0;costsec[sec]+=cost;r.update(global_rank=rank,static_funded_q=q,static_funded_cost=cost,static_decision='CLOSE_CONDITIONAL_FUNDED' if q else 'CASH_RESERVE');allchosen.append(r)
 for r in req:
  if 'planned_q' not in r:r.update(planned_q=0,planned_cost=Z,static_funded_q=0,static_funded_cost=Z,static_decision=r.get('plan_reject',r['unit_reason'] if r['unit_reason']!='PASS' else 'NO_ACTIVE_PHASE_OR_EVENT'))
 allreq.extend(req);alldonors.extend(don)
 for sec,ss in sects.items():
  rs=[r for r in req if r['sector51']==sec];cc=[r for r in chosen if r['sector51']==sec];allsector.append(dict(snapshot_day=day,sector51=sec,N=ss['N'],n=ss['n'],state=ss['state'],M=ss['M'],E=ss['E'],birth_day=events[sec]['birth_day'],event_remaining=events[sec]['remaining'],current_mature=mature[sec],current_value=ss['market_value'],core=sum((D(r['core_value']) for r in lots if r['sector51']==sec),Z),new_fixed=fixed[sec],T=T[sec],real_SEED_requests=sum(r['kind']=='SEED' for r in rs),real_ADD_requests=sum(r['kind']=='ADD' for r in rs),economic_size_pass=sum(r['kind']=='SEED' and r['unit_q']>0 for r in rs),event_selected=sum(r['phase']=='EVENT' for r in cc),mature_selected=sum(r['phase']=='MATURE' for r in cc),funded_requests=fc[sec],funded_SEED=fn[sec],funded_buy_cost=costsec[sec],planned_buy_cost=sum((r['planned_cost'] for r in cc),Z),donor_net=sum((r['net_cash'] for r in don if r['sector51']==sec),Z)))
 summary=dict(snapshot_day=day,NAV=nav,cash=cash,reserve=reserve,receivable=D(ld['receivable']),new_mobile_formerly_frozen_seed_mark=released_dormant,mandatory_close_estimate=mandatory,candidate_donor_net_upper=sale_upper,actual_planned_donor_net=net,desired_cost=desired,initial_shortfall=initialgap,remaining_shortfall=gap,close_conditional_funded_cost=funded,funded_requests=sum(fc.values()),funded_new_seed_names=sum(fn.values()),funded_sectors=sum(v>0 for v in fc.values()),event_selected=sum(r['phase']=='EVENT' for r in chosen),event_funded=sum(r['phase']=='EVENT' and r['static_funded_q']>0 for r in chosen),event_funded_cost=sum((r['static_funded_cost'] for r in chosen if r['phase']=='EVENT'),Z),mature_funded_cost=sum((r['static_funded_cost'] for r in chosen if r['phase']=='MATURE'),Z),fee_economic_fail=sum(r['kind']=='SEED' and r['unit_q']==0 for r in req),seed_request_count=sum(r['kind']=='SEED' for r in req),T_status=status,lambda_value=lam,closing_cash_after_conditional_orders=available)
 allbudget.append(summary);print('SNAPSHOT '+json.dumps(summary,ensure_ascii=False,default=str),flush=True)
for n,x in [('ALL_REAL_REQUESTS',allreq),('ALL50_STATIC_FEASIBILITY',allsector),('ALL_SELECTED_REQUESTS',allchosen),('ALL_PLANNED_DONORS',alldonors),('SNAPSHOT_SUMMARY',allbudget),('EVENT_CAPITAL_IDENTITIES',allevents),('CURRENT_SEED_RETIREMENT_AND_CORE',alllots)]:save(n,x)
qa=dict(result='PASS_STATIC_ONLY_NOT_NEW_ACCOUNT',snapshots=DATES,source_engine_sha256=m.sha(R/'mainline_candidate_v3_core_reference/engine.py'),source_account_hashes={n:m.sha(P/(n+'.json')) for n in logs},script_sha256=m.sha(O/'build_static.py'),mechanism_sha256=m.sha(O/'STATIC_MECHANISM.md'),future_OPEN_prices_used=0,new_history_runs=0,minimum_commission_rule='surcharge <= 2*0.0005*q*C',old_total_fee_inequality='MATHEMATICALLY_INFEASIBLE_WITH_SSE_10.282BP_LOWER_BOUND',original_files_modified=0)
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2,default=str)+'\n')
