import unittest,json,copy,subprocess
from datetime import datetime
from dataclasses import asdict
from projector import *
AT='2025-07-03 15:10:00+08:00';END='2025-07-04 15:10:00+08:00'
MAIN=asdict(N.quantity(datetime.fromisoformat(AT),False));STAR=asdict(N.quantity(datetime.fromisoformat(AT),True));FEES=asdict(N.fees(datetime.fromisoformat(AT),False))
def lot(sid='OLD',q=5000,mark='100',floor='88.4',purpose='G',pool='confirmed',role='mobile',sector='OLDSEC',risk=None,locked=False):
 m=D(mark);r=D(q)*max(Z,m-D(floor)) if risk is None else D(risk)
 return dict(id=sid,sid=sid,sector=sector,qty=q,mark=m,floor=D(floor),capital=D(q)*m,risk=r,pool=pool,role=role,purpose=purpose,
   locked_capital=D(q)*m if locked else Z,donor_eligible=not locked,holding_S=True,sellable_qty=q,quantity=copy.deepcopy(MAIN),fees=copy.deepcopy(FEES))
def state(lots=(),cash='500000',assets=(),nd=None):
 nav=D(cash)+sum((num(z,'capital') for z in lots),Z)+sum((num(a,'amount') for a in assets if a['kind']=='sale_receivable'),Z)
 return dict(at=AT,deadline=END,decision_nav=nav if nd is None else D(nd),nav=nav,available=D(cash),pending_fees=Z,rows=copy.deepcopy(list(lots)),lots=copy.deepcopy(list(lots)),assets=copy.deepcopy(list(assets)),targets={z['sector']:nav*D('.8') for z in lots})
def demand(sid='NEW',q=500,mark='100',floor='90',quantity=MAIN,sector=None):
 return dict(sid=sid,sector=sector or sid,priority=(0,sid),max_q=q,mark=D(mark),floor=D(floor),role='mobile',pool='confirmed',use='S',eligible=True,receipt_valid=True,
   receipt_id='receipt-'+sid,known_at=AT,deadline=END,industry_target=D('800000'),quantity=copy.deepcopy(quantity),fees=copy.deepcopy(FEES))
def simple_exit_state():
 z=lot(q=800,mark='1',floor='1.1',risk='5',locked=True)
 asset=dict(id='EXIT|old',kind='pending_exit',amount=D(100)*(ONE-SLIP)-fee(100,ONE-SLIP,FEES,'sell'),due_at='2025-07-04 09:30:00+08:00',parts=[dict(layer='OLD',q=100,risk_release=D(5))],cancel_pending=False)
 return state([z],cash='200',assets=[asset]),[demand('A',100,'.9','.89'),demand('B',100,'.9','.89')]

