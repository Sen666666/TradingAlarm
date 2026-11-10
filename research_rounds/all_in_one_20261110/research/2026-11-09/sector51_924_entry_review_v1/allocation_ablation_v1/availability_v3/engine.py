"""New bounded availability/accounting semantics, not a fact-only revision."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys,json,copy,hashlib,importlib.util,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;OLD=O.parent;ROOT=OLD.parent
sys.path.insert(0,str(OLD));import ablation_engine as frozen
spec=importlib.util.spec_from_file_location('availability_core_v11',ROOT/'joint51_candidate_v11_suspension_accounting/engine.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
base=frozen.base;ZERO=base.ZERO;SLIP=base.SLIP;INITIAL=base.INITIAL
pd=base.pd;np=base.np;dec=base.dec;day=base.day;finite=base.finite;truth=base.truth;false=base.false;valid=base.valid;lineage=base.lineage;Blocked=core.Blocked
from allocation_rules import add_quantity_limit,arm_config,seed_capital_failure,ticket_from_seed,refresh_retained_ticket,m3_seed_exit
OLD_FAMILIES=frozen.FAMILIES+['RETRY_TICKETS','RETAINED_AT_END','ADDITIONAL_EXIT','ADD_QUANTITY_LIMITS','FULL_CAP_VIOLATIONS']

def known_origin(z):return all(z.get(k) is not None and pd.notna(z.get(k)) and str(z.get(k))!='' for k in ('source_kind','source_path','segment_id'))
def open_known(z):return known_origin(z) and all(finite(z.get(k)) and z[k]>0 for k in ('raw_open','adjustment_factor'))

class Data(base.Data):
 def __init__(self):
  base.O=O/'facts';super().__init__('2024-10-31')
  self.hashes[str(Path(core.__file__))]=base.sha(core.__file__)
  self.policies=base.read(O/'SUSPENSION_POLICY.json')['policies'];self.resume_sources={}
  for pol in self.policies:
   for stem in ['source','official_notice','official_text','fact_envelope']:
    p=pol[stem+'_path'];h=pol[stem+'_sha256'];assert base.sha(p)==h;self.hashes[p]=h
   anchor=self.z(pol['sid'],pd.Timestamp(pol['mark_source_day']));assert valid(anchor) and dec(anchor['raw_close'])==dec(pol['raw_mark']) and dec(anchor['adjustment_factor'])==dec(pol['factor']);pol['origin']=lineage(anchor)
   for ds in pol['covered_dates']:
    assert not len(self.z(pol['sid'],pd.Timestamp(ds)));assert self.stock.at[pd.Timestamp(ds),pol['sid']]==-1
   fact=base.read(pol['fact_envelope_path']);self.resume_sources[pol['sid']]=[x for x in fact.get('official_sources',[]) if x.get('role')=='RESUMPTION']
  for name in ['engine.py','CONTRACT.md','SUSPENSION_POLICY.json','synthetic_availability.py','SYNTHETIC_QA.json','build_engine.py']:self.hashes[str(O/name)]=base.sha(O/name)
 def suspension(self,s,d):
  return next((p for p in self.policies if p['sid']==s and day(d) in p['covered_dates']),None)
 def resume_notice_available(self,s,d):
  # Same-day publication without a historical pre-OPEN timestamp is insufficient.
  return any(x['publication_date']<day(d) for x in self.resume_sources.get(s,[]))

class Engine(frozen.AblationEngine):
 def __init__(self,data,arm):
  super().__init__(data,arm);self.quote_gaps={};self.held_gaps={};self.availability=[];self.suspension_log=[];self.preflight_log=[]
 suspension=core.Engine.suspension
 mark=core.Engine.mark
 qvalue=core.Engine.qvalue
 liquidation_value=core.Engine.liquidation_value
 suspension_preflight=core.Engine.suspension_preflight
 suspension_event=core.Engine.suspension_event
 net=core.Engine.net
 order=core.Engine.order
 exit_open=core.Engine.exit_open
 def avail(self,t,d,event,**kw):
  self.availability.append(dict(day=day(d),sid=t['sid'],ticket_id=t.get('ticket_id'),event=event,status=t.get('status'),original_signal_day=t.get('signal_day'),original_NAV=str(t['nav0']),last_verified_day=t.get('last_verified_day'),last_verified_factor=str(t.get('current_factor',t.get('factor'))),**kw))
 def pause(self,t,d,z):
  s=t['sid'];assert s not in self.active or self.quantity(self.active[s])==0
  if s not in self.quote_gaps:self.quote_gaps[s]=dict(start_day=day(d),last_verified_day=t['last_verified_day'],last_verified_factor=str(t['current_factor']),origin=t['origin'],days=[],action_inventory=[])
  gap=self.quote_gaps[s];gap['days'].append(day(d));gap['action_inventory'].extend(dict(day=day(d),action=a,reviewed_event=(s,d) in self.d.events) for a in self.d.action(s,d));t['status']='PAUSED_NO_QUOTE';t['plan']=None;t['reason']='CURRENT_OPEN_SOURCE_UNAVAILABLE'
  self.avail(t,d,'PAUSED_NO_QUOTE',source_identity_observed=known_origin(z),observed_open=z.get('raw_open') if finite(z.get('raw_open')) else None,pending_action_count=len(gap['action_inventory']))
 def verify_gap_chain(self,s,d,gap,held=False):
  expected=dec(gap['last_verified_factor']);origin=tuple(gap['origin']);start=pd.Timestamp(gap['last_verified_day']);dates=set(self.d.cal[(self.d.cal>start)&(self.d.cal<=d)])
  for event in self.d.actions[s]['events']:
   dt=pd.Timestamp(event['effective_date'])
   if start<dt<=d:dates.add(dt)
  dates|={dt for sid,dt in self.d.events if sid==s and start<dt<=d};checks=[]
  if hasattr(self.d,'manifest'):
   source=next(p for p in self.d.manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));assert base.sha(source)==self.d.hashes[source]
  for when in sorted(dates):
   z=self.d.z(s,when);actions=self.d.action(s,when);ev=self.d.events.get((s,when))
   if known_origin(z) and lineage(z)!=origin:
    if held:raise Blocked(f'{day(d)} {s} HELD_GAP_SOURCE_CHANGED {day(when)}')
    return None,dict(changed_source_day=day(when))
   if actions and ev is None:raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_EQUITY_EVENT {day(when)}')
   if ev:
    if abs(expected/dec(ev['factor_old'])-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FACTOR_CHAIN_OLD_MISMATCH {day(when)}')
    expected=dec(ev['factor_new'])
   observed=finite(z.get('adjustment_factor')) and z['adjustment_factor']>0
   if observed and abs(dec(z['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_FACTOR_CHANGE {day(when)}')
   checks.append(dict(day=day(when),event_id=ev.get('economic_event_id_candidate') if ev else None,factor_observed=bool(observed),verified_factor_chain=str(expected)))
  if not open_known(self.d.z(s,d)) or abs(dec(self.d.z(s,d)['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FINAL_QUOTE_MISMATCH')
  return expected,checks
 def economic_preflight(self,d,pending):
  exclude=set();remove=set()
  if self.arm.retry_capital_seed:
   for s,t in list(self.retained.items()):
    if s in self.active and self.quantity(self.active[s])>0:raise Blocked(f'{day(d)} {s} RETAINED_TICKET_WITH_ACTUAL_HOLDING')
    z=self.d.z(s,d)
    if known_origin(z) and lineage(z)!=tuple(t['origin']):
     t['status']='CANCELLED';t['plan']=None;self.retry_record(t,d,'OPEN','SOURCE_CHANGED_CANCEL');self.avail(t,d,'KNOWN_SOURCE_CHANGED_CANCEL');self.retained.pop(s);self.quote_gaps.pop(s,None);remove.add(s);continue
    if not open_known(z):self.pause(t,d,z);exclude.add(s);remove.add(s)
    elif s in self.quote_gaps:
     factor,checks=self.verify_gap_chain(s,d,self.quote_gaps[s]);remove.add(s);exclude.add(s)
     if factor is None:
      t['status']='CANCELLED';t['plan']=None;self.avail(t,d,'GAP_SOURCE_CHANGED_CANCEL',**checks);self.retained.pop(s)
     else:
      t['current_factor']=factor;t['last_verified_day']=day(d);t['status']='RETAINED';t['plan']=None;t['reason']='GAP_REVERIFIED_WAIT_CLOSE';self.avail(t,d,'GAP_REVERIFIED_NO_OLD_OPEN_FILL',checks=checks)
     self.quote_gaps.pop(s,None)
  pending[:]=[r for r in pending if r['sid'] not in remove]
  all_pending=list(pending);queued={r['sid'] for r in all_pending}
  for s,t in self.retained.items():
   if s not in queued and s not in exclude:all_pending.append(dict(sid=s,origin=t['origin'],factor=t['current_factor'],ticket_id=t['ticket_id']))
  # Held policies do not supply a quote; capture original anchor and obligations.
  resumed=[]
  for s,a in self.active.items():
   pol=self.suspension(s,d)
   if pol and s not in self.held_gaps:self.held_gaps[s]=dict(last_verified_day=pol['mark_source_day'],last_verified_factor=str(a['factor']),origin=a['origin'],start_day=day(d))
   elif not pol and s in self.held_gaps and open_known(self.d.z(s,d)):
    if not self.d.resume_notice_available(s,d):raise Blocked(f'{day(d)} {s} HELD_RESUME_NOTICE_NOT_KNOWN_BEFORE_OPEN')
    factor,checks=self.verify_gap_chain(s,d,self.held_gaps[s],held=True);a['factor']=factor;resumed.append(s);self.suspension_event(a,d,'OPEN','HELD_RESUMPTION_VERIFIED',checks=checks);self.held_gaps.pop(s)
  # A resumed held chain has already been checked over its entire interval.
  held_saved={s:self.active.pop(s) for s in resumed}
  try:core.Engine.economic_preflight(self,d,all_pending)
  finally:self.active.update(held_saved)
  for s,t in self.retained.items():
   if s not in exclude:
    t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d)
    if self.d.events.get((s,d)) is not None:self.retry_record(t,d,'OPEN','VERIFIED_PENDING_BRIDGE',record_qty=0,entitlement='0')
 def paused_close(self,s,t,d):
  sec=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']);st=int(self.d.stock.at[d,s]);i=self.d.f(s,d).get('i_target');reason='RETRY_SECTOR_FALSE' if sec==0 else 'RETRY_STOCK_M3_FALSE' if st==0 else 'RETRY_I_FALSE' if false(i) else None
  if reason:
   t['status']='CANCELLED';t['plan']=None;t['reason']=reason;self.avail(t,d,'KNOWN_FALSE_CANCEL_WHILE_NO_QUOTE',reason=reason);self.retained.pop(s);self.quote_gaps.pop(s,None)
  else:self.avail(t,d,'PAUSED_CLOSE_NO_PRICE_SIGNAL',sector_state=sec,stock_state=st)
 def close(self,d,prev):
  pending=core.Engine.close(self,d,prev)
  if self.arm.progressive_add:
   for s,a in self.active.items():
    r=a.get('plan')
    if r:
     before=r['planned_q'];after=add_quantity_limit(self.arm,self.d.getmeta(s,d)[0],before,self.quantity(a));r['planned_q']=after
     self.add_quantity_log.append(dict(day=day(d),phase='CLOSE',sid=s,round_id=a['id'],baseline_q=before,current_round_q=self.quantity(a),limited_q=after,cp_id=r['cp_id']))
     if not after:
      a['plan']=None
      for row in reversed(self.candidates):
       if row['day']==day(d) and row.get('sid')==s and row.get('event')=='ADD_GATE':row['decision']='B_ADD_HOLDING_Q_NO_LEGAL';break
  if self.arm.exit_unconfirmed_m3_false:
   for s,a in self.active.items():
    decision=m3_seed_exit(self.arm,historical_actual_add_count=a['add_count'],stock_state=int(self.d.stock.at[d,s]),prior_exit_reason=a['exit'])
    if decision['new_condition']:
     self.extra_exits.append(dict(day=day(d),sid=s,round_id=a['id'],stock_state=int(self.d.stock.at[d,s]),add_count=a['add_count'],prior_exit=a['exit'],**decision))
    if decision['incremental_exit']:
     a['exit']=decision['exit_reason'];a['plan']=None
     for row in reversed(self.candidates):
      if row['day']==day(d) and row.get('sid')==s and row.get('event')=='ADD_GATE':row['decision']='LOCKED_EXIT';break
     for h in reversed(self.holdings):
      if h['day']!=day(d):break
      if h['sid']==s:h['locked_exit']=a['exit']
  if self.arm.retry_capital_seed:
   old=set(self.retained)
   for row in self.candidates:
    if row['day']==day(d) and row.get('phase')=='CLOSE' and row.get('sid') in old and row.get('event') in ('A','B'):row['decision']='TICKET_ALREADY_RETAINED'
   pending=[r for r in pending if r['sid'] not in old]
   for s,t in list(self.retained.items()):
    if s in self.quote_gaps:
     self.paused_close(s,t,d);continue
    z=self.d.z(s,d);f=self.d.f(s,d);cap=self.d.cap[s].get(d,np.nan);i=f.get('i_target');istate=1 if truth(i) else 0 if false(i) else -1
    floor=dec(f['i_floor']) if finite(f.get('i_floor')) else None
    raw=dec(z['raw_close']) if finite(z.get('raw_close')) else None
    q=self.d.getmeta(s,d)[0].buy_minimum
    cost=q*raw*(1+SLIP)+self.d.fee(s,d,q,raw*(1+SLIP),'buy') if raw is not None and raw>0 else ZERO
    result=refresh_retained_ticket(t,date=day(d),sector_state=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']),stock_state=int(self.d.stock.at[d,s]),i_state=istate,current_ifloor=floor,raw_close=raw,capacity=int(cap) if finite(cap) else None,buy_minimum=q,all_in_min_cost=cost,source_valid=valid(z))
    self.retry_record(t,d,'CLOSE',result,reason=t.get('reason'),plan_day=day(d))
    if result=='PLAN':pending.append(copy.deepcopy(t['plan']))
    elif result=='CANCELLED':self.retained.pop(s)
  return pending
 def alloc_open(self,d,pending):
  pre_nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};sec=defaultdict(lambda:ZERO);cash=self.cash
  for s,v in sv.items():sec[self.d.sid_sector[s]]+=v
  requests=[]
  for s,a in self.active.items():
   r=a.get('plan');a['plan']=None
   if r:requests.append(r)
  requests.sort(key=lambda r:(r['cp_date'],r['sid']));requests+=sorted(pending,key=lambda r:(r['signal_day'],r['sid']))
  reserved=[]
  for rank,r in enumerate(requests):
   s=r['sid'];a=self.active.get(s)
   if self.suspension(s,d):
    self.candidates.append(dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],decision='SUSPENDED_NONTRADABLE',allocation_rank=rank+1,cp_id=r.get('cp_id'),planned_q=r['planned_q'],executed_q=0));continue
   z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None
   if r['kind']=='ADD':
    if a is None or a['exit'] or any(l.get('exit') for l in a['lots']):reason='LOCKED_EXIT'
    elif a.get('cp') is None or a['cp']['id']!=r['cp_id'] or not self.cpvalid(a,a['cp'],z,'raw_open'):reason='CP_INVALID_OR_REPLACED'
    else:
     net=self.net(a,d,'raw_open')
     if net<=0:reason='OPEN_NET_NOT_POSITIVE'
     elif op*fac<=max(a['ifloor'],a['cp']['floor']):reason='OPEN_BELOW_PROTECTION'
    budget=min(r['budget'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_open'))) if a else ZERO
   else:
    if a is not None:reason='ALREADY_HELD'
    elif op*fac<=r['ifloor']:reason='OPEN_BELOW_PROTECTION'
    budget=r['budget']
   # Preserve baseline caps insertion order and hence exact tie labels for A.
   caps={'attempt_budget':budget,'stock_cap':max(ZERO,D('.10')*pre_nav-sv.get(s,ZERO))}
   if self.arm.sector_cap is not None:caps['sector_cap']=max(ZERO,self.arm.sector_cap*pre_nav-sec[self.d.sid_sector[s]])
   caps['cash_reserve']=max(ZERO,cash-D('.10')*pre_nav)
   q=0
   if reason=='PASS':
    if r['kind']=='SEED':
     q=self.d.getmeta(s,d)[0].buy_minimum
     if q>r['planned_q'] or q>r['capacity']:reason='DATED_LOT_OR_CAPACITY_CHANGED'
     elif q*p+self.d.fee(s,d,q,p,'buy')>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
    else:
     q=self.d.size(s,d,p,min(caps.values()),min(r['planned_q'],r['capacity']))
     if self.arm.progressive_add:
      before=q;q=add_quantity_limit(self.arm,self.d.getmeta(s,d)[0],q,self.quantity(a))
      self.add_quantity_log.append(dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'],baseline_q=before,current_round_q=self.quantity(a),limited_q=q,cp_id=r['cp_id'],planned_q=r['planned_q']))
     if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
   minq=self.d.getmeta(s,d)[0].buy_minimum;mincost=minq*p+self.d.fee(s,d,minq,p,'buy')
   violated=sorted(k for k,v in caps.items() if mincost>v)
   self.cap_violations.append(dict(day=day(d),sid=s,kind=r['kind'],ticket_id=r.get('ticket_id'),signal_day=r['signal_day'],plan_day=r.get('plan_day',r['signal_day']),allocation_rank=rank+1,decision=reason,minimum_all_in_cost=str(mincost),all_violated_caps=violated,**{k:str(v) for k,v in caps.items()}))
   row=dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],decision=reason,allocation_rank=rank+1,cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=str(net) if net is not None else None,planned_q=r['planned_q'],executed_q=q if reason=='PASS' else 0,**{k:str(v) for k,v in caps.items()});self.candidates.append(row)
   if reason!='PASS':
    if self.arm.retry_capital_seed and r['kind']=='SEED':
     eligible=seed_capital_failure('SEED',reason.startswith('MIN_LOT_CAPITAL_REJECT:'),mincost,caps)['retain'];t=self.retained.get(s)
     if eligible:
      if t is None:
       t=ticket_from_seed(r,mincost,caps);t['current_factor']=fac;t['last_verified_day']=day(d);self.retained[s]=t
      t['status']='RETAINED';t['plan']=None;self.retry_record(t,d,'OPEN','CAPITAL_REJECT_RETAIN',all_violated_caps=violated)
     elif t is not None:
      t['status']='CANCELLED';t['plan']=None;self.retry_record(t,d,'OPEN','NON_CAPITAL_REJECT_CANCEL',reason=reason,all_violated_caps=violated);self.retained.pop(s)
    continue
   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;sec[self.d.sid_sector[s]]+=cost;sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,net,cost))
  for r,q,p,net,cost in reserved:
   s=r['sid']
   if r['kind']=='SEED':
    self.seq[s]+=1;rid=f'{s}|{self.seq[s]}|{r["signal_day"]}';a=dict(id=rid,sid=s,signal_day=r['signal_day'],birth_type=r['birth_type'],nav0=r['nav0'],seed_day=day(d),cashflow=ZERO,dividend=ZERO,fees=ZERO,lots=[],ifloor=r['ifloor'],factor=dec(self.d.z(s,d)['adjustment_factor']),origin=r['origin'],exit=None,plan=None,cp=None,add_count=0);self.active[s]=a;self.archive[rid]=a
   else:a=self.active[s]
   cp=a['cp'] if r['kind']=='ADD' else None;fl=max(a['ifloor'],cp['floor']) if cp else a['ifloor'];lid=f'{a["id"]}|{len(self.orders)+1}'
   a['lots'].append(dict(id=lid,kind=r['kind'],q=q,bought=day(d),floor=fl,cp_id=cp['id'] if cp else None));self.order(a,d,'BUY_'+r['kind'],q,p,'NEW_A_B_MIN_UNIT' if not cp else 'STRENGTH_POSITIVE_UNCONSUMED_CP',signal_day=r['signal_day'],lot_id=lid,cp_id=cp['id'] if cp else None,close_net=r.get('close_net'),open_net=str(net) if net is not None else None,frozen_attempt_NAV=str(a['nav0']),all_in_cost=str(cost))
   if cp:cp['consumed']=True;a['add_count']+=1;self.eventlog(a,d,'OPEN','CONSUMED_ON_FILL',cp);a['cp']=None
   if self.arm.retry_capital_seed and s in self.retained:
    t=self.retained[s];assert not t['ever_seeded'];t['ever_seeded']=True;t['status']='CONSUMED';t['plan']=None;self.retry_record(t,d,'OPEN','ACTUAL_SEED_CONSUMED_ONCE',round_id=a['id'],executed_q=q);self.retained.pop(s)
 def scan_blocked_targets(self,d,pending):
  rows=super().scan_blocked_targets(d,pending)
  for r in rows:
   s=r['sid'];z=self.d.z(s,d);t=self.retained.get(s)
   if r['held_qty']==0 and t is not None and not open_known(z) and not (known_origin(z) and lineage(z)!=tuple(t['origin'])):
    r['availability_boundary']='EXISTING_Q0_RETAINED_TICKET_PAUSABLE';r['deferred_quote_issues']=[x for x in r['issues'] if x in ('OPEN_MISSING','FACTOR_MISSING_OR_INVALID')];r['issues']=[x for x in r['issues'] if x not in r['deferred_quote_issues']]
   if self.suspension(s,d):
    r['availability_boundary']='OFFICIAL_SUSPENSION_STALE_ACCOUNTING';r['issues']=[x for x in r['issues'] if x not in ('OPEN_MISSING','FACTOR_MISSING_OR_INVALID')]
  return rows
 def export_ablation(self,path):
  super().export_ablation(path)
  for name,value in [('SUSPENSION_EVENTS',self.suspension_log),('PREFLIGHT_CHECKS',self.preflight_log),('AVAILABILITY_EVENTS',self.availability),('QUOTE_GAPS',self.quote_gaps),('HELD_GAPS',self.held_gaps)]:base.save(path/(name+'.json'),value)
  base.save(path/'OUTPUT_HASHES.json',{p.name:base.sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
 def run_new(self,out,end,prefix_only=False):
  pending=[];prior=OLD/f'run_{self.arm.name}_fact2';old_end=base.read(prior/'RUN_STATUS.json')['certified_through'];passed=False
  keys=['cash','receivable','active','archive','seq','claims','snapshots','retained','quote_gaps','held_gaps'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','retry_log','extra_exits','add_quantity_log','cap_violations','availability','suspension_log','preflight_log']
  for d in self.d.days[self.d.days<=pd.Timestamp(end)]:
   prev=self.d.cal[self.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(self,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if day(d)==old_end:
     self.pending=pending;p=out/'prior_prefix_replay';self.export_ablation(p);counts={}
     for name in OLD_FAMILIES:
      got=base.read(p/(name+'.json'));old=base.read(prior/'full_prefix'/(name+'.json'));assert got==old,('OLD_SEMANTIC_PREFIX_MISMATCH',self.arm.name,name);counts[name]=len(got)
     assert not self.availability and not self.suspension_log and not self.preflight_log and not self.quote_gaps and not self.held_gaps
     base.save(out/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',through=old_end,exact_records=counts,new_logs_empty=True));passed=True;print('NEW_SEMANTIC_PREFIX_PASS '+self.arm.name+' '+old_end,flush=True)
     if prefix_only:break
    if day(d) in ('2024-09-30','2024-10-08'):
     self.pending=pending;self.export_ablation(out/('checkpoint_'+day(d)));print('CHECKPOINT '+self.arm.name+' '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:])
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    pending=p0;self.blockers.append(str(ex));self.blocked_targets=self.scan_blocked_targets(d,pending);break
  self.pending=pending;self.export_ablation(out/'full_prefix');base.save(out/'RUN_STATUS.json',dict(arm=self.arm.name,new_semantics=True,not_fact_only=True,prior_prefix_exact=passed,days=len(self.ledger),orders=len(self.orders),last=self.ledger[-1] if self.ledger else None,blockers=self.blockers));return self

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['freeze','run'],required=True);ap.add_argument('--arms',default='A,E,F,B,D');ap.add_argument('--prefix-only',action='store_true');args=ap.parse_args()
 assert base.read(O/'SYNTHETIC_QA.json')['result']=='PASS'
 data=Data()
 if args.mode=='freeze':
  assert not (O/'FREEZE.json').exists();base.save(O/'FREEZE.json',dict(hashes=data.hashes,explicit_new_accounting_availability_semantics=True,old_implementation_hashes=base.read(OLD/'EXECUTION_FREEZE.json')['implementation_hashes']));print('FROZEN',len(data.hashes),flush=True)
 else:
  f=base.read(O/'FREEZE.json');assert data.hashes==f['hashes'];assert all(base.sha(p)==h for p,h in f['old_implementation_hashes'].items());assert base.read(O/'APPROVAL.json')['approved']
  for arm in args.arms.split(','):
   end='2024-10-08' if arm in ('B','D') else '2024-10-25';out=O/f'run_{arm}';out.mkdir(exist_ok=False);e=Engine(data,arm).run_new(out,end,prefix_only=args.prefix_only);print('RESULT '+json.dumps(base.read(out/'RUN_STATUS.json')),flush=True)
