"""Frozen M4 event/representative candidate. Research only, no production orders."""
from pathlib import Path
import sys,importlib.util,copy,json,inspect,ast,argparse,types
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;V3=ROOT/'mainline_candidate_v3_core_reference'
def module(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
m3=module('m4_frozen_m3',V3/'engine.py');m2=m3.m2;v1=m3.v1;b=m3.b
D=m3.D;ZERO=m3.ZERO;INITIAL=m3.INITIAL;SLIP=m3.SLIP;pd=m3.pd;np=m3.np;dec=m3.dec;day=m3.day;finite=m3.finite;truth=m3.truth;false=m3.false;valid=m3.valid;lineage=m3.lineage;sha=m3.sha;save=m3.save;read=m3.read;Blocked=m3.Blocked
assert sha(V3/'engine.py')=='690a3cde9121c50e5b994d79c45049441cc89a2ad47ddb478ab27ae7e05b0a7b'
rules=types.ModuleType('m4_rules');sys.modules[rules.__name__]=rules
exec(compile((ROOT/'allocation_ablation_v1/allocation_rules.py').read_text().replace("{'cash_reserve', 'sector_cap'}","{'cash_reserve', 'reference_cap', 'event_cap'}"),'m4_retention_keys','exec'),rules.__dict__)

class Data(m3.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)

class Engine(m3.Engine):
 def __init__(self,data):
  super().__init__(data);self.events={};self.current_event={};self.event_log=[];self.event_plans=[];self.seed_floor_risk=[];self.seed_execution_cost=[];self._event_open_reserved={};self._execution_requests={};self._donor_sectors=set();self._probe_receiver_sectors=set();self._score_cache={}
 def next_day(self,d):return self.d.cal[self.d.cal.get_loc(d)+1]
 def log_event(self,e,d,action,**kw):
  self.event_log.append(dict(day=day(d),event=action,event_id=e['event_id'],sector51=e['sector51'],birth_day=e['birth_day'],budget_anchor=e['budget_anchor'],birth_NAV=str(e['birth_NAV']),capital_cap=str(e['capital_cap']),priority_attempted=e['priority_attempted'],spent=str(e['spent']),reserved=str(e['reserved']),**kw))
 def create_event(self,sec,birth,d,nav,cold=False):
  eid=sec+'|'+day(birth);assert eid not in self.events
  e=dict(event_id=eid,sector51=sec,birth_day=day(birth),budget_anchor='INITIAL_ACCOUNT_OPEN_ONCE' if cold else 'ACTUAL_BIRTH_CLOSE_NAV',birth_NAV=nav,capital_cap=D('.02')*nav,priority_attempted=False,priority_attempt_day=None,priority_reserved_day=None,priority_expired=False,spent=ZERO,reserved=ZERO,status='ACTIVE',cold_start=cold)
  self.events[eid]=e;self.current_event[sec]=eid;self.log_event(e,d,'COLD_EVENT_INITIALIZED' if cold else 'NEW_FALSE_TRUE_EVENT');return e
 def sync_events(self,d):
  first=d==self.d.days[0];prev=self.d.cal[self.d.cal.get_loc(d)-1];nav=self.nav(d,'raw_close')
  for sec in self.d.sector_ids:
   fr=self.d.sectors[sec];now=int(fr.at[d,'state']);before=int(fr.at[prev,'state']);eid=self.current_event.get(sec)
   if first:
    hist=fr.loc[:d];births=hist.index[hist.state.eq(1)&hist.state.shift().eq(0)]
    if len(births):
     born=births[-1]
     if hist.loc[born:].state.eq(1).all():self.create_event(sec,born,d,INITIAL if born<d else nav,born<d)
   elif before==0 and now==1:self.create_event(sec,d,d,nav)
   eid=self.current_event.get(sec)
   if not eid:continue
   e=self.events[eid];e['reserved']=ZERO
   if e['cold_start'] and day(d)>day(self.d.days[0]) and e['priority_reserved_day'] is None:e['priority_expired']=True
   e['status']='CLOSED_FALSE' if now==0 else 'PAUSED_UNKNOWN' if now==-1 else 'ACTIVE'
   self.log_event(e,d,'CLOSE_EVENT_STATUS',sector_state=now)
 def surcharge(self,s,d,q,C):
  _,fs,pa=self.d.getmeta(s,d);out=ZERO
  for side,p in [('buy',C*(1+SLIP)),('sell',C*(1-SLIP))]:
   actual=fs.incremental(side,q*p,{}, {},1,shares=q,par_value=pa);rate=fs.rate_accrual(side,q*p,1,shares=q,par_value=pa)
   for c in fs.components:
    if c.name=='net_brokerage' and c.side in ('both',side):out+=max(ZERO,actual[c.name]-rate[c.name])
  return out
 def economic_q(self,s,d,C,capacity):
  qr=self.d.getmeta(s,d)[0];maxq=qr.buy_floor(int(capacity))
  if not maxq:return 0
  ok=lambda q:self.surcharge(s,d,q,C)<=2*SLIP*q*C
  if not ok(maxq):return 0
  lo=0;hi=(maxq-qr.buy_minimum)//qr.buy_step
  while lo<hi:
   mid=(lo+hi)//2
   if ok(qr.buy_minimum+mid*qr.buy_step):hi=mid
   else:lo=mid+1
  return qr.buy_minimum+lo*qr.buy_step
 def representative_score(self,s,d):
  key=(s,d)
  if key in self._score_cache:return self._score_cache[key]
  ix=self.d.cal.get_loc(d);ds=self.d.cal[ix-5:ix+1];z=self.d.raw[s].reindex(ds);answer=None
  if len(z)==6:
   ok=True;origin=None
   for _,r in z.iterrows():
    if not valid(r) or not all(finite(r.get(c)) and r[c]>0 for c in ['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']):ok=False;break
    if origin is None:origin=lineage(r)
    if lineage(r)!=origin or abs(dec(r.raw_close)*dec(r.adjustment_factor)/dec(r.close)-1)>D('1e-10'):ok=False;break
   median=self.d.main[self.d.sid_sector[s]].loc[d].return5_median
   if ok and finite(median):
    ret=dec(z.iloc[-1].close)/dec(z.iloc[0].close)-1;streak=0
    for x in reversed(self.d.stock.loc[:d,s].tolist()):
     if x!=1:break
     streak+=1
    answer=(ret-dec(median),streak)
  self._score_cache[key]=answer;return answer
 def current_trial_seed(self,a,d):
  if any(l['kind']!='SEED' for l in a['lots']):return False
  s=a['sid'];m=self.d.m(s,d);f=self.d.f(s,d);c=self.d.c(s,d);z=self.d.z(s,d)
  return m.M==0 and finite(m.E) and int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']) in [0,1] and int(self.d.stock.at[d,s]) in [0,1] and (truth(f.get('i_target')) or false(f.get('i_target'))) and (not truth(f.get('i_target')) or finite(f.get('i_floor')) and f['i_floor']>0) and (truth(c.get('receipt')) or false(c.get('receipt'))) and valid(z) and lineage(z)==a['origin']
 def close(self,d,prev):
  for s,a in self.active.items():
   if self.current_trial_seed(a,d) and int(self.d.sectors[self.d.sid_sector[s]].at[d,'state'])==0:a['exit']=a['exit'] or 'CURRENT_SEED_TRIAL_SECTOR_FALSE'
  return super().close(d,prev)
 def prepare_requests(self,d,reqs):
  nxt=self.next_day(d)
  for r in reqs:
   r['_ref_q']=0;s=r['sid'];sec=self.d.sid_sector[s];t=self.live_tickets().get(s);old_id=r.get('event_id') or (t.get('event_id') if t else None);current_id=self.current_event.get(sec);r['event_id']=old_id or current_id;e=self.events.get(r['event_id']);r['_event_identity_mismatch']=bool(old_id and old_id!=current_id);r['allocation_phase']='MATURE' if r['kind']=='ADD' else 'PAUSED'
   if r['kind']!='SEED':continue
   r['original_minimum_q']=r['planned_q'];C=dec(self.d.z(s,d)['raw_close']);q=self.economic_q(s,nxt,C,r['capacity']);sc=self.representative_score(s,d);r['econ_q']=q;r['planned_q']=q;r['score_known']=sc is not None;r['stock_excess5']=sc[0] if sc else None;r['stock_true_streak']=sc[1] if sc else None;r['capacity_value']=r['capacity']*C;r['close_surcharge']=self.surcharge(s,nxt,q,C) if q else None;r['close_slippage_comparator']=2*SLIP*q*C if q else None
   active=e is not None and e['status']=='ACTIVE' and not r['_event_identity_mismatch'];newpriority=active and not e['priority_attempted'] and not e['priority_expired']
   if newpriority and r['M']!=-1 and (r['M']==0 or r['E']>0):r['allocation_phase']='EVENT'
   elif r['M']==1 and r['E']>0 and active:r['allocation_phase']='MATURE'
   elif r['M']==0 and active:r['allocation_phase']='RESIDUAL'
   r['_priority_candidate']=r['allocation_phase']=='EVENT' and q>0 and sc is not None
   if r['_priority_candidate']:
    e['priority_reserved_day']=day(d);self.log_event(e,d,'PRIORITY_STRUCTURAL_CLOSE_PLAN',sid=s,original_signal_day=r['signal_day'],econ_q=q)
  return reqs
 def stock_key(self,r):return (-r['stock_excess5'],-r['stock_true_streak'],-r['capacity_value'],r['signal_day'],r['sid'])
 def noncash(self,r,d,field,nav,sv):
  if r['kind']!='SEED':return super().noncash(r,d,field,nav,sv)
  s=r['sid'];z=self.d.z(s,d);raw=dec(z[field]);p=raw*(1+SLIP);q=r.get('econ_q',0);qr=self.d.getmeta(s,d if field=='raw_open' else self.next_day(d))[0];reason='PASS';caps=dict(attempt_budget=r['budget'],stock_cap=max(ZERO,D('.1')*nav-sv.get(s,ZERO)));when=d if field=='raw_open' else self.next_day(d)
  if s in self.active:reason='ALREADY_HELD'
  elif raw*dec(z['adjustment_factor'])<=r['ifloor']:reason='OPEN_BELOW_PROTECTION'
  elif q<=0:reason='ECONOMIC_Q_CAPACITY_UNAVAILABLE'
  elif q>r['planned_q'] or q>r['capacity'] or qr.buy_floor(q)!=q:reason='DATED_LOT_OR_CAPACITY_CHANGED'
  elif q*p+self.d.fee(s,when,q,p,'buy')>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
  return dict(q=q if reason=='PASS' else 0,reason=reason,p=p,net=None,caps=caps,structural=reason=='PASS' or reason.startswith('MIN_LOT_CAPITAL_REJECT'))
 def event_cap(self,r,extra=None):
  if r.get('allocation_phase') not in ['EVENT','RESIDUAL']:return D('Infinity')
  e=self.events.get(r.get('event_id'));extra=self._event_open_reserved if extra is None else extra
  return max(ZERO,e['capital_cap']-e['spent']-extra.get(e['event_id'],ZERO)) if e else ZERO
 def reference_cap(self,r,sv,spent=None):
  if r.get('_ref_q',0)<=0:return ZERO
  phase=r.get('allocation_phase')
  if phase in ['EVENT','RESIDUAL']:
   if phase=='RESIDUAL' and self.d.sid_sector[r['sid']] in self._donor_sectors:return ZERO
   return D('Infinity')
  if phase!='MATURE' or r['M']!=1:return ZERO
  return super().reference_cap(r,sv,spent)
 def classify_reference(self,d):
  before_lots=len(self.capital_lots);before_refs=len(self.reference_log);ref=super().classify_reference(d);del self.capital_lots[before_lots:];del self.reference_log[before_refs:];fixed=dict(ref['sector_value']);stress=ZERO;nxt=self.next_day(d)
  for r in ref['rows']:
   a=self.active[r['sid']];qr=self.d.getmeta(r['sid'],nxt)[0];mobile=r['mobile_qty'];current_trial=self.current_trial_seed(a,d);r['sector_state']=int(self.d.sectors[r['sector51']].at[d,'state'])
   if r['sector_state']==-1:
    r['unknown'].append('SECTOR_M3_UNKNOWN');mobile=0
   if current_trial and not r['unknown'] and not r['locked'] and nxt>pd.Timestamp(r['bought']):
    mobile=qr.sell_floor(r['qty'],self.quantity(a));mobile=mobile if mobile==r['qty'] else 0;r['donor_reason']='CURRENT_NON_MAINLINE_SEED_RETIREMENT'
   if r['sector51'] in self._probe_receiver_sectors:mobile=0
   r['prior_mobile_qty']=r['mobile_qty'];r['current_trial_seed']=current_trial;r['mobile_qty']=mobile;r['mobile_value']=mobile*r['raw_mark'];r['frozen_qty']=r['qty']-mobile;r['frozen_value']=r['frozen_qty']*r['raw_mark'];r['mobile_sell_stress']=mobile*r['raw_mark']-(mobile*r['raw_mark']*(1-SLIP)-self.d.fee(r['sid'],nxt,mobile,r['raw_mark']*(1-SLIP),'sell')) if mobile else ZERO;fixed[r['sector51']]-=r['mobile_value'];stress+=r['mobile_sell_stress']
  outside=sum((v for sec,v in fixed.items() if sec not in ref['E']),ZERO);budget=ref['NAV']-ref['reserve']-self.receivable-outside-stress;ref.update(fixed=fixed,lower={sec:fixed[sec] for sec in ref['E']},stress=stress,outside_fixed=outside,budget_before_event=budget,budget=budget,event_reserve=ZERO,event_by_sector={},frozen_lot_qty={r['lot_id']:r['frozen_qty'] for r in ref['rows']});return ref
 def finalize_reference(self,d,event_by_sector):
  ref=self.reference;reserved=sum(event_by_sector.values(),ZERO);budget=ref['budget_before_event']-reserved;targets,lam,status=m3.water(ref['lower'],ref['E'],budget);residual=dict(ref['fixed']);residual.update(targets);total={sec:residual[sec]+event_by_sector.get(sec,ZERO) for sec in self.d.sector_ids};envelope={sec:max(ZERO,residual[sec]-ref['sector_value'][sec]) if status=='PASS' and sec in ref['E'] else ZERO for sec in self.d.sector_ids};ref.update(budget=budget,event_reserve=reserved,event_by_sector=dict(event_by_sector),T_residual=residual,T=total,lambda_value=lam,status=status,envelope=envelope)
  assert reserved<=max(ZERO,ref['budget_before_event']-sum(ref['lower'].values(),ZERO))
  self.capital_lots.extend(ref['rows'])
  for sec in self.d.sector_ids:
   z=self.d.main[sec].loc[d];self.reference_log.append(dict(day=day(d),sector51=sec,M=int(z.M),E=dec(z.E) if finite(z.E) else None,actual_value=ref['sector_value'][sec],core=ref['core'][sec],other_frozen=ref['fixed'][sec]-ref['core'][sec],fixed=ref['fixed'][sec],T=total[sec],T_mature_residual=residual[sec],event_reserved=event_by_sector.get(sec,ZERO),buy_envelope=envelope[sec],budget_before_event=ref['budget_before_event'],event_reserve_total=reserved,budget=budget,stress=ref['stress'],receivable=self.receivable,outside_fixed=ref['outside_fixed'],status=status,lambda_value=lam))
 def plan_requests(self,d,reqs):
  ref=self.reference;nav=ref['NAV'];sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};event_remaining={eid:max(ZERO,e['capital_cap']-e['spent']) for eid,e in self.events.items()};event_by_sector={};event_credit=max(ZERO,ref['budget_before_event']-sum(ref['lower'].values(),ZERO));event_total=ZERO;ordered=[];details=[];nxt=self.next_day(d)
  def reserve(r,q,cost,reason):
   r['_ref_q']=q;r['_reference_close_cost']=cost;r['_ref_rank']=len(ordered)+1;ordered.append(r);s=r['sid'];sec=self.d.sid_sector[s]
   details.append(dict(day=day(d),phase='CLOSE',sid=s,sector51=sec,kind=r['kind'],M=r['M'],E=r['E'],cp_id=r.get('cp_id'),signal_day=r['signal_day'],rank=r['_ref_rank'],base_planned_q=r['planned_q'],reference_q=q,all_in_cost=cost,decision=reason,allocation_phase=r['allocation_phase'],event_id=r.get('event_id'),econ_q=r.get('econ_q'),priority_candidate=r.get('_priority_candidate',False),stock_excess5=r.get('stock_excess5'),stock_true_streak=r.get('stock_true_streak'),capacity_value=r.get('capacity_value')))
  queues={sec:sorted([r for r in reqs if r.get('_priority_candidate') and self.d.sid_sector[r['sid']]==sec],key=self.stock_key) for sec in self.d.sector_ids}
  while any(queues.values()):
   secs=sorted([s for s in queues if queues[s]],key=lambda sec:(self.events[self.current_event[sec]]['birth_day'],-dec(self.d.sectors[sec].at[d,'n'])/dec(self.d.sectors[sec].at[d,'N']),-dec(self.d.sectors[sec].at[d,'diff'])/dec(self.d.sectors[sec].at[d,'N']),sec))
   for sec in secs:
    while queues[sec]:
     r=queues[sec].pop(0);x=self.noncash(r,d,'raw_close',nav,sv);q=x['q'];cost=q*x['p']+self.d.fee(r['sid'],nxt,q,x['p'],'buy') if q else ZERO;reason=x['reason'];eid=r['event_id']
     if q and cost>event_remaining[eid]:q=0;cost=ZERO;reason='EVENT_CAP'
     if q and event_total+cost>event_credit:q=0;cost=ZERO;reason='CORE_BUDGET_LIMIT'
     reserve(r,q,cost,reason)
     if q:
      event_remaining[eid]-=cost;event_total+=cost;event_by_sector[sec]=event_by_sector.get(sec,ZERO)+cost;sv[r['sid']]=sv.get(r['sid'],ZERO)+cost;break
  self.finalize_reference(d,event_by_sector)
  remaining=[r for r in reqs if r['allocation_phase']=='MATURE' and r not in ordered];spent={}
  while remaining:
   sectors=self.sector_values(sv);heads=[]
   for sec in sorted({self.d.sid_sector[r['sid']] for r in remaining}):
    rs=[r for r in remaining if self.d.sid_sector[r['sid']]==sec];adds=[r for r in rs if r['kind']=='ADD'];knownseed=[r for r in rs if r['kind']=='SEED' and r.get('score_known')]
    heads.append(min(adds,key=lambda r:(r.get('cp_date',r['signal_day']),r['sid'])) if adds else min(knownseed,key=self.stock_key) if knownseed else min(rs,key=lambda r:(r['signal_day'],r['sid'])))
   r=min(heads,key=lambda r:(-max(ZERO,ref['T'][self.d.sid_sector[r['sid']]]-sectors[self.d.sid_sector[r['sid']]]),-r['M_streak'],-r['E'],r.get('cp_date',r['signal_day']),r['sid']));remaining.remove(r);s=r['sid'];sec=self.d.sid_sector[s];x=self.noncash(r,d,'raw_close',nav,sv);q=x['q'];cap=max(ZERO,min(ref['T'][sec]-sectors[sec],ref['envelope'][sec]-spent.get(sec,ZERO)));reason=x['reason']
   if r['kind']=='SEED':
    cost=q*x['p']+self.d.fee(s,nxt,q,x['p'],'buy') if q else ZERO
    if not r.get('score_known'):q=0;reason='REPRESENTATIVE_UNKNOWN'
    elif cost>cap:q=0;reason='REFERENCE_CAP'
   else:q=self.d.size(s,nxt,x['p'],min(min(x['caps'].values()),cap),q) if q else 0;reason=reason if reason!='PASS' else 'PASS' if q else 'REFERENCE_CAP'
   cost=q*x['p']+self.d.fee(s,nxt,q,x['p'],'buy') if q else ZERO;reserve(r,q,cost,reason)
   if q:sv[s]=sv.get(s,ZERO)+cost;spent[sec]=spent.get(sec,ZERO)+cost
  residual=[r for r in reqs if r['allocation_phase']=='RESIDUAL' and r not in ordered]
  residual.sort(key=lambda r:(self.events[r['event_id']]['birth_day'],self.d.sid_sector[r['sid']],self.stock_key(r) if r.get('score_known') else (D('Infinity'),0,0,r['signal_day'],r['sid'])))
  for r in residual:
   x=self.noncash(r,d,'raw_close',nav,sv);q=x['q'];cost=q*x['p']+self.d.fee(r['sid'],nxt,q,x['p'],'buy') if q else ZERO;reason=x['reason'];eid=r['event_id']
   if not r.get('score_known'):q=0;reason='REPRESENTATIVE_UNKNOWN'
   elif cost>event_remaining[eid]:q=0;reason='EVENT_CAP'
   cost=cost if q else ZERO;reserve(r,q,cost,reason)
   if q:event_remaining[eid]-=cost
  for r in reqs:
   if r not in ordered:reserve(r,0,ZERO,'REPRESENTATIVE_UNKNOWN' if r['kind']=='SEED' and not r.get('score_known') else 'NO_ACTIVE_PHASE')
  for e in self.events.values():e['reserved']=sum((r['_reference_close_cost'] for r in ordered if r.get('event_id')==e['event_id'] and r['allocation_phase'] in ['EVENT','RESIDUAL']),ZERO)
  self.reference_requests.extend(details);self.event_plans.extend(copy.deepcopy(details));return ordered,details
 def demand(self,reqs,d,field,nav,sv):
  total=ZERO;details=[];sv=dict(sv);spent={};eventspent={};when=d if field=='raw_open' else self.next_day(d)
  for r in self.request_key_groups(reqs):
   if r.get('allocation_phase') not in ['EVENT','MATURE']:continue
   x=self.noncash(r,d,field,nav,sv);cap=min(self.reference_cap(r,sv,spent),self.event_cap(r,eventspent));q=min(x['q'],r.get('_ref_q',0));p=x['p'];s=r['sid'];phase=r['allocation_phase']
   if r['kind']=='SEED':q=q if q and q*p+self.d.fee(s,when,q,p,'buy')<=cap else 0
   else:q=self.d.size(s,when,p,min(min(x['caps'].values()),cap),q) if q else 0
   cost=q*p+self.d.fee(s,when,q,p,'buy') if q else ZERO;total+=cost;sec=self.d.sid_sector[s];sv[s]=sv.get(s,ZERO)+cost
   if phase=='MATURE':spent[sec]=spent.get(sec,ZERO)+cost
   else:eventspent[r['event_id']]=eventspent.get(r['event_id'],ZERO)+cost
   details.append(dict(sid=s,kind=r['kind'],allocation_phase=phase,event_id=r.get('event_id'),q=q,cost=str(cost),reason=x['reason'] if x['reason']!='PASS' else 'PASS' if q else 'REFERENCE_OR_EVENT_CAP'))
  return total,details
 def plan_transfers(self,d,pending):
  self.sync_events(d);reqs=self.prepare_requests(d,[a['plan'] for a in self.active.values() if a.get('plan')]+pending)
  self._probe_receiver_sectors={self.d.sid_sector[r['sid']] for r in reqs if r.get('_priority_candidate')};self.reference=self.classify_reference(d);reqs,detail=self.plan_requests(d,reqs);nav=self.reference['NAV'];sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};cash=self.cash;nxt=self.next_day(d)
  for s,a in self.active.items():
   q=sum(l['q'] for l in a['lots'] if (a['exit'] or l.get('exit')) and nxt>pd.Timestamp(l['bought']))
   if q:p=dec(self.d.z(s,d)['raw_close'])*(1-SLIP);cash+=q*p-self.d.fee(s,nxt,q,p,'sell')
  desired,receivers=self.demand(reqs,d,'raw_close',nav,sv);gap=max(ZERO,desired+self.reference['reserve']-cash) if desired>0 else ZERO;initial=gap;sector=dict(self.reference['sector_value']);receiving={self.d.sid_sector[r['sid']] for r in reqs if r['allocation_phase'] in ['EVENT','MATURE'] and r['_ref_q']>0};pool=[r for r in self.reference['rows'] if r['mobile_qty']>0 and r['sector51'] not in receiving];self.transfer_plan=[]
  def floor(sec):return max(self.reference['fixed'][sec],self.reference['T'][sec])
  while pool and gap>0:
   def key(r):
    tier=0 if r['kind']=='SEED' else 1 if r['donor_reason']=='WEAK_SECTOR_ADD_LAYER' else 2
    return (tier,r['stock_state']!=0 if tier==0 else False,r['E'] if tier==0 else -max(ZERO,sector[r['sector51']]-floor(r['sector51'])) if tier==2 else ZERO,r['E'] if tier==2 else ZERO,r['bought'],r['sid'],r['lot_id'])
   r=min(pool,key=key);pool.remove(r);sec=r['sector51'];s=r['sid'];a=self.active[s];qr=self.d.getmeta(s,nxt)[0];surplus=max(ZERO,sector[sec]-floor(sec));maxq=qr.sell_floor(min(r['mobile_qty'],int(surplus/r['raw_mark'])),self.quantity(a));p=r['raw_mark']*(1-SLIP)
   q=maxq if r['kind']=='SEED' and maxq==r['qty'] else 0 if r['kind']=='SEED' else self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))
   if not q:continue
   proceeds=q*p-self.d.fee(s,nxt,q,p,'sell');rank=len(self.transfer_plan)+1;pl=dict(signal_day=day(d),sid=s,sector51=sec,round_id=a['id'],lot_id=r['lot_id'],max_q=q,reason=r['donor_reason'],rank=rank,close_estimated_net=str(proceeds),initial_gap=str(initial),gap_before=str(gap),close_sector_floor=str(floor(sec)),frozen_lot_qty=r['frozen_qty']);self.transfer_plan.append(pl);sector[sec]-=q*r['raw_mark'];gap=max(ZERO,gap-proceeds);self.transfers.append(dict(day=day(d),phase='CLOSE',event='DONOR_PLANNED',**pl,remaining_gap=str(gap)))
  self._donor_sectors={r['sector51'] for r in self.transfer_plan};self.transfers.append(dict(day=day(d),phase='CLOSE',event='DEMAND_PLAN',M_desired_cost=str(desired),cash_after_known_protection=str(cash),reserve=str(self.reference['reserve']),initial_gap=str(initial),remaining_gap=str(gap),receivers=receivers,planned_donors=len(self.transfer_plan),includes_once_priority_events=True))
 def begin_open(self,d,pending):
  self._event_open_reserved={};self._execution_requests={r['sid']:r for r in pending}
  for a in self.active.values():
   if a.get('plan'):self._execution_requests[a['sid']]=a['plan']
  for r in pending:
   if not r.get('_priority_candidate'):continue
   e=self.events[r['event_id']]
   if not e['priority_attempted'] and m2.open_known(self.d.z(r['sid'],d)):
    e['priority_attempted']=True;e['priority_attempt_day']=day(d);self.log_event(e,d,'PRIORITY_REAL_OPEN_ATTEMPT',sid=r['sid'],plan_day=r['plan_day'],priority_before=False,priority_after=True,capital_approval_required=False)
 def reserve_phase_cash(self,r,cost):
  if r['allocation_phase']=='MATURE':sec=self.d.sid_sector[r['sid']];self._ref_spent[sec]=self._ref_spent.get(sec,ZERO)+cost
  elif r['allocation_phase'] in ['EVENT','RESIDUAL']:eid=r['event_id'];self._event_open_reserved[eid]=self._event_open_reserved.get(eid,ZERO)+cost
 def pause_unknown_ticket(self,t,r,reason):
  super().pause_unknown_ticket(t,r,reason)
  if r['kind']=='SEED' and not r.get('score_known',True) and t['status']=='RETAINED':t['status']='PAUSED';t['reason']='REPRESENTATIVE_SCORE_UNKNOWN'
  if r.get('_event_identity_mismatch') and t['status']=='RETAINED':t['status']='PAUSED';t['reason']='IMMUTABLE_EVENT_ID_MISMATCH'
  if r.get('event_id'):
   if t.get('event_id'):assert t['event_id']==r['event_id']
   t['event_id']=r['event_id']
 def order(self,a,d,side,q,p,reason,**kw):
  fee=super().order(a,d,side,q,p,reason,**kw)
  if side=='BUY_SEED':
   r=self._execution_requests[a['sid']];cost=-dec(self.orders[-1]['cash_delta']);e=self.events.get(r.get('event_id'));phase=r['allocation_phase'];self.orders[-1].update(allocation_phase=phase,event_id=r.get('event_id'),frozen_econ_q=r.get('econ_q'),close_estimated_all_in=str(r.get('_reference_close_cost')),plan_day=r['plan_day'],open_actual_cost=str(cost),open_minus_close_cost=str(cost-r.get('_reference_close_cost',ZERO)))
   if phase in ['EVENT','RESIDUAL']:
    assert e is not None and e['spent']+cost<=e['capital_cap'];spent_before=e['spent'];e['spent']+=cost;self.log_event(e,d,'ACTUAL_SEED_CAPITAL_CONSUMED',sid=a['sid'],phase=phase,actual_cost=str(cost),qty=q,plan_day=r['plan_day'],spent_before=str(spent_before),spent_after=str(e['spent']),close_reserved_cost=str(r.get('_reference_close_cost')),open_actual_cost=str(cost),open_minus_close_cost=str(cost-r.get('_reference_close_cost',ZERO)))
   else:
    if e:self.log_event(e,d,'MATURE_SEED_NO_EVENT_DEBIT',sid=a['sid'],actual_cost=str(cost),qty=q)
   raw=dec(self.d.z(a['sid'],d)['raw_open']);stop=a['ifloor']/a['factor']*(1-SLIP);loss=cost-(q*stop-self.d.fee(a['sid'],d,q,stop,'sell'));self.seed_floor_risk.append(dict(day=day(d),sid=a['sid'],round_id=a['id'],allocation_phase=phase,event_id=r.get('event_id'),qty=q,buy_all_in=str(cost),known_protection=str(a['ifloor']),hypothetical_raw_sell=str(stop),incremental_known_floor_loss=str(loss),new_principal_risk=True,not_stop_execution_guarantee=True));extra=self.surcharge(a['sid'],d,q,raw);threshold=2*SLIP*q*raw;self.seed_execution_cost.append(dict(day=day(d),sid=a['sid'],qty=q,frozen_econ_q=r.get('econ_q'),open_surcharge=str(extra),open_slippage_comparator=str(threshold),excess=str(max(ZERO,extra-threshold)),not_an_OPEN_gate=True))
  return fee
 def run(self,checkpoint=True):return run_loop(self,checkpoint)
 def export(self,path):
  super().export(path)
  for name,value in [('EVENT_LOG',self.event_log),('EVENT_REQUEST_PLANS',self.event_plans),('SEED_FLOOR_RISK',self.seed_floor_risk),('SEED_COMMISSION_DIAGNOSTIC',self.seed_execution_cost)]:save(path/(name+'.json'),value);pd.DataFrame(value).to_csv(path/(name+'.csv'),index=False)
  save(path/'EVENT_REGISTRY.json',self.events);save(path/'CURRENT_EVENT.json',self.current_event);save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

