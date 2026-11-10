"""Affected actual-Pair tests; original16 bodies reused without original writes."""
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import copy, io, pickle, sys, tempfile, unittest
import composition as A
E, J, IO = A.E, A.J, A.IO
sys.modules.setdefault('d1_runner', E)
T = A.load('composition_frozen_D1_lifecycle_tests', A.D1/'test_real_pair.py')

def setup(role='mobile', enabled=True):
    r,a,i,t,c,t1,*rest = T.setup(role=role, ref='B_diag', enabled=enabled)
    r.__class__ = A.Composition
    r.bind_composition('PVR_SLOT1', {'test':'native fixture'})
    return r,a,i,t,c,t1,*rest

class Affected(unittest.TestCase):
    def test_PVR_reversal_only_new_intents_retained_order_key_and_single_receipt_exact(self):
        r,a,i,t,c,t1,prices,*_ = setup()
        i['rank']=7
        r.opening(a,t)
        old_order=copy.deepcopy(a.buys['A'].__dict__)
        oid=a.buys['A'].order_id
        old_meta=copy.deepcopy(a.order_meta[oid]); old_delay=copy.deepcopy(a.d1_orders[oid])
        old_consumed=set(a.budget.consumed); reserve=a.budget.resources()[2]
        b=copy.deepcopy(i);b.update(sid='B',rank=1,CP1_id='new-B')
        d=copy.deepcopy(i);d.update(sid='C',rank=2,CP1_id='new-C')
        a.pending=[b,d];a.decisions.append(dict(at=c,intents=copy.deepcopy(a.pending)))
        original=A.N.SCORES
        A.N.SCORES=SimpleNamespace(manifest_sha256=original.manifest_sha256,
            at=lambda sid,day: {'B':1.,'C':9.}[sid])
        try:r.apply_new_priority(c)
        finally:A.N.SCORES=original
        self.assertEqual([(x['sid'],x['rank']) for x in a.pending],[('B',2),('C',1)])
        self.assertEqual(a.buys['A'].__dict__,old_order)
        self.assertEqual(a.order_meta[oid],old_meta)
        self.assertEqual(a.d1_orders[oid],old_delay)
        self.assertEqual(a.budget.resources()[2],reserve)
        self.assertEqual(a.budget.consumed,old_consumed)
        T.closing(r,a,c);a.fixture_state['price']=J.D(11);r.opening(a,t1)
        self.assertGreater(a.quantity('A'),0)
        self.assertEqual(a.budget.consumed,old_consumed)
        self.assertEqual(len([x for x in a.journal if x['kind']=='real_reserve']),1)

    def test_core_successful_reservation_zero_fill_still_suppresses_same_stock_mobile(self):
        r,a,i,t,c,t1,*_ = setup('core')
        mobile=T.T.intent(at=i['clock'].decision_at,rid='unconsumed-mobile')
        mobile['clock']=replace(mobile['clock'],earliest_execution_at=t)
        mobile['rank']=i['rank']
        a.pending=[i,mobile]
        r.opening(a,t)
        self.assertEqual(a.quantity('A'),0)
        self.assertEqual(len(a.buys),1)
        self.assertEqual(a.order_meta[a.buys['A'].order_id]['role'],'core')
        self.assertNotIn('unconsumed-mobile',a.budget.consumed)
        self.assertEqual(len([x for x in a.journal if x['kind']=='real_reserve']),1)

    def test_composed_openNAV_counter_inherits_original_gap_rule(self):
        old_setup=T.setup
        def composed(*args,**kw):
            result=old_setup(*args,**kw)
            r=result[0]
            if r.reference=='B_diag':
                r.__class__=A.Composition
                r.bind_composition('PVR_SLOT1',{'test':'gap fixture'})
            return result
        try:
            T.setup=composed
            test=T.Tests('test_overnight_gap_amend_does_not_change_fresh_intent_decision_NAV_or_quantity')
            test.test_overnight_gap_amend_does_not_change_fresh_intent_decision_NAV_or_quantity()
        finally:T.setup=old_setup

    def test_composed_native_checkpoint_retained_order_full_state_and_mode_guard(self):
        r,a,i,t,c,t1,*_=setup();r.opening(a,t);T.closing(r,a,c)
        root=Path(tempfile.mkdtemp(prefix='PVR-D1-native-',dir=A.O/'tests-tmp'))
        with IO.atomic_runner_outputs(r,A.L,root,canonicalize=J.W.canon):r.checkpoint(root,c)
        other,*_=setup()
        with IO.atomic_runner_outputs(other,A.L,root/'restart',canonicalize=J.W.canon):
            self.assertEqual(other.restore(root/'checkpoint.pkl'),c)
        self.assertTrue(A.Q.equal({k:v for k,v in a.__dict__.items() if k not in ('market','facts')},
            {k:v for k,v in other.accounts['B'].__dict__.items() if k not in ('market','facts')}))
        wrong,*_=setup();wrong.bind_composition('H1',{'test':'native fixture'})
        with self.assertRaisesRegex(AssertionError,'binding mismatch'):
            with IO.atomic_runner_outputs(wrong,A.L,root/'wrong',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
        wrong,*_=setup();wrong.composition_binding['horizon']={'test':'different horizon'}
        with self.assertRaisesRegex(AssertionError,'binding mismatch'):
            with IO.atomic_runner_outputs(wrong,A.L,root/'wrong-horizon',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')

def run():
    A.N.configure_scores()
    (A.O/'tests-tmp').mkdir(parents=True,exist_ok=True)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(T.Tests),
                             unittest.defaultTestLoader.loadTestsFromTestCase(Affected)])
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    IO.write_bytes(A.O/'NATIVE_TEST_LOG.txt',log.getvalue().encode())
    IO.write_json(A.O/'NATIVE_GATE.json',J.W.canon(dict(passed=result.wasSuccessful(),
        tests=result.testsRun,original_native_D1_reexecuted=16,affected_native=4,
        failures=len(result.failures),errors=len(result.errors),details=T.DETAIL,
        D1_source_sha256=A.sha(A.D1/'d1_runner.py'),PVR_source_sha256=A.sha(A.P/'native_rank.py'),
        original_test_body_sha256=A.sha(A.D1/'test_real_pair.py'),composition_sha256=A.sha(A.O/'composition.py'),
        full_financial_paths=0)))
    print(log.getvalue(),flush=True)
    assert result.wasSuccessful(),'native composition gates failed'

if __name__=='__main__':run()
