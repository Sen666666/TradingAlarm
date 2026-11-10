"""No-subscription analysis/research adapter. No historical or finance imports."""
from pathlib import Path
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from dataclasses import is_dataclass,fields
from fractions import Fraction
from numbers import Integral,Real
import math
import copy,hashlib,json,pickle

KIND='rights_issue_no_subscription'
ELECTION='do_not_subscribe_no_cash_debit_no_extra_holder_shares'
class UnsupportedRights(ValueError):pass
def require(value,message):
 if not value:raise UnsupportedRights(message)
def number(value,label):
 require(value is not None and not isinstance(value,bool),'unknown '+label)
 try:n=Decimal(str(value))
 except (InvalidOperation,ValueError):raise UnsupportedRights('unknown '+label)
 require(n.is_finite(),'unknown '+label);return n
def canonical(value):
 try:return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
 except (ValueError,TypeError):raise UnsupportedRights('noncanonical/unknown action metadata')
def validate_rights(event,day=None):
 required=('sid','effective_date','known_action_date','source_id','classification','holder_election','modeling_basis','cash_per_old_share','split_ratio','volume_split_ratio','rights_ratio','subscription_price','signal_cash_per_old_share','signal_split_ratio')
 require(isinstance(event,dict) and all(k in event for k in required),'missing rights metadata')
 for k in ('sid','source_id'):require(isinstance(event[k],str) and bool(event[k]),'unknown '+k)
 try:d=date.fromisoformat(event['effective_date'])
 except (ValueError,TypeError):raise UnsupportedRights('unknown effective date')
 require(event['effective_date']==d.isoformat() and event['known_action_date']==d.isoformat(),'unknown/misaligned action date')
 require(day is None or day==d.isoformat(),'misdated rights action')
 require(event['classification']==KIND and event['holder_election']==ELECTION and event['modeling_basis']=='declared_research_proxy','unsupported holder election/classification')
 cash=number(event['cash_per_old_share'],'actual cash');ratio=number(event['split_ratio'],'actual share ratio');vol=number(event['volume_split_ratio'],'volume share ratio')
 rr=number(event['rights_ratio'],'rights ratio');sp=number(event['subscription_price'],'subscription price')
 sc=number(event['signal_cash_per_old_share'],'signal cash');sr=number(event['signal_split_ratio'],'signal ratio')
 require(cash==0 and ratio==1 and vol==1,'no-subscription must have zero cash and unit actual shares')
 require(rr>0 and sp>0 and sr==1+rr and sc==-(rr*sp),'rights signal-coordinate identity mismatch')
 # The full source packet, including optional provenance, is immutable identity.
 payload=hashlib.sha256(canonical(event).encode()).hexdigest()
 key='no-subscription|'+event['sid']+'|'+event['effective_date']+'|'+event['source_id']
 return dict(event_id=key,payload_sha256=payload,sid=event['sid'],day=d.isoformat(),actual_cash='0',actual_share_ratio='1',signal_ratio=str(sr),signal_cash=str(sc))

class NoSubscriptionInputsMixin:
 def check_action_support(self,event,layer_quantities=None):
  if event.get('classification')==KIND:
   proof=validate_rights(event)
   return dict(ready=True,kind=KIND,proof=proof,no_cash_or_extra_shares=True)
  return super().check_action_support(event,layer_quantities)

def state_value(value,memo=None,path='$'):
 """Stable typed values and mutable references, not pickle memo-byte layout."""
 memo={} if memo is None else memo
 if value is None or isinstance(value,(str,bool)):return value
 if isinstance(value,Decimal):return {'decimal':str(value)}
 if isinstance(value,Fraction):return {'fraction':[value.numerator,value.denominator]}
 if isinstance(value,(datetime,date)):return {'date':value.isoformat()}
 if isinstance(value,Integral):return int(value)
 if isinstance(value,Real):return {'float':repr(float(value))}
 if isinstance(value,Path):return {'path':str(value)}
 if id(value) in memo:return {'reference':memo[id(value)]}
 memo[id(value)]=path
 if isinstance(value,dict):return {'dict':[[state_value(k,memo,path+'/key'+str(j)),state_value(v,memo,path+'/'+str(k))] for j,(k,v) in enumerate(sorted(value.items(),key=lambda p:repr(p[0]))) ]}
 if isinstance(value,(list,tuple)):return {type(value).__name__:[state_value(v,memo,path+'/'+str(j)) for j,v in enumerate(value)]}
 if isinstance(value,(set,frozenset)):return {'set':[state_value(v,memo,path+'/'+str(j)) for j,v in enumerate(sorted(value,key=repr))]}
 data={f.name:getattr(value,f.name) for f in fields(value)} if is_dataclass(value) else getattr(value,'__dict__',None)
 require(data is not None,'unsupported conservation state '+type(value).__name__)
 return {'type':type(value).__module__+'.'+type(value).__qualname__,'state':state_value(data,memo,path+'/state')}