# Materialize the reviewed M3 allocator with only explicit integration hooks.
def replace_once(text,old,new):
 assert text.count(old)==1,('HOOK_NOT_UNIQUE',old,text.count(old))
 return text.replace(old,new)
source=inspect.getsource(m3.Engine.alloc_open)
source=replace_once(source,' def alloc_open(self,d,pending):','def alloc_open(self,d,pending):')
source=replace_once(source,'  self._ref_spent={};self.info_open(d);','  self.begin_open(d,pending);self._ref_spent={};self.info_open(d);')
source=replace_once(source,'reference_cap=self.reference_cap(r,sv))','reference_cap=self.reference_cap(r,sv),event_cap=self.event_cap(r))')
source=replace_once(source,"rawq=qr.buy_minimum if r['kind']=='SEED' else q","rawq=r.get('econ_q',qr.buy_minimum) if r['kind']=='SEED' else q")
source=replace_once(source,"self._ref_spent[self.d.sid_sector[s]]=self._ref_spent.get(self.d.sid_sector[s],ZERO)+cost;","self.reserve_phase_cash(r,cost);")
source=replace_once(source,"reference_close_rank=r.get('_ref_rank'),","reference_close_rank=r.get('_ref_rank'),allocation_phase=r.get('allocation_phase'),event_id=r.get('event_id'),frozen_econ_q=r.get('econ_q'),")
namespace=dict(globals());exec(compile(source,'M4_allocator_explicit_hooks','exec'),namespace);Engine.alloc_open=namespace['alloc_open']

