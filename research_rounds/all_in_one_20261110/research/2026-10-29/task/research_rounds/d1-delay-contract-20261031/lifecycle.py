"""Bounded D1 lifecycle specification only; no market/account execution model."""
from dataclasses import dataclass,field

@dataclass
class Lease:
 order_id:str
 stock:str
 role:str
 authorization:str
 original_session:int
 remaining:int
 first_wait_session:int|None=None
 retry_session:int|None=None
 expiry_session:int|None=None
 terminal:str|None=None
 audit:list=field(default_factory=list)
 used_windows:set=field(default_factory=set)
 ready_event:tuple|None=None
 def window(self,session,*,eligible,event_id):
  if self.terminal:return 'terminal'
  if session<self.original_session:return 'before_earliest'
  expiry=self.expiry_session if self.expiry_session is not None else self.original_session
  if session>expiry:raise ValueError('day-close expiry callback missing')
  if not eligible:return 'no_eligible_window'
  if event_id in self.used_windows:return 'duplicate_window'
  if self.first_wait_session is None:
   self.used_windows.add(event_id)
   self.first_wait_session=session;self.retry_session=session+1;self.expiry_session=session+1
   self.audit.append(('wait_once',session));return 'deliberately_skipped'
  if session<self.retry_session:return 'not_before_next_market_session'
  self.used_windows.add(event_id);self.ready_event=(session,event_id)
  self.audit.append(('execution_attempt',session));return 'attempt_original_order'
 def fill(self,session,qty):
  assert self.first_wait_session is not None and self.retry_session<=session<=self.expiry_session
  assert not self.terminal and self.ready_event and self.ready_event[0]==session and 0<qty<=self.remaining
  self.ready_event=None
  self.remaining-=qty;self.audit.append(('actual_fill_callback',session,qty))
  if not self.remaining:self.terminal='filled'
 def close(self,session,*,invalid_reason=None):
  if self.terminal:return self.terminal
  if invalid_reason:
   self.terminal='cancel_pending:'+invalid_reason;self.audit.append(('real_cancel_required',session,invalid_reason));return self.terminal
  expiry=self.expiry_session if self.expiry_session is not None else self.original_session
  if session>=expiry:
   self.terminal='cancel_pending:lease_expired';self.audit.append(('real_cancel_required',session,'lease_expired'));return self.terminal
  return 'retain_same_order_and_resources'
 def cancel_ack(self):
  assert self.terminal and self.terminal.startswith('cancel_pending:')
  self.audit.append(('actual_cancel_ack_callback',self.remaining));self.remaining=0;self.terminal='cancelled'

class Book:
 """Token/identity state only; capital and real cancellation are caller-owned."""
 def __init__(self):self.consumed=set();self.pending={};self.sequence=0
 def place(self,stock,role,authorization,session,qty):
  assert role in ('core','mobile_first','mobile_add','mobile_reentry') and qty>0
  if stock in self.pending and self.pending[stock].terminal not in ('filled','cancelled'):return 'buy_pending'
  if authorization in self.consumed:return 'already_consumed'
  self.sequence+=1;self.consumed.add(authorization)
  o=Lease(str(self.sequence),stock,role,authorization,session,qty);self.pending[stock]=o;return o
