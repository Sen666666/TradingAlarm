"""No-subscription analysis/research adapter. No historical or finance imports."""
from pathlib import Path
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
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

def conservation_bytes(runner):
 """All financial/account/strategy state except marks, audit and observation clocks."""
 a=runner.account
 excluded={'owner','market','facts','last_cursor','audit_log','native_callbacks'}
 account={k:v for k,v in a.__dict__.items() if k not in excluded}
 facts={k:v for k,v in a.facts.__dict__.items() if k not in {'market','inputs'}}
 names=('authority','budget','binding_id','active','trusted','coverage','goal_intents','local_wait_sids','_busy_goals','close_stages','f1','f1seq','last_stock_state','cursor','windows','event_ids','action_ids','results','lifecycle','rank_bindings','active_intents','transitions')
 state={k:runner.__dict__[k] for k in names if k in runner.__dict__}
 return pickle.dumps((account,facts,state),protocol=pickle.HIGHEST_PROTOCOL)

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
  for key,p in new.items():
   f=self.inputs.rows('facts',p['sid'],day,True)
   require(f is not None and 'factor' in f and number(f['factor'],'exact ex-date factor')>0,'unknown exact ex-date factor')
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