def run_loop(e,checkpoint=True,prefix='checkpoint'):
 pending=[];keys=['cash','receivable','active','archive','seq','claims','snapshots','tickets','transfer_plan','quote_gaps','reference','_ref_spent'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','ticket_log','confirmations','transfers','request_details','floor_risk','open_exposure','availability','reference_log','capital_lots','reference_requests']
 if isinstance(e,Engine):keys+=['events','current_event','_event_open_reserved','_execution_requests','_donor_sectors','_probe_receiver_sectors'];logs+=['event_log','event_plans','seed_floor_risk','seed_execution_cost']
 for d in e.d.days:
  prev=e.d.cal[e.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(e,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(e,k)) for k in logs}
  try:
   e.economic_preflight(d,pending);e.accrue(d);e.exit_open(d);e.alloc_open(d,pending);pending=e.close(d,prev)
   if checkpoint and day(d) in ['2024-09-23','2024-09-27','2024-09-30','2024-10-08']:
    e.pending=pending;e.export(O/(prefix+'_'+day(d).replace('-','')));print('CHECKPOINT '+json.dumps(e.ledger[-1]),flush=True)
  except Blocked as ex:
   e.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=e.orders[lengths['orders']:])
   for k,v in snap.items():setattr(e,k,v)
   for k,n in lengths.items():del getattr(e,k)[n:]
   pending=p0;e._preflight_excluded=set();e.all_blockers=e.scan_restored_targets(d,pending);e.blockers.append(str(ex));print('ATOMIC_BLOCK '+str(ex),flush=True);break
  print('DAY '+day(d)+' orders='+str(len(e.orders))+' tickets='+str(len(e.live_tickets()))+' NAV='+e.ledger[-1]['NAV'],flush=True)
 e.pending=pending;return e

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['replay','run'],required=True);args=ap.parse_args()
 if args.mode=='replay':
  data=m3.Data();e=run_loop(m3.Engine(data),False);e.export(O/'m3_replay_20241008');families=m2.BASE_FAMILIES+['AVAILABILITY_EVENTS','QUOTE_GAPS','REFERENCE_DAILY','CAPITAL_LOTS','REFERENCE_REQUESTS','REFERENCE_AT_END'];counts={}
  for n in families:
   aa=read(O/'m3_replay_20241008'/(n+'.json'));bb=read(V3/'once_20241008'/(n+'.json'));assert aa==bb or (n=='AVAILABILITY_EVENTS' and __import__('collections').Counter(json.dumps(r,sort_keys=True) for r in aa)==__import__('collections').Counter(json.dumps(r,sort_keys=True) for r in bb)),('M3_REPLAY_MISMATCH',n);counts[n]=dict(count=len(aa),comparison='exact_ordered' if aa==bb else 'full_record_multiset_only_unordered_diagnostic')
  save(O/'M3_EXACT_REPLAY_QA.json',dict(result='PASS',days=20,orders=len(e.orders),families=counts));print('M3_EXACT_REPLAY_PASS')
 else:
  approval=read(O/'CONTRACT_APPROVAL.json');assert approval['approved'];assert approval['engine_sha256']==sha(O/'engine.py');assert approval['contract_sha256']==sha(O/'CONTRACT.md');assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert read(O/'M3_EXACT_REPLAY_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')));save(O/'RUN_STARTED.json',dict(end='2024-10-08',time=str(pd.Timestamp.now(tz='UTC'))));e=Engine(data).run();e.export(O/'once_20241008');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
