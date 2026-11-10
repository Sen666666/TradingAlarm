import unittest,copy,subprocess,sys
from step_cap import *
import test_c_selector as T
F=T.F;fixture=T.fixture

class Tests(unittest.TestCase):
    def test_only_max_q_changes_not_priority_qualification_or_snapshot(self):
        s,ds,e=fixture([],[F.demand(q=9000,mark='10',floor='9.99')],cash='1000000')
        before=J.digest((s,ds,e));dd,rows=cap2(s,ds)
        self.assertEqual(dd[0]['max_q'],1900);self.assertEqual(J.digest((s,ds,e)),before)
        self.assertEqual(C.transform(s,ds,e)[2]['stock_priority'],C.transform(s,dd,e)[2]['stock_priority'])
    def test_all_original_caps_below_two_recovers_C10(self):
        s,ds,e=fixture([],[F.demand('A',1000,mark='10',floor='9.99'),F.demand('B',1000,mark='10',floor='9.99')],cash='1000000')
        a=C.solve_C(s,ds,e);b=solve_C2(s,ds,e)
        self.assertEqual((a['Q'],a['D'],a['validation']),(b['Q'],b['D'],b['validation']))
    def test_existing_six_percent_can_add_two_not_total_two(self):
        s,ds,e=fixture([F.lot('NEW',6000,'10','9.999',sector='NEW')],[F.demand(q=3900,mark='10',floor='9.99')],cash='940000',ranks={'NEW':1})
        r=solve_C2(s,ds,e);self.assertEqual(r['Q']['NEW'],1900);self.assertEqual(r['mobile_targets']['NEW'],7900)
    def test_nine_percent_remainder_and_no_fresh_or_overcap(self):
        s,ds,e=fixture([F.lot('NEW',9000,'10','9.999',sector='NEW')],[F.demand(q=900,mark='10',floor='9.99')],cash='910000',ranks={'NEW':1})
        self.assertEqual(solve_C2(s,ds,e)['Q']['NEW'],900)
        self.assertEqual(solve_C2(s,[],e)['mobile_targets']['NEW'],9000)
        ds[0]['max_q']=0;self.assertEqual(solve_C2(s,ds,e)['Q']['NEW'],0)
    def test_three_percent_STAR_minimum_rejected_only_by_C2_target(self):
        for held in (0,100):
            lots=[F.lot('NEW',held,'150','149.99',sector='NEW')] if held else []
            s,ds,e=fixture(lots,[F.demand(q=500,mark='150',floor='149.9',quantity=F.STAR)],cash=str(1000000-held*150),ranks={'NEW':1})
            small=solve_C2(s,ds,e);large=C.solve_C(s,ds,e)
            self.assertEqual(small['Q']['NEW'],0);self.assertGreaterEqual(large['Q']['NEW'],200)
            self.assertTrue(small['C2_upper_bounds'][0]['target_minlot_lost']);self.assertEqual(ds[0]['quantity']['buy_minimum'],200)
    def test_fees_separate_from_gross_and_no_minlot_exception(self):
        s,ds,e=fixture([],[F.demand(q=9000,mark='10',floor='9.99')],cash='1000000');r=solve_C2(s,ds,e);q=r['Q']['NEW'];p=D('10.005')
        self.assertLessEqual(D(q)*p,20000);self.assertGreater(J.buy_cost(ds[0],q),D(q)*p)
        ds[0]['max_q']=99;self.assertEqual(solve_C2(s,ds,e)['Q']['NEW'],0)
    def test_small_fits_no_donation_large_requires_donation(self):
        s,ds,e=fixture([F.lot(q=8700,mark='100',floor='99.99')],[F.demand(q=9000,mark='10',floor='9.99')],cash='130000',scores={'NEW':90,'OLDSEC':10})
        self.assertFalse(solve_C2(s,ds,e)['D']);self.assertTrue(C.solve_C(s,ds,e)['D'])
    def test_unavailable_core_and_tighter_risk_not_relaxed(self):
        old=F.lot();old['sellable_qty']=0
        s,ds,e=fixture([old],[F.demand(q=900,mark='100',floor='1')]);r=solve_C2(s,ds,e)
        self.assertFalse(r['D']);self.assertTrue(r['validation']['ok'])
        s,ds,e=fixture([F.lot(role='core')],[F.demand(q=900,mark='100',floor='1')]);self.assertFalse(solve_C2(s,ds,e)['D'])
    def test_same_industry_replacement_and_joint_budgets(self):
        old=F.lot(q=1900,floor='99.9',sector='S');d=F.demand(q=900,mark='100',floor='99.8',sector='S');d.update(use='G',industry_target=D(200000))
        s,ds,e=fixture([old],[d],cash='810000',ranks={'OLD':2,'NEW':1});r=solve_C2(s,ds,e)
        self.assertEqual(r['Q']['NEW'],100);self.assertEqual(r['D']['OLD'],100)
        self.assertTrue(all(D(z['residual'])>=0 for z in r['validation']['checks']))
    def test_zero_cap_preserves_na_slots_and_receipt_identity(self):
        keys,_=C.B.priority_plan([dict(sid=x,rank=10*(i+1),role='mobile') for i,x in enumerate('abc')],lambda sid,day:{'a':5.,'b':None,'c':8.}[sid],'d')
        ds=[F.demand(x,500,mark='150' if x=='b' else '10',floor='149.9' if x=='b' else '9.99',quantity=F.STAR if x=='b' else F.MAIN,sector='S') for x in 'abc']
        s,ds,e=fixture([],ds,cash='1000000',ranks=keys);dd,rows=cap2(s,ds)
        self.assertEqual(dd[1]['max_q'],0);self.assertEqual(len(dd),3)
        self.assertEqual(C.transform(s,ds,e)[2]['stock_priority'],C.transform(s,dd,e)[2]['stock_priority'])
        self.assertEqual([d['receipt_binding'] for d in dd],[d['receipt_binding'] for d in ds])
    def test_rehashed_wrong_mode_binding_or_old_input_rejected(self):
        s,ds,e=fixture([],[F.demand(q=9000,mark='10',floor='9.99')],cash='1000000');x=dict(snapshot=s,B_demands=ds,industry_evidence=e);r=solve_C2(s,ds,e)
        r['C2_selector_sha256']='wrong';r['result_id']=J.digest({k:v for k,v in r.items() if k!='result_id'})
        with self.assertRaisesRegex(AssertionError,'source binding'):verify(x,r)
        r=solve_C2(s,ds,e);xx=copy.deepcopy(x);xx['B_demands'][0]['receipt_id']='later-fresh'
        with self.assertRaises(AssertionError):verify(xx,r)
    def test_crossprocess_exact_and_analysis_only(self):
        s,ds,e=fixture([],[F.demand(q=9000,mark='10',floor='9.99')],cash='1000000');r=solve_C2(s,ds,e)
        self.assertFalse(r['submit_allowed']);self.assertEqual(r['validation']['actual_cash_released'],0)
        p=O/'test-restart';save(p/'INPUT.json',dict(snapshot=s,B_demands=ds,industry_evidence=e));save(p/'RESULT.json',r)
        subprocess.run([sys.executable,'-B',str(O/'step_cap.py'),str(p/'INPUT.json'),sha(p/'INPUT.json'),str(p/'RESULT.json'),str(p/'RESTORED.json')],check=True)
        self.assertTrue(read(p/'RESTORED.json')['exact'])

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    save(O/'SYNTHETIC_RESULTS.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),financial_events=0))
    raise SystemExit(not r.wasSuccessful())
