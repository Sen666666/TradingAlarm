"""Small retained-mechanism checks, no native Account or financial path."""
import copy,json,sys
from pathlib import Path
import component as P
sys.path.insert(0,str(P.W/'probe-batch-local-preview-20261101'))
import test_planner as F

def make():
 # Existing confirmed capital660k and global probe risk5000 exceed their old
 # admission limits once known new fees are deducted. Cash remains290k.
 lots=[P.N.Lot('held-confirmed','C','OLD','E-OLD','confirmed',6600,100,99.99,attempt='A-OLD'),
       P.N.Lot('held-probe','Q','P','E-P','probe',500,100,90,attempt='A-P')]
 return P.State(cash=290000,lots=lots,prices={'C':100,'Q':100},sectors={s:F.sector(s,l)for s,l in [('OLD',1),('P',0),('S',1)]},sector_by_sid={'C':'OLD','Q':'P','X':'S','Y':'S'})

def main():
 s=make();x=F.item('X','S',p='10',floor='9.9',target=100)
 off=P.plan(s,[x],F.AT,False);on=P.plan(s,[x],F.AT,True)
 assert not off['orders']and len(on['orders'])==1 and on['orders'][0]['pool']=='confirmed'
 tests=[dict(name='only60_can_bind_with_cash',OFF_orders=0,ON_orders=1)]
 for status in ['open','cancel_pending']:
  t=make();o=P.N.Order('old','Z','S','E-S','probe',100,10,9.9,0,status=status,attempt='A-S');t.orders['old']=o
  r=P.plan(t,[x],F.AT,True)
  assert not r['orders']and not r['migrations'][0]['result']and r['final_state']['orders']['old']==P.serial(o)
  tests.append(dict(name='same_attempt_probe_'+status,ON_orders=0,old_pending_unchanged=True))
 t=make();wide=F.item('X','S',p='100',floor='0',target=100)
 assert not P.plan(t,[wide],F.AT,True)['orders']
 tests.append(dict(name='sector1_still_blocks_wide_risk',ON_orders=0))
 t=make();t.lots.append(P.N.Lot('stock-full','X','S','E-S','confirmed',10000,10,9.99,attempt='A-S'));t.prices['X']=10;t.cash-=100000
 assert not P.plan(t,[x],F.AT,True)['orders']
 tests.append(dict(name='stock10_still_blocks',ON_orders=0))
 t=make();t.cash=0;t.receivable_equity=290000
 assert not P.plan(t,[x],F.AT,True)['orders']
 tests.append(dict(name='receivable_cannot_pay_cash',ON_orders=0))
 t=make();core=F.item('X','S',role='core',target=100);t.core_epoch['X']=core['epoch']
 r=P.plan(t,[x,core],F.AT,True)
 assert len(r['orders'])==1 and r['orders'][0]['role']=='mobile'
 # Core has only probe and cannot bypass its risk bound. Route/request's
 # original core_epoch gate is retained; check it separately at request level.
 v=make();v.core_epoch['X']=core['epoch'];v.stock_requests=set();v.orders={}
 answer=v.request('locked','X','S',100,10,9.9,None,P.J.ordinal(F.DEC.date()),0,probe_request=True,role='core',core_epoch_locked=True)
 assert answer=='core_epoch_locked'
 tests.append(dict(name='core_lock_retained_mobile_continues',core_request='core_epoch_locked',ON_roles=['mobile']))
 # Independent identical snapshots could each reserve1900. Serial resource
 # feedback admits the first only; adding hypothetical quantities is wrong.
 t=make();a=F.item('X','S',p='10',floor='5',target=2000);b=F.item('Y','S',rank=1,p='10',floor='5',target=2000)
 one=P.plan(t,[a],F.AT,True);two=P.plan(t,[b],F.AT,True);both=P.plan(t,[a,b],F.AT,True)
 independent=sum(z['quantity']for r in [one,two]for z in r['orders']);serial=sum(z['quantity']for z in both['orders'])
 assert independent>serial and len(both['orders'])==1
 tests.append(dict(name='serial_sector_risk_feedback',independent_quantities=independent,serial_quantities=serial,serial_orders=1))
 (P.O/'COUNTEREXAMPLES.json').write_text(json.dumps(P.serial(dict(passed=True,tests=tests,native_Account_initializations=0,real_fills=0,financial_paths=0)),ensure_ascii=False,indent=2)+'\n')
 print('counterexamples passed',len(tests))

if __name__=='__main__':main()
