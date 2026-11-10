"""Synthetic CORE fill/expiry checks, no historical economic path."""
from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
import json
import inputs as I
import conditional_engine as E
J=I.J

def make(data,c):
 r=E.Runner(*I.single(data,c['sid']),c,E.ARMS[1]);r.warm(data['calendar']);E.seed_plan(r);return r

def main():
 data=I.load();c=data['cases'][0];r=make(data,c);a=r.account;mobile=a.pending[0];cpid=mobile['CP1_id'];assert cpid not in a.budget.consumed
 at=mobile['clock'].earliest_execution_at;r.market.set_phase(at,'OPEN');factor=r.facts.factor(r.sid,at);w=r.market.window(r.sid,at,'buy',1)
 assert J.LR.preview(mobile,mobile['guard_floor']/factor,factor,w.quantity,w.fees)[1]=='open_at_or_below_protection';assert cpid not in a.budget.consumed
 # Old pending intent is not a perpetual order and cannot be executed a session late.
 nxt=next(t for t in r.market.sessions['A']if t>at);r.market.set_phase(nxt,'OPEN');r.opening(a,nxt);assert not a.trades and cpid not in a.budget.consumed
 # A distinct synthetic true CORE intent takes native LR sizing and consumes epoch only on fill.
 r=make(data,c);a=r.account;i=dict(a.pending[0]);i.update(kind='core',role='core',floor=i['I_floor'],CP1_id=None,CP1_trace=None,reason='SYNTHETIC_TRUE_CORE')
 for key in ['common_probe','probe_arm','risk_floor','guard_floor','seed_signal_nav']:i.pop(key,None)
 J.LR.resize_core(i,a.current_nav,r.facts.factor(r.sid,i['clock'].decision_at));a.pending=[i];at=i['clock'].earliest_execution_at;m=r.market;m.set_phase(at,'OPEN');old=m.window
 def win(sid,t,side,cost):
  w=old(sid,t,side,cost);return replace(w,event_id=w.event_id+':SYNTHETIC_CORE37',capacity_shares=37)if w else None
 m.window=win;r.opening(a,at);assert a.quantity(r.sid)==37 and a.layers[-1]['kind']=='core'and a.core_epoch[r.sid]==i['epoch']
 # Native mirror serialization includes tuple-key losses; verify persisted schema can represent it.
 encoded=I.canon(a.budget.__dict__);assert isinstance(encoded,dict)
 I.save('CORE_FILL_AND_EXPIRY_TESTS.json',dict(passed=True,preview_rejection_does_not_consume_CP=True,old_intent_not_replayed_on_later_OPEN=True,true_CORE_fill_consumes_epoch=True,probe_CORE_distinction_proven=True,native_budget_serializes=True,synthetic_quantity=37,economic_paths=0))
 print('CORE_FILL_AND_EXPIRY_PASS')
if __name__=='__main__':main()
