"""New-policy regressions on synthetic budget views, NOT historical execution.
Native model fill/sell/cancel callbacks below are synthetic unit fixtures only;
the real adapter still owns actual fills and is never instantiated here.
"""
import unittest,copy,json,sys
from decimal import Decimal as D
from types import SimpleNamespace as NS
import variant as V
B=V.B;sys.path.insert(0,str(V.OLD))
from test_planner import item,sector,AT,SCHEDULE

class Synthetic(V.TraceState):
    loss=B.N.Contract.loss
    fill=B.N.Contract.fill
    sell=B.N.Contract.sell
    cancel=B.N.Contract.cancel
    cancel_ack=B.N.Contract.cancel_ack
def state(levels=None,decoupled=True,**kw):
    return Synthetic(cash=kw.pop('cash',1000000),sectors={s:sector(s,l) for s,l in (levels or {'S':1}).items()},decoupled=decoupled,**kw)
def bind(s,items,sec):
    for i in items:s.sector_by_sid[i['sid']]=sec[i['sid']]
    return s
def ords(r):return [(x['sid'],x['role'],x['pool'],x['quantity'],x['fee']) for x in r['orders']]
def from_result(r,decoupled=True):
    x=r['final_state'];s=Synthetic(cash=x['cash'],available_exact=r['available'],receivables=x['receivables'],lots=[B.N.Lot(**v) for v in x['lots']],orders={k:B.N.Order(**v) for k,v in x['orders'].items()},sectors={k:NS(**v) for k,v in x['sectors'].items()},prices=x['prices'],consumed=x['consumed'],stock_requests=x['stock_requests'],sector_by_sid=x['sector_by_sid'],decision_nav=x['decision_nav'],historical_shared_loss=x['historical_shared_loss'],decoupled=decoupled)
    return s
def pending_fixture(status='open'):
    lots=[B.N.Lot('Y'+str(k),'Y'+str(k),'T'+str(k),'old','confirmed',800,90,99,attempt='old') for k in range(5)]
    lots.append(B.N.Lot('P','P','S','E-S','probe',200,40,45,role='core',attempt='A-S'))
    s=state({'S':1,**{'T'+str(k):1 for k in range(5)}},cash=590000,lots=lots,prices={**{'Y'+str(k):100 for k in range(5)},'P':50},historical_shared_loss=123)
    a=item('A','S',role='core',p='50',floor='40',target=100);bind(s,[a],{'A':'S'});av=B.AccountView(s);s.context=B.bid(a)
    r,why=B.reserve_fixed(av,a,a['_preview'],100,'probe',AT);assert why is None;s.available_exact=av.available;s.orders[B.bid(a)].status=status
    x=item('X','S',rank=1,p='50',floor='45',target=400);bind(s,[x],{'X':'S'});return s,a,x