def conservation_bytes(runner):
 """All financial/account/strategy state except marks, audit and observation clocks."""
 a=runner.account
 excluded={'owner','market','facts','last_cursor','as_of','audit_log','native_callbacks'}
 account={k:v for k,v in a.__dict__.items() if k not in excluded}
 facts={k:v for k,v in a.facts.__dict__.items() if k not in {'market','inputs'}}
 names=('authority','budget','binding_id','active','trusted','coverage','goal_intents','local_wait_sids','_busy_goals','close_stages','f1','f1seq','last_stock_state','cursor','windows','event_ids','action_ids','results','lifecycle','rank_bindings','active_intents','transitions')
 state={k:runner.__dict__[k] for k in names if k in runner.__dict__}
 return canonical(state_value((account,facts,state))).encode()

class NoSubscriptionRunnerMixin:
 """Compose before MonthRunner; _rights_ordinary_dispatch must delegate unchanged."""
 def source_binding(self):
  out=super().source_binding()
  for name in ('rights_wiring.py','CONTRACT.txt'):
   p=Path(__file__).with_name(name);out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  return out
 def corporate_actions(self,day):
  self.execution_guard(day)
  actions=self.inputs.actions(day)
  if not actions:return None
  rights=[r for r in actions if r.get('classification')==KIND]
  if not rights:return self._rights_ordinary_dispatch(day)
  require(len(rights)==len(actions),'mixed rights/ordinary batch not wired; atomic refusal')
  at=datetime.fromisoformat(day+'T00:00:00+08:00');seen=getattr(self,'no_subscription_actions',{})
  proofs={};terms={}
  for event in rights:
   p=validate_rights(event,day);key=p['event_id']
   require(event['sid'] in self.inputs.ids and day in self.inputs.days,'outside frozen input identity/date')
   if key in proofs:require(proofs[key]['payload_sha256']==p['payload_sha256'],'changed duplicate rights terms')
   if key in seen:require(seen[key]['payload_sha256']==p['payload_sha256'],'changed applied rights terms')
   proofs[key]=p;terms[key]=event
  new={k:p for k,p in proofs.items() if k not in seen}
  if not new:return dict(status='already_applied',events=sorted(proofs))
  require(self.last_completed_event is None or at>self.last_completed_event,'new rights action before/equal completed cursor')
  for item in self.account.settlements.values():
   due=getattr(item,'due_at',None)
   require(isinstance(due,datetime) and due.tzinfo is not None,'unknown native settlement clock')
   require(due>at,'rights ACTION with already-due settlement not wired; do not shift native cash timing')
  for key,p in new.items():
   f=self.inputs.rows('facts',p['sid'],day,True)
   require(f is not None and 'factor' in f and number(f['factor'],'exact ex-date factor')>0,'unknown exact ex-date factor')
   for z in (z for z in self.account.layers if z['sid']==p['sid'] and z['qty']):
    try:floor=self.account.raw_floor(z)
    except Exception:raise UnsupportedRights('unknown existing effective protection')
    require(number(floor,'existing effective protection')>0,'unknown existing effective protection')
   if p['sid'] in self.account.buys:
    order=self.account.buys[p['sid']];floor=self.account.order_meta.get(order.order_id,{}).get('floor')
    require(number(floor,'reserved buy protection')>0,'unknown reserved buy protection')
  # Same trusted in-memory transaction discipline as the frozen native event API.
  backup=pickle.dumps(self,protocol=pickle.HIGHEST_PROTOCOL);before=conservation_bytes(self)
  try:
   a=self.account;a.market.refresh(at);a.last_cursor=at
   for key,p in new.items():
    actual=a.facts.factor(p['sid'],at)
    f=self.inputs.rows('facts',p['sid'],day,True)
    require(number(actual,'loaded factor')==number(f['factor'],'source factor'),'loaded/source coordinate factor mismatch')
    entry=dict(kind=KIND,at=at,event_id=key,source=copy.deepcopy(terms[key]),old_shares=a.quantity(p['sid']),
     actual_cash_delta='0',actual_share_ratio='1',no_cash_or_extra_shares_invented=True,signal_ratio_not_applied_to_inventory=True)
    a.audit_log.append(entry);a.native_callbacks.append(dict(kind='no_subscription_action_observed',at=at,event_id=key,actual_share_ratio='1',signal_only_ratio=p['signal_ratio']))
    self.action_log.append(copy.deepcopy(entry))
   self.assert_observers();bridge=a.bridge(at)
   require(conservation_bytes(self)==before,'rights changed financial/strategy/budget/authority state')
   # Commit observation identity only after native checks have succeeded.
   self.no_subscription_actions=copy.deepcopy(seen)
   self.no_subscription_actions.update({k:dict(p,source=copy.deepcopy(terms[k])) for k,p in new.items()})
   self.last_completed_event=at;self.events.append(dict(at=at,phase='ACTION',bridge=bridge,no_subscription_events=sorted(new)))
   return dict(status='observed_no_subscription',events=sorted(new),bridge=bridge)
  except Exception:
   prior=pickle.loads(backup);self.__dict__.clear();self.__dict__.update(prior.__dict__);self.account.owner=self
   raise
