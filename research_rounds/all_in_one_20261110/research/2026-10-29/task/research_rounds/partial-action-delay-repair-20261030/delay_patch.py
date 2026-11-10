"""One-cutoff, role-identified delay credit; no signal/budget policy changes."""
import sys
from pathlib import Path
OLD=Path(__file__).resolve().parent.parent/'partial-action-full-account-20261030'
sys.path.insert(0,str(OLD))
import integrated as I
BASE_FACTORY=I.account_class
class RoleDelayCredit:
 def _enabled(self):return self.roles_enabled and bool(self.delay_events)
 def _key(self,sid):
  r=self.roles.get(sid)
  if r is None or self.quantity(sid)<=0 or r['R']>=r['cap'] or sid in self.exits or sid in self.full_signals:return None
  return (sid,r['group'],'risk_restore',r['cycle'],str(r['risk_flat_at']))
 def expire_day_buys(self,at):
  if not self._enabled():return super().expire_day_buys(at)
  credits={};roleids=set()
  for sid,o in tuple(self.buys.items()):
   if o.purpose!='risk_restore':continue
   roleids.add(sid);meta=self.role_orders.get(o.order_id,{});key=self._key(sid)
   if at.date()>=o.earliest_at.date() and not o.filled_shares and not o.delay_remaining and key and meta.get('group')==key[1]:
    credits[sid]=dict(key=key,at=at,from_order=o.order_id)
  expired=super().expire_day_buys(at)
  self.daily_delay_credit.difference_update(roleids)
  self._restore_delay_credit=credits
  for sid,c in credits.items():self.log('role_delay_credit_created',at,sid=sid,key=c['key'],from_order=c['from_order'],valid_only_at_cutoff=at)
  return expired
 def restore(self,quote,clock,budget,receipt):
  if not self._enabled():return super().restore(quote,clock,budget,receipt)
  sid=quote.security_id;c=getattr(self,'_restore_delay_credit',{}).get(sid);key=self._key(sid)
  if c and c['key']!=key:getattr(self,'_restore_delay_credit',{}).pop(sid,None)
  valid=bool(c and key and c['key']==key and c['at']==clock.decision_at and receipt.native_i_buy and receipt.symbol==sid and receipt.known_at<=clock.decision_at and receipt.known_at.date()==clock.session_date)
  ok,oid=super().restore(quote,clock,budget,receipt)
  if ok and valid:
   self.buys[sid].delay_remaining=0;self._restore_delay_credit.pop(sid,None)
   self.log('role_delay_credit_consumed',clock.decision_at,sid=sid,key=key,from_order=c['from_order'],to_order=oid,new_event_id=receipt.event_id,signal_not_extended=True)
  return ok,oid
 def request_exit(self,quote,clock):
  if self._enabled():getattr(self,'_restore_delay_credit',{}).pop(quote.security_id,None)
  return super().request_exit(quote,clock)
 def fill_buy(self,sid,w):
  f=super().fill_buy(sid,w)
  if self._enabled() and f and self.roles[sid]['R']>=self.roles[sid]['cap']:getattr(self,'_restore_delay_credit',{}).pop(sid,None)
  return f
 def fill_exit(self,sid,w):
  f=super().fill_exit(sid,w)
  if self._enabled() and not self.quantity(sid):getattr(self,'_restore_delay_credit',{}).pop(sid,None)
  return f

def factory(Parent,feed):return type('RoleDelayRepairedAccount',(RoleDelayCredit,BASE_FACTORY(Parent,feed)),{})
def install():I.account_class=factory
