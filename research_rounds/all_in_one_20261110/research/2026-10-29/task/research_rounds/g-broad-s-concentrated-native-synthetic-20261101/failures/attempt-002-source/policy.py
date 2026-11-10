"""Capital/evidence policy only. No cash, positions or synthetic financial fills."""
from dataclasses import dataclass,field,asdict
from decimal import Decimal as D
import hashlib,json
Z=D(0)
class UnknownRisk(ValueError):pass
@dataclass
class Scope:
 source:str
 seq:int=0
 context:str|None=None
 permit:bool=False
 support:bool=False
 mature:bool=False
 events:list=field(default_factory=list)

@dataclass
class ExitLock:
 eid:str
 lot:int
 sid:str
 q0:D|None
 e0:D|None
 ratio:D
 remaining:int
 h:dict|None
 reason:str
 native_exit:str|None=None
 def charge(self,mark,floor):
  if self.remaining==0:return Z
  if self.q0 is None or self.e0 is None or self.q0<=0 or self.ratio<=0 or mark is None or floor is None:
   raise UnknownRisk('exit lock unknown '+self.eid)
  return max(D(self.remaining)*max(Z,mark-floor),self.e0*D(self.remaining)/(self.ratio*self.q0))

class Policy:
 def __init__(self):
  self.scopes={};self.cursor=-1;self.nd=D(1000000);self.consumed=set();self.k={};self.k_seq=0;self.k_trace=[]
  self.act=dict(on=True,peak=D(1000000),episode=0,saw_off=False,previous_fast=False)
  self.incident=None;self.incidents=[];self.proof_history=[];self.snapshots={};self.locks={};self.lock_seq=0
  self.losses={};self.audit=[]
 def evidence(self,scope,source,events,permit,support,cursor,seq,*,confirmed_cursor=None):
  confirmed=cursor if confirmed_cursor is None else confirmed_cursor
  old=self.scopes.get(scope)
  if old and seq<=old.seq:raise ValueError('source observation replay')
  s=old if old and old.source==source else Scope(source)
  ev=list(events)
  ended=any(e.startswith('price_failure') or e=='source_changed_context_ended' for e in ev)
  if ended:s.context=None;s.support=False;s.mature=False
  for kind in ev:
   if kind in ('break_started','repair_restored'):
    s.context=f'{scope}|{source}|{confirmed}|{seq}';s.mature=False
   elif kind=='price_advance' and s.context:s.mature=True
   if kind in ('break_started','repair_restored','price_advance') and s.context:
    self.proof_history.append(dict(scope=scope,source=source,context=s.context,kind=kind,confirmed=confirmed,seq=seq,known=cursor,event_id=f'{scope}|{source}|{confirmed}|{seq}|{kind}'))
  s.seq=seq;s.permit=bool(permit);s.support=bool(support and s.context);s.events=ev;self.scopes[scope]=s
 def start_incident(self,cursor,nav,packet_watermarks):
  self.act['on']=False
  self.incident=dict(id=len(self.incidents)+1,cutoff=cursor,watermarks=dict(packet_watermarks),trigger_nav=nav,
   old_phase=self.act['episode'],pending=[],unlocks={},phase_started_once=False,phase_seed_cursor=None,phase_seed_nav=None)
  self.incidents.append(self.incident);self.audit.append(dict(kind='ACT_incident',cursor=cursor,id=self.incident['id']))
 def unlock(self,cursor,nav):
  i=self.incident
  if i is None:return
  pending=[]
  for e in self.proof_history:
   s=self.scopes.get(e['scope']);wm=i['watermarks'].get(e['scope']+'|'+e['source'],-1)
   if e['confirmed']<=i['cutoff'] or e['seq']<=wm or e['known']>cursor:continue
   if not s or not s.support or s.source!=e['source'] or s.context!=e['context']:continue
   if not s.permit:pending.append(e['event_id']);continue
   uses=['G'] if e['scope']=='G' else (['T','S'] if e['kind']=='price_advance' else ['T'])
   for use in uses:
    key=e['scope']+'|'+e['context']+'|'+use
    if key in i['unlocks']:continue
    if not i['phase_started_once']:
     i.update(phase_started_once=True,phase_seed_cursor=cursor,phase_seed_nav=nav)
     self.act.update(on=True,peak=nav,episode=self.act['episode']+1,saw_off=False,previous_fast=False)
    i['unlocks'][key]=dict(e,use=use,unlocked_at=cursor)
  i['pending']=pending
 def allowed(self,scope,use,*,holding=False):
  s=self.scopes.get(scope)
  if not s or not s.support:return False
  if use=='S' and not s.mature:return False
  if holding:return True
  if not s.permit:return False
  if self.incident is None:return self.act['on']
  return self.act['on'] and scope+'|'+s.context+'|'+use in self.incident['unlocks']
 def choose_k(self,holders,old_orders,candidates,minimum_ok):
  # Incumbent shares are holding evidence, not a new minimum-size order.
  accepted={sec:dict(context=self.scopes[sec].context,reason='holding',witness=holders[sec]) for sec in sorted(holders) if self.allowed(sec,'S',holding=True)}
  admitted=[];seen=set(accepted);trace=[]
  entries=sorted(old_orders,key=lambda x:(x['priority'],x['sid']))+sorted(candidates,key=lambda x:(x['priority'],x['sid']))
  for w in entries:
   sec=w['sector']
   if sec in seen:continue
   seen.add(sec)
   if not self.allowed(sec,'S'):trace.append(dict(sector=sec,accepted=False,why='S1_unavailable'));continue
   proposed=len(accepted)+1;quota=self.nd*D('.8')/proposed
   ok=all(minimum_ok(x,quota) for x in admitted+[w])
   trace.append(dict(sector=sec,accepted=ok,k=proposed,quota=quota,why=None if ok else 'final_target_minimum'))
   if not ok:continue
   self.k_seq+=1;accepted[sec]=dict(context=self.scopes[sec].context,reason='order_or_fresh',witness=w['sid'],sequence=self.k_seq);admitted.append(w)
  self.k=accepted;self.k_trace.append(dict(cursor=self.cursor,accepted=list(accepted),trace=trace))
  return self.k
 def targets(self,sector):return self.nd*D('.8')/len(self.k) if sector in self.k else Z
 def snapshot(self,lot,*,mark,floor,ratio,cursor,qty,source):
  if mark is not None and floor is not None and mark>floor and qty>0:
   self.snapshots[lot]=dict(mark=mark,floor=floor,ratio=ratio,cursor=cursor,quantity=qty,source=source)
 def lock(self,lot,sid,qty,ratio,reason):
  h=self.snapshots.get(lot);self.lock_seq+=1;eid='exit-lock-'+str(self.lock_seq)
  if h:q0=D(qty)/(ratio/h['ratio']);e0=q0*(h['mark']-h['floor']);r=ratio/h['ratio']
  else:q0=e0=None;r=D(1)
  e=ExitLock(eid,lot,sid,q0,e0,r,qty,h,reason);self.locks[eid]=e;return e
 def consume_exit(self,lot,qty):
  left=qty
  for e in self.locks.values():
   if e.lot!=lot or not e.remaining:continue
   q=min(left,e.remaining);e.remaining-=q;left-=q
   if not left:break
  if left:raise AssertionError('native sell has no matching exit responsibility')
 def split(self,sid,ratio):
  for e in self.locks.values():
   if e.sid!=sid or not e.remaining:continue
   exact=D(e.remaining)*ratio;e.ratio*=ratio
   if exact!=int(exact):e.e0=None  # Exact native per-tranche fraction attribution is unavailable.
   e.remaining=int(exact)
 def record_loss(self,sector,episode,amount):
  key=sector+'|'+str(episode);self.losses[key]=self.losses.get(key,Z)+amount
 def exported(self):
  return dict(cursor=self.cursor,nd=self.nd,scopes={k:asdict(s) for k,s in self.scopes.items()},k=self.k,k_trace=self.k_trace,
   consumed=sorted(self.consumed),act=self.act,incident=self.incident,incidents=self.incidents,proof_history=self.proof_history,
   snapshots=self.snapshots,locks={k:asdict(e) for k,e in self.locks.items()},losses=self.losses,audit=self.audit)
