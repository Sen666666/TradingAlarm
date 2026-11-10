"""Integrated bounded A/B/D/E/F account engines. C is disabled.
Original economic methods imported from hash-frozen v9; history only in CLI.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys, json, copy, hashlib, importlib.util, argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
BASE=O.parent/'joint51_candidate_v9_facts'
spec=importlib.util.spec_from_file_location('allocation_baseline',BASE/'engine.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
from allocation_rules import (arm_config,add_quantity_limit,buy_capital_limits,
 seed_capital_failure,ticket_from_seed,refresh_retained_ticket,m3_seed_exit)
ZERO=base.ZERO;SLIP=base.SLIP;INITIAL=base.INITIAL
pd=base.pd;np=base.np;dec=base.dec;day=base.day;finite=base.finite
truth=base.truth;false=base.false;valid=base.valid;lineage=base.lineage
Blocked=base.Blocked
FAMILIES=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END']

class AblationEngine(base.Engine):
 def __init__(self,data,arm):
  super().__init__(data);self.arm=arm_config(arm);self.retained={};self.retry_log=[];self.extra_exits=[];self.add_quantity_log=[];self.cap_violations=[];self.blocked_targets=[]
 def retry_record(self,t,d,phase,event,**kw):
  self.retry_log.append(dict(day=day(d),phase=phase,event=event,ticket_id=t['ticket_id'],sid=t['sid'],signal_day=t['signal_day'],nav0=str(t['nav0']),original_factor=str(t['original_factor']),current_factor=str(t['current_factor']),ifloor=str(t['ifloor']),status=t['status'],**kw))
 def economic_preflight(self,d,pending):
  if not self.arm.retry_capital_seed:return super().economic_preflight(d,pending)
  # A source change explicitly cancels a retained ticket. Fresh ordinary tickets
  # and actual holdings retain the original hard-block source rule.
  for s,t in list(self.retained.items()):
   z=self.d.z(s,d)
   if len(z) and lineage(z)!=t['origin']:
    t['status']='CANCELLED';t['plan']=None;self.retry_record(t,d,'OPEN','SOURCE_CHANGED_CANCEL');self.retained.pop(s)
    pending[:]=[r for r in pending if r.get('ticket_id')!=t['ticket_id']]
  all_pending=list(pending);already={r['sid'] for r in pending}
  for s,t in self.retained.items():
   if s not in already:all_pending.append(dict(sid=s,origin=t['origin'],factor=t['current_factor'],ticket_id=t['ticket_id']))
  super().economic_preflight(d,all_pending)
  for s,t in self.retained.items():
   t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d)
   if self.d.events.get((s,d)) is not None:self.retry_record(t,d,'OPEN','VERIFIED_PENDING_BRIDGE',record_qty=0,entitlement='0')
 def close(self,d,prev):
  pending=super().close(d,prev)
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
   s=r['sid'];a=self.active.get(s);z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None
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
  bysid={r['sid']:r for r in pending}
  for s,t in self.retained.items():bysid.setdefault(s,dict(sid=s,origin=t['origin'],factor=t['current_factor'],ticket_id=t['ticket_id']))
  rows=[]
  for s in sorted(set(self.active)|set(bysid)):
   a=self.active.get(s);r=bysid.get(s);z=self.d.z(s,d);issues=[];acts=self.d.action(s,d);ev=self.d.events.get((s,d));origin=a['origin'] if a else r['origin'];f0=a['factor'] if a else r['factor']
   if not finite(z.get('raw_open')) or z.get('raw_open',0)<=0:issues.append('OPEN_MISSING')
   if len(z) and lineage(z)!=origin:issues.append('SOURCE_CHANGE')
   f1=dec(z['adjustment_factor']) if finite(z.get('adjustment_factor')) else None
   if f1 is None or f1<=0:issues.append('FACTOR_MISSING_OR_INVALID')
   elif abs(f1/f0-1)>D('1e-11') and ev is None:issues.append('UNADMITTED_FACTOR_CHANGE')
   if acts and ev is None:issues.append('UNADMITTED_EQUITY_EVENT')
   if ev is not None and f1 is not None and (abs(f0/dec(ev['factor_old'])-1)>D('1e-11') or abs(f1/dec(ev['factor_new'])-1)>D('1e-11')):issues.append('FACTOR_BRIDGE_MISMATCH')
   rows.append(dict(day=day(d),sid=s,sector51=self.d.sid_sector[s],held_qty=self.quantity(a) if a else 0,pending_seed=r is not None,retained_ticket=s in self.retained,issues=issues,actions=acts,source_origin=origin,previous_factor=str(f0),current_factor=str(f1),action_path=str(base.AS/'inputs-v1/actions'/(s+'.json'))))
  return rows
 def run_ablation(self,output):
  pending=[]
  for d in self.d.days:
   prev=self.d.cal[self.d.cal.get_loc(d)-1]
   keys=['cash','receivable','active','archive','seq','claims','snapshots','retained'];snap=copy.deepcopy({k:getattr(self,k) for k in keys});prior_pending=copy.deepcopy(pending)
   logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','retry_log','extra_exits','add_quantity_log','cap_violations'];lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if day(d) in ('2024-09-23','2024-09-27','2024-10-08'):
     self.pending=pending;self.export_ablation(output/f'checkpoint_{day(d)}');print('CHECKPOINT '+self.arm.name+' '+json.dumps(self.ledger[-1],ensure_ascii=False),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:])
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    pending=prior_pending;self.blockers.append(str(ex));self.blocked_targets=self.scan_blocked_targets(d,pending);break
  self.pending=pending;self.export_ablation(output/'full_prefix');return self
 def export_ablation(self,path):
  super().export(path)
  for name,rows in [('RETRY_TICKETS',self.retry_log),('RETAINED_AT_END',list(self.retained.values())),('ADDITIONAL_EXIT',self.extra_exits),('ADD_QUANTITY_LIMITS',self.add_quantity_log),('FULL_CAP_VIOLATIONS',self.cap_violations),('BLOCKED_DAY_ALL_TARGETS',self.blocked_targets),('BLOCKED_DAY_ALL_ISSUES',[r for r in self.blocked_targets if r['issues']])]:base.save(path/(name+'.json'),rows)
  base.save(path/'OUTPUT_HASHES.json',{p.name:base.sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

def freeze(data):
 files=['ablation_engine.py','allocation_rules.py','synthetic_integrated.py','FROZEN_CONTRACT.md','SYNTHETIC_INTEGRATION_QA.json']
 manifest=dict(baseline=str(BASE),effective_arms=['A','B','D','E','F'],C='DISABLED',historical_rules_frozen_before_runs=True,data_hashes=data.hashes,implementation_hashes={str(O/n):base.sha(O/n) for n in files})
 base.save(O/'EXECUTION_FREEZE.json',manifest);return manifest

def verify_freeze(data):
 f=base.read(O/'EXECUTION_FREEZE.json');assert data.hashes==f['data_hashes'];assert all(base.sha(p)==h for p,h in f['implementation_hashes'].items());return f

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['freeze','run'],required=True);ap.add_argument('--arms',default='A');ap.add_argument('--run-tag',default='v1');ap.add_argument('--review-approved',action='store_true');args=ap.parse_args()
 names=args.arms.split(',');[arm_config(x) for x in names]
 if any(x!='A' for x in names):assert args.review_approved,'INDEPENDENT_REVIEW_REQUIRED_BEFORE_NONBASELINE_RUN'
 data=base.Data('2024-10-31')
 if args.mode=='freeze':
  assert base.read(O/'SYNTHETIC_INTEGRATION_QA.json')['result']=='PASS';assert not (O/'EXECUTION_FREEZE.json').exists();freeze(data);print('FROZEN',len(data.hashes),flush=True)
 else:
  verify_freeze(data)
  for name in names:
   out=O/f'run_{name}_{args.run_tag}';out.mkdir(exist_ok=False);engine=AblationEngine(data,name).run_ablation(out)
   if name=='A':
    exact={}
    for fam in FAMILIES:
     got=base.read(out/'full_prefix'/(fam+'.json'));want=base.read(BASE/'full_20241031_once'/(fam+'.json'));assert got==want,('A_EXACT_REPLAY_FAILED',fam);exact[fam]=len(got)
    base.save(out/'A_EXACT_REPLAY_QA.json',dict(result='PASS',certified_through=engine.ledger[-1]['day'],exact_records=exact))
   base.save(out/'RUN_STATUS.json',dict(arm=name,days=len(engine.ledger),orders=len(engine.orders),certified_through=engine.ledger[-1]['day'] if engine.ledger else None,blockers=engine.blockers,last=engine.ledger[-1] if engine.ledger else None))
   print('RESULT '+name+' '+json.dumps(dict(days=len(engine.ledger),orders=len(engine.orders),blockers=engine.blockers,last=engine.ledger[-1] if engine.ledger else None)),flush=True)