class NewPolicyTests(unittest.TestCase):
 def test_open_and_cancel_pending_do_not_hide_new_confirmed_or_release_probe(self):
    for status in ['open','cancel_pending']:
        s,a,x=pending_fixture(status);coupled=copy.deepcopy(s);coupled.decoupled=False
        old=V.plan(coupled,[x],AT);new=V.plan(s,[x],AT)
        self.assertFalse(old['orders']);self.assertEqual(ords(new)[0][:4],('X','mobile','confirmed',400))
        original=s.orders[B.bid(a)];after=new['final_state']['orders'][B.bid(a)]
        self.assertEqual((after['pool'],after['role'],after['qty'],after['status']),(original.pool,original.role,original.qty,original.status))
        self.assertEqual(new['final_state']['lots'][-1]['pool'],'probe')
        self.assertTrue(any(e['diagnostic']['primary_reason']=='same_attempt_probe_pending' and e['result'] is False for e in new['migrations']))
 def test_whole_old_transfer_too_large_new_minimum_fits_then_rechecks_live_space(self):
    lots=[B.N.Lot('Y'+str(k),'Y'+str(k),'T'+str(k),'old','confirmed',590,100,99.9,attempt='old') for k in range(10)]
    lots.append(B.N.Lot('P','P','S','E-S','probe',380,40,45,role='core',attempt='A-S'))
    s=state({'S':1,**{'T'+str(k):1 for k in range(10)}},cash=391000,lots=lots,prices={**{'Y'+str(k):100 for k in range(10)},'P':50},historical_shared_loss=123)
    x=item('X','S',p='50',floor='45',target=400);bind(s,[x],{'X':'S'});r=V.plan(s,[x],AT)
    self.assertEqual(ords(r)[0][:4],('X','mobile','confirmed',100));self.assertEqual(r['final_state']['lots'][-1]['pool'],'probe')
    d=next(e['diagnostic'] for e in r['migrations'] if e['phase']=='request')
    self.assertEqual(d['primary_reason'],'confirmed_capacity_for_whole_old_transfer');self.assertEqual(d['old_filled_probe_transfer_required'],19000);self.assertTrue(d['request_gross_fits_pool_after_fee'])
    t=from_result(r);t.context='later-recheck';t.phase='manual-unit';self.assertFalse(t.migrate('S'));later=t.migrations[-1]['diagnostic']
    self.assertEqual(later['current_confirmed_capital'],595000);self.assertGreater(later['old_transfer_deficit'],d['old_transfer_deficit'])
    fee=float(B.LR.fees(200,D(100),SCHEDULE,'sell',D(1)));t.sell('Y0',200,100,fee=fee)
    before=(t.cash,t.nav,t.resources(),t.shared_loss);self.assertTrue(t.migrate('S'));self.assertEqual(before,(t.cash,t.nav,t.resources(),t.shared_loss));self.assertEqual(t.lots[-1].pool,'confirmed')
 def test_cap_full_still_rejects(self):
    lots=[B.N.Lot(str(k),'Y'+str(k),'T'+str(k),'old','confirmed',600,100,99.9,attempt='old') for k in range(10)];lots.append(B.N.Lot('P','P','S','E-S','probe',380,40,45,attempt='A-S'))
    s=state({'S':1,**{'T'+str(k):1 for k in range(10)}},cash=381000,lots=lots,prices={**{'Y'+str(k):100 for k in range(10)},'P':50});x=item('X','S',p='50',floor='45',target=400);bind(s,[x],{'X':'S'});r=V.plan(s,[x],AT)
    self.assertFalse(r['orders']);self.assertIn('pool_capital',str(r['rejected']))
 def test_industry_combines_probe_confirmed_and_old_attempt(self):
    lots=[B.N.Lot('P','P','S','old','probe',380,45,49,attempt='OLD'),B.N.Lot('C','C','S','E-S','confirmed',1600,45,49,attempt='A-S')]
    s=state(cash=901000,lots=lots,prices={'P':50,'C':50});x=item('X','S',p='50',floor='49',target=400);bind(s,[x],{'X':'S'});r=V.plan(s,[x],AT)
    self.assertFalse(r['orders']);self.assertIn('sector_capital',str(r['rejected']));self.assertEqual(r['final_state']['lots'][0]['pool'],'probe')
 def test_targets_minimum_and_step_not_relaxed(self):
    s=state();high=item('X','S',p='250',floor='240',target=100);core=item('C','S',role='core',p='100',floor='50',target=100);star=item('STAR','S',p='50',floor='45',target=201,minimum=200,step=1);bind(s,[high,core,star],{'X':'S','C':'S','STAR':'S'})
    self.assertFalse(V.plan(s,[high,core],AT)['orders']);r=V.plan(s,[star],AT,'two_pass');self.assertEqual(r['orders'][0]['quantity'],201)
 def test_late_partial_fill_and_cancel_ack_keep_role_and_occupancy(self):
    s,a,x=pending_fixture();r=V.plan(s,[x],AT);t=from_result(r);oid=B.bid(a);before=t.resources();loss=t.shared_loss
    t.cancel(oid);self.assertEqual(before,t.resources());t.fill(oid,40,50,execution_bar=B.J.ordinal(AT.date()))
    self.assertAlmostEqual(t.resources()[0],before[0]);self.assertAlmostEqual(t.resources()[1],before[1]);self.assertEqual(t.orders[oid].qty,60);self.assertEqual(t.orders[oid].pool,'probe');self.assertEqual(t.lots[-1].role,'core');self.assertEqual(t.lots[-1].pool,'probe');self.assertFalse(t.migrate('S'))
    t.cancel_ack(oid);self.assertEqual(t.orders[oid].qty,0);self.assertEqual(t.lots[-1].role,'core');self.assertEqual(t.lots[-1].pool,'confirmed');self.assertGreaterEqual(t.shared_loss,loss);self.assertEqual(t.orders[B.bid(x)].qty,400)
 def test_failed_no_order_candidate_still_migrates(self):
    p=B.N.Lot('P','P','S','E-S','probe',2000,9,9.9,attempt='A-S');s=state(cash=0,receivables=980000,lots=[p],prices={'P':10});x=item('X','S');bind(s,[x],{'X':'S'});r=V.plan(s,[x],AT)
    self.assertFalse(r['orders']);self.assertEqual(r['final_state']['lots'][0]['pool'],'confirmed');self.assertEqual(r['migrations'][0]['moved'],['P'])
 def test_failed_trial_keeps_previous_legal_migrations_and_reservations(self):
    p=B.N.Lot('P','P','S','E-S','probe',380,40,45,attempt='A-S');s=state({'S':1,'T':0},cash=981000,lots=[p],prices={'P':50});m=item('M','S',p='50',floor='45',target=400);c=item('C','T',rank=1,role='core',target=100);bind(s,[m,c],{'M':'S','C':'T'});r=V.plan(s,[m,c],AT,'two_pass');before=B.digest(s.view());bad=copy.deepcopy(r['orders']);next(x for x in bad if x['sid']=='C')['quantity']=100000
    trial=B.fixed_validation(s,[m,c],r['attempts'],bad,AT,r['migrations']);self.assertFalse(trial['valid']);self.assertIn(B.bid(m),trial['state'].orders);self.assertEqual(trial['state'].lots[0].pool,'confirmed');self.assertEqual(before,B.digest(s.view()));self.assertEqual(ords(r),ords(V.plan(s,[m,c],AT,'two_pass')))
 def test_same_stock_core_first_pending_and_old_receipt_unchanged(self):
    s=state();c=item('X','S',role='core',target=100);m=item('X','S',target=400);bind(s,[c,m],{'X':'S'})
    for mode in ['single_pass','two_pass']:
        r=V.plan(s,[m,c],AT,mode);self.assertEqual(r['orders'][0]['role'],'core');self.assertEqual(len(r['orders']),1);self.assertFalse(r['proposed_stock_receipt_consumptions'])
    t=copy.deepcopy(s);t.consumed.add(m['CP1_id']);self.assertFalse(V.plan(t,[m],AT)['orders'])
    t=copy.deepcopy(s);t.pending_sells.add('X');self.assertFalse(V.plan(t,[m],AT)['orders'])
 def test_coupled_no_order_original_identity_and_pure_repeat(self):
    s=state(decoupled=False,cash=0,receivables=1000000);x=item('X','S');bind(s,[x],{'X':'S'});before=B.digest(s.view())
    for mode in ['single_pass','two_pass']:
        got=V.plan(s,[x],AT,mode);native=B.plan(s,[x],AT,mode);self.assertEqual(B.digest(V.old_observable(got)),B.digest(native));self.assertFalse(got['orders']);self.assertEqual(before,B.digest(s.view()))
        self.assertEqual(B.digest(got),B.digest(V.plan(s,[x],AT,mode)))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NewPolicyTests);r=unittest.TextTestRunner(verbosity=2).run(suite)
    (V.O/'TEST_RESULTS.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),scope='new policy synthetic budget/allocator regressions, native budget callbacks only; no real ledger or historical account',previous18_tests_not_claimed_as_new_policy=True),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