class Tests(unittest.TestCase):
 def test_zero_no_liquidation(self):
  s=state([lot()]);d=demand();d['eligible']=False;r=solve(s,[d]);self.assertEqual(r['Q'],{'NEW':0});self.assertFalse(r['donors']['rows'])
 def test_partial_feasible_not_full_target(self):
  s=state([lot()]);d=demand();r=solve(s,[d]);self.assertEqual(r['Q']['NEW'],100);self.assertFalse(r['donors']['rows']);self.assertFalse(preview(s,[d],{'NEW':500})['validation']['ok'])
 def test_all_feasible(self):
  s=state([],cash='1000000');ds=[demand('A',100,'10','9'),demand('B',200,'10','9')];r=solve(s,ds);self.assertEqual(r['Q'],{'A':100,'B':200});self.assertFalse(r['donors']['rows'])
 def test_genuine_nonmonotone_quantity_min_fails_larger_passes(self):
  s=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');d=demand(q=200,mark='1',floor='.98')
  low=preview(s,[d],{'NEW':100});high=preview(s,[d],{'NEW':200})
  self.assertFalse(low['validation']['ok']);self.assertTrue(high['validation']['ok']);self.assertFalse(low['donors']['rows']);self.assertTrue(high['donors']['rows'])
  self.assertEqual(solve(s,[d])['Q']['NEW'],200)
 def test_star_each_new_order_min200_even_with_holdings(self):
  for existing in (False,True):
   s=state([lot('NEW',q=50,mark='10',floor='9')] if existing else [],cash='1000000');d=demand(q=199,mark='10',floor='9',quantity=STAR)
   self.assertEqual(solve(s,[d])['Q']['NEW'],0)
  d=demand(q=205,mark='10',floor='9',quantity=STAR);self.assertEqual(list(qty_options(d)),[205,204,203,202,201,200,0])
 def test_min_fee_native_incremental_not_paid_twice(self):
  sched=schedule(FEES);p=D('10');paid=sched.incremental('sell',D(100)*p,{}, {},1,shares=100);accrued=sched.rate_accrual('sell',D(100)*p,1,shares=100)
  second=fee(100,p,FEES,'sell',paid,accrued);independent=fee(100,p,FEES,'sell');self.assertEqual(independent-second,D(5))
 def test_unfilled_exit_lock_not_current_cash_or_risk(self):
  s,ds=simple_exit_state();before=digest(s);r=solve(s,ds)
  self.assertTrue(r['validation']['conditional']);self.assertEqual(r['validation']['actual_risk_released'],0);self.assertEqual(r['validation']['actual_cash_released'],0)
  self.assertEqual(s['rows'][0]['risk'],5);self.assertEqual(s['available'],200);self.assertEqual(digest(s),before)
 def test_pending_cover_not_funded_twice(self):
  s,ds=simple_exit_state();r1=solve(s,ds);r2=solve(s,ds);self.assertEqual(r1['certificate_id'],r2['certificate_id']);self.assertFalse(r2['donors']['rows']);self.assertGreater(r2['donors']['covered'],0)
 def test_partial_sale_then_partial_cash_settlement_no_double_cover(self):
  s,ds=simple_exit_state();p=ONE-SLIP;sc=schedule(FEES);paid=sc.incremental('sell',D(50)*p,{}, {},1,shares=50);acc=sc.rate_accrual('sell',D(50)*p,1,shares=50)
  net1=D(50)*p-sum(paid.values(),Z);net2=D(50)*p-fee(50,p,FEES,'sell',paid,acc)
  s['rows'][0]['qty']-=50;s['rows'][0]['capital']-=50;s['rows'][0]['risk']-=D('2.5');s['lots']=copy.deepcopy(s['rows'])
  s['assets']=[dict(id='AR|partial',kind='sale_receivable',amount=net1,due_at='2025-07-04 09:30:00+08:00',parts=[]),dict(s['assets'][0],amount=net2,parts=[dict(layer='OLD',q=50,risk_release=D('2.5'))])]
  s['nav']+=net1-D(50)
  unsettled=solve(s,ds);self.assertFalse(unsettled['donors']['rows'])
  s['available']+=net1;s['assets']=s['assets'][1:]
  settled=solve(s,ds);self.assertEqual(unsettled['Q'],settled['Q']);self.assertEqual(unsettled['validation']['terminal'],settled['validation']['terminal']);self.assertFalse(settled['donors']['rows'])
 def test_cancel_pending_and_duplicate_asset_block_atomically(self):
  s,ds=simple_exit_state();s['assets'][0]['cancel_pending']=True;before=digest(s)
  with self.assertRaisesRegex(ValueError,'WAIT_CANCEL_ACK'):solve(s,ds)
  self.assertEqual(digest(s),before);s['assets'][0]['cancel_pending']=False;s['assets'].append(copy.deepcopy(s['assets'][0]))
  with self.assertRaisesRegex(ValueError,'duplicate'):solve(s,ds)
 def test_future_quote_and_gap_guard(self):
  s=state([],cash='1000000');d=demand(q=100);d['known_at']='2025-07-04 09:30:00+08:00';self.assertEqual(solve(s,[d])['Q']['NEW'],0)
  d=demand(q=100);d['floor']=d['mark'];self.assertEqual(solve(s,[d])['Q']['NEW'],0)
 def test_probe_core_pending_reserve_unchanged(self):
  s=state([],cash='1000000');d=demand(q=1000,mark='100',floor='90');d['pool']='probe';d['role']='core'
  self.assertEqual(solve(s,[d])['Q']['NEW'],100)
  # Cancel-pending commitment remains charged, just as any other old order.
  s['rows'].append(dict(id='pending',sid='P',sector='P',pool='probe',role='core',qty=1000,mark=100,capital=D(100000),risk=D(5000)))
  self.assertEqual(solve(s,[d])['Q']['NEW'],0)
 def test_donor_not_yet_sellable_rejects_no_fictional_cash(self):
  s=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');s['lots'][0]['sellable_qty']=0;d=demand(q=200,mark='1',floor='.98')
  r=solve(s,[d]);self.assertEqual(r['Q']['NEW'],0);self.assertFalse(r['donors']['rows'])
 def test_restart_fresh_never_revives_raw_target(self):
  s=state([lot()]);d=demand();c=solve(s,[d]);b=CertificateBook();b.accept(c,'same-industry-source-context')
  b.bind_reservation('same-industry-source-context','NEW','real-order-1',100,AT);b.actual_fill('real-order-1',50);b.cancel_request('real-order-1')
  self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT),0)
  b=CertificateBook.loads(b.dumps());self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT),0)
  b.cancel_ack('real-order-1');self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT),50)
  self.assertEqual(b.cap('same-industry-source-context','NEW',500,'2025-07-05 09:30:00+08:00'),0)
 def test_wrong_certificate_source_rejected(self):
  b=CertificateBook();r=json.loads(b.dumps());r['source_sha256']='wrong'
  with self.assertRaisesRegex(ValueError,'identity'):CertificateBook.loads(json.dumps(r))

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 Path(__file__).with_name('SYNTHETIC_RESULTS.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),financial_events=0),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
