import unittest,copy,subprocess,sys,json
from c_selector import *
import test_selector as T
F=T.F
D=Decimal

def fixture(lots,ds,*,cash='500000',ranks=None,scores=None):
    s,ds=T.fixture(lots,ds,cash=cash,ranks=ranks)
    sec={z['sector'] for z in s['lots']}|{d['sector'] for d in ds}
    e=dict(day=s['at'][:10],known_at=s['at'],industry_H1={k:(scores or {}).get(k,50) for k in sec})
    return s,ds,e

class Tests(unittest.TestCase):
    def test_only_rank_fields_change(self):
        s,ds,e=fixture([F.lot()],[F.demand()],scores={'NEW':90,'OLDSEC':10})
        ss,dd,a=transform(s,ds,e);self.assertTrue(a['financial_fields_and_receipts_exact'])
        self.assertEqual(ss['rows'],s['rows']);self.assertEqual(dd[0]['receipt_binding'],ds[0]['receipt_binding'])
    def test_same_industry_recovers_frozen_B(self):
        s,ds,e=fixture([F.lot(sector='S')],[F.demand(sector='S',q=900,mark='100',floor='70')])
        a=B.solve_B(s,ds);c=solve_C(s,ds,e);self.assertEqual((a['Q'],a['D']),(c['Q'],c['D']))
    def test_high_stock_PVR_low_industry_can_be_donor(self):
        s,ds,e=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')],ranks={'OLD':1,'NEW':2},scores={'NEW':90,'OLDSEC':10})
        self.assertEqual(B.solve_B(s,ds)['Q']['NEW'],0)
        c=solve_C(s,ds,e);self.assertEqual(c['Q']['NEW'],900);self.assertGreater(c['D']['OLD'],0)
    def test_high_industry_old_no_fresh_not_funded_for_lower(self):
        s,ds,e=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')],scores={'NEW':10,'OLDSEC':90})
        c=solve_C(s,ds,e);self.assertFalse(c['D']);self.assertEqual(c['mobile_targets']['OLD'],5000)
    def test_no_fresh_old_retains_no_growth(self):
        s,ds,e=fixture([F.lot()],[]);r=solve_C(s,ds,e)
        self.assertEqual(r['mobile_targets']['OLD'],5000);self.assertFalse(r['D'])
    def test_high_rank_no_opportunity_does_not_take_slots(self):
        s,ds,e=fixture([],[F.demand(q=100)],cash='1000000',scores={'NEW':10});e['industry_H1']['EMPTY']=100
        r=solve_C(s,ds,e);self.assertNotIn('EMPTY',r['C_rank_binding']['industry_order']);self.assertEqual(r['Q']['NEW'],100)
    def test_stock_PVR_NA_and_ties_preserve_original_subsequence(self):
        keys,logs=B.priority_plan([dict(sid=x,rank=10*(i+1),role='mobile') for i,x in enumerate('abc')],lambda sid,day:{'a':5.,'b':None,'c':8.}[sid],'d')
        s,ds,e=fixture([],[F.demand(x,100,sector='S') for x in 'abc'],cash='1000000',ranks=keys)
        ss,dd,a=transform(s,ds,e);self.assertEqual([d['sid'] for d in sorted(dd,key=lambda d:d['priority'])],['c','b','a'])
        self.assertFalse(next(v for v in logs if v['sid']=='b')['PVR_ready'])
    def test_industry_unknown_future_and_wrong_date_rejected(self):
        s,ds,e=fixture([],[F.demand()],cash='1000000');e['industry_H1']['NEW']=None
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):solve_C(s,ds,e)
        e['industry_H1']['NEW']=50;e['known_at']='2025-07-04 15:10:00+08:00'
        with self.assertRaisesRegex(ValueError,'future'):solve_C(s,ds,e)
        e['known_at']=s['at'];e['day']='2025-07-04'
        with self.assertRaisesRegex(ValueError,'date mismatch'):solve_C(s,ds,e)
    def test_industry_tie_uses_sector_id(self):
        s,ds,e=fixture([],[F.demand('b',100,sector='B'),F.demand('a',100,sector='A')],cash='1000000')
        self.assertEqual(transform(s,ds,e)[2]['industry_order'],['A','B'])
    def test_three_stocks_cannot_manufacture_eighty_percent(self):
        ds=[F.demand(x,q=1000,mark='100',floor='99.9',sector='S') for x in 'ABC']
        s,ds,e=fixture([],ds,cash='1000000');r=solve_C(s,ds,e)
        self.assertEqual(list(r['Q'].values()),[900,900,900]);self.assertLessEqual(sum(r['Q'].values())*100,300000);self.assertFalse(r['D'])
    def test_G_twenty_not_G_plus_S_eighty(self):
        ds=[F.demand(x,q=1000,mark='100',floor='99.9',sector='S') for x in 'ABC']
        for d in ds:d.update(use='G',industry_target=D(200000))
        s,ds,e=fixture([],ds,cash='1000000');r=solve_C(s,ds,e)
        self.assertLessEqual(sum(r['Q'].values())*D('100.05'),200000)
        for d in ds:self.assertEqual(d['industry_target'],200000)
    def test_empty_D_no_sale_and_unavailable_cannot_supply(self):
        s,ds,e=fixture([F.lot()],[F.demand(q=900,mark='100',floor='99.9')]);self.assertFalse(solve_C(s,ds,e)['D'])
        s['lots'][0]['sellable_qty']=0;ds[0]['floor']=D(70);self.assertFalse(solve_C(s,ds,e)['D'])
    def test_same_industry_replacement(self):
        z=F.lot(q=1900,floor='99.9',sector='S');d=F.demand(q=900,mark='100',floor='99.8',sector='S');d.update(use='G',industry_target=D(200000))
        s,ds,e=fixture([z],[d],cash='810000',ranks={'OLD':2,'NEW':1});r=solve_C(s,ds,e)
        self.assertEqual(r['Q']['NEW'],900);self.assertEqual(r['D']['OLD'],900)
    def test_star_new_minimum_and_core_not_donated(self):
        s,ds,e=fixture([F.lot('NEW',q=50,mark='10',floor='9',sector='NEW')],[F.demand(q=199,mark='10',floor='9',quantity=F.STAR)],ranks={'NEW':1})
        self.assertEqual(solve_C(s,ds,e)['Q']['NEW'],0)
        s,ds,e=fixture([F.lot('CORE',q=5000,role='core')],[F.demand(q=900,mark='100',floor='70')]);self.assertFalse(solve_C(s,ds,e)['D'])
    def test_same_stock_inconsistent_source_identity_is_rejected(self):
        s,ds,e=fixture([F.lot('NEW',q=50)],[F.demand(q=199,quantity=F.STAR)])
        with self.assertRaisesRegex(ValueError,'same stock'):solve_C(s,ds,e)
    def test_forged_result_or_source_cannot_restore(self):
        s,ds,e=fixture([],[F.demand(q=100)],cash='1000000');x=dict(snapshot=s,B_demands=ds,industry_evidence=e);r=solve_C(s,ds,e)
        r['Q']['NEW']=500
        with self.assertRaisesRegex(AssertionError,'body'):verify_result(x,r)
        r=solve_C(s,ds,e);r['C_selector_sha256']='wrong';r['result_id']=J.digest({k:v for k,v in r.items() if k!='result_id'})
        with self.assertRaisesRegex(AssertionError,'binding'):verify_result(x,r)
    def test_crossprocess_result_exact_and_input_unchanged(self):
        s,ds,e=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')]);r=solve_C(s,ds,e)
        p=HERE/'test-restart';save(p/'INPUT.json',dict(snapshot=s,B_demands=ds,industry_evidence=e));save(p/'RESULT.json',r)
        subprocess.run([sys.executable,'-B',str(HERE/'c_selector.py'),str(p/'INPUT.json'),sha(p/'INPUT.json'),str(p/'RESULT.json'),str(p/'RESTORED.json')],check=True)
        self.assertTrue(read(p/'RESTORED.json')['exact'])

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    save(HERE/'SYNTHETIC_RESULTS.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),financial_events=0))
    raise SystemExit(not r.wasSuccessful())
