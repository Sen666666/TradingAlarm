import unittest,copy,json,hashlib,sys,subprocess
from c_batch20 import *
import test_c_selector as T
F=T.F;fixture=T.fixture
AT='2025-07-03 15:10:00+08:00';NEXT='2025-07-04 15:10:00+08:00'

def line(layer='A',qty=5000,opp=0):return dict(layer=layer,sid=layer,qty=qty,opp=opp,mandatory=0,relative_ratio='1')
def book(lines=None,proofs=None):
    b=BatchBook('fixture-account','fixture-native-observation-source',lines or [line('A'),line('B')],proofs)
    b.begin(AT,'1000000',{k:'100' for k in b.lines});return b
def proof(pid,qty,kind='original_protection_failure',known=AT):
    return dict(kind=kind,layer='A',qty=qty,known_at=known,relative_ratio='1',original_evidence_id=pid)

class Tests(unittest.TestCase):
    def test_multiple_goals_share_one_twenty_budget(self):
        b=book();b.approve('p1',{'A':1000},target_binding='goal-one');b.approve('p2',{'B':1000},target_binding='goal-two')
        self.assertEqual(D(b.batch['new']),200000)
        before=b.dumps()
        with self.assertRaisesRegex(ValueError,'exhausted'):b.approve('p3',{'A':1500},target_binding='fresh-other')
        self.assertEqual(b.dumps(),before)
    def test_same_cursor_plan_and_receipt_do_not_refresh(self):
        b=book();b.approve('all',{'A':2000},target_binding='canonical-one');old=b.dumps()
        b.begin(AT,'1000000',{'A':'100','B':'100'});b.approve('all',{'A':2000},target_binding='canonical-one')
        self.assertEqual(b.dumps(),old)
        with self.assertRaisesRegex(ValueError,'identity changed'):b.approve('all',{'A':2000},target_binding='fresh-two')
        with self.assertRaisesRegex(ValueError,'already frozen'):b.begin(AT,'999999',{'A':'100','B':'100'})
    def test_fill_shrink_cancel_ack_never_refund_current_batch(self):
        b=book();b.approve('all',{'A':2000},target_binding='one')
        b.observe_fill('A',500,'103','real-observation-1',source_binding=b.source_binding,at='2025-07-04 09:30:00+08:00')
        b.shrink('A',1000);b.cancel_request('A');self.assertEqual(b.lines['A']['opp'],1000)
        self.assertFalse(b.preview({'B':100})['ok']);b.cancel_ack('A')
        self.assertEqual(D(b.batch['new']),200000);self.assertFalse(b.preview({'B':100})['ok'])
        self.assertEqual(b.history[-1]['actual_gross'],'51500');self.assertFalse(b.history[-1]['cash_changed_by_book'])
        b.begin(NEXT,'1000000',{'A':'100','B':'100'});self.assertEqual(D(b.batch['carry']),0);self.assertTrue(b.preview({'B':2000})['ok'])
    def test_cross_day_only_residual_carry_revalued(self):
        b=book();b.approve('all',{'A':2000},target_binding='one')
        b.observe_fill('A',500,'101','fill',source_binding=b.source_binding,at='2025-07-04 09:30:00+08:00')
        b.begin(NEXT,'1000000',{'A':'110','B':'100'})
        self.assertEqual(D(b.batch['carry']),165000);self.assertEqual(D(b.batch['new']),0)
        self.assertTrue(b.preview({'B':300})['ok']);self.assertFalse(b.preview({'B':400})['ok'])
    def test_unfilled_and_cancel_unack_carry_cannot_disappear(self):
        b=book();b.approve('p',{'A':2000},target_binding='one');b.cancel_request('A')
        b.begin(NEXT,'1000000',{'A':'100','B':'100'});self.assertEqual(D(b.batch['carry']),200000)
        self.assertFalse(b.preview({'B':100})['ok']);b.cancel_ack('A');self.assertFalse(b.preview({'B':100})['ok'])
    def test_overhang_blocks_new_opp_but_mandatory_still_exists(self):
        b=book([line('A',opp=3000),line('B')],{'mandatory':proof('m',5000)})
        self.assertTrue(b.preview({})['ok']);self.assertTrue(b.preview({})['existing_overhang'])
        self.assertFalse(b.preview({'B':100})['ok'])
        b.mandatory('A',5000,'mandatory',at=AT);self.assertEqual(max(b.lines['A']['opp'],b.lines['A']['mandatory']),5000)
        self.assertEqual(D(b.batch['carry']),300000) # No same-batch waiver/refund.
    def test_independent_mandatory_prefix_union_not_double_counted(self):
        p={'m1':proof('m1',1000),'m2':proof('m2',2000)}
        b=BatchBook('a','src',[line('A')],p);b.mandatory('A',1000,'m1',at=AT);b.begin(AT,'1000000',{'A':'100'})
        v=b.preview({'A':1500});self.assertEqual(D(v['additional']),50000);self.assertEqual(v['lines'][0]['native_union'],1500)
        b.approve('p',{'A':1500},target_binding='goal');b.mandatory('A',2000,'m2',at=AT)
        self.assertEqual(D(b.batch['new']),50000);self.assertEqual(max(b.lines['A']['opp'],b.lines['A']['mandatory']),2000)
    def test_rank_target_decline_cannot_be_mandatory_and_future_rejected(self):
        b=book(proofs={'bad':proof('x',5000,'rank_decline'),'future':proof('f',5000,known=NEXT)})
        with self.assertRaisesRegex(ValueError,'independent'):b.mandatory('A',5000,'bad',at=AT)
        with self.assertRaisesRegex(ValueError,'future'):b.mandatory('A',5000,'future',at=AT)
        with self.assertRaisesRegex(ValueError,'registry'):b.mandatory('A',5000,'missing',at=AT)
    def test_partial_split_same_domain_and_fractional_atomic_reject(self):
        b=book();b.approve('p',{'A':2000},target_binding='goal');b.observe_fill('A',500,'101','f',source_binding=b.source_binding,at=NEXT)
        b.observe_split('A','2');self.assertEqual(b.lines['A']['opp'],3000);self.assertEqual(D(b.batch['new']),200000)
        self.assertEqual(D(b.preview({'A':3000})['additional']),0)
        b.begin(NEXT,'1000000',{'A':'50','B':'100'});self.assertEqual(D(b.batch['carry']),150000)
        c=book([line('A',qty=3)]);c.approve('p',{'A':1},target_binding='goal');before=c.dumps()
        with self.assertRaisesRegex(ValueError,'fractional'):c.observe_split('A','.5')
        self.assertEqual(c.dumps(),before)
    def test_unknown_carry_and_observation_source_fail_closed(self):
        b=BatchBook('a','src',[line('A',opp=1)])
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):b.begin(AT,'1000000',{})
        b.begin(AT,'1000000',{'A':'100'})
        with self.assertRaisesRegex(ValueError,'source'):b.observe_fill('A',1,'100','f',source_binding='wrong',at=NEXT)
    def test_restore_preserves_used_and_requires_external_bindings(self):
        b=book();b.approve('p',{'A':2000},target_binding='goal');raw=b.dumps();h=hashlib.sha256(raw.encode()).hexdigest()
        r=BatchBook.loads(raw,trusted_sha256=h,account_id=b.account_id,source_binding=b.source_binding,actual_commitments=b.commitments())
        self.assertEqual(r.dumps(),raw);self.assertFalse(r.preview({'B':100})['ok'])
        x=json.loads(raw);x['body']['batch']['new']='0';x['state_id']=J.digest(x['body']);bad=json.dumps(x)
        with self.assertRaisesRegex(ValueError,'trusted'):BatchBook.loads(bad,trusted_sha256=h,account_id=b.account_id,source_binding=b.source_binding,actual_commitments=b.commitments())
        actual=b.commitments();actual['A']['opp']=0
        with self.assertRaisesRegex(ValueError,'commitments'):BatchBook.loads(raw,trusted_sha256=h,account_id=b.account_id,source_binding=b.source_binding,actual_commitments=actual)
    def test_empty_G_and_mature_S_can_deploy_near_ninety_eighty(self):
        for n,use in [(9,'G'),(8,'S')]:
            ds=[F.demand(str(i),q=9900,mark='10',floor='9.5',sector='S'+str(i//2) if use=='G' else 'S') for i in range(n)]
            for d in ds:d.update(use=use,industry_target=D(200000 if use=='G' else 800000))
            s,ds,e=fixture([],ds,cash='1000000');base=C.solve_C(s,ds,e);r=solve_C20(s,ds,e)
            self.assertEqual((r['Q'],r['D']),(base['Q'],base['D']));self.assertFalse(r['D'])
            self.assertGreaterEqual(sum(r['Q'].values())*10,880000 if use=='G' else 780000)
    def test_full_batch_Q_D_reclipped_not_posthoc_D_cut(self):
        ds=[F.demand(x,q=900,mark='100',floor='95',sector='S') for x in 'ABCD']
        s,ds,e=fixture([F.lot(q=9000,mark='100',floor='95')],ds,cash='100000',scores={'OLDSEC':10,'S':90})
        base=C.solve_C(s,ds,e);r=solve_C20(s,ds,e)
        self.assertLess(sum(r['Q'].values()),sum(base['Q'].values()))
        self.assertLessEqual(sum(D(v['capital']) for v in r['donors']['rows']),200000)
        self.assertTrue(r['validation']['ok']);self.assertEqual([d['max_q'] for d in ds],[900]*4)
    def test_joint_risk_can_reject_all_without_selling_budget(self):
        core=F.lot('CORE',6000,'100','90.08333333333333333333333333',role='core',sector='LEGACY')
        mobile=F.lot('OLD',1000,'100','99.99',sector='OLDSEC')
        s,ds,e=fixture([core,mobile],[F.demand(q=900,mark='100',floor='90')],cash='300000',scores={'NEW':90,'OLDSEC':10,'LEGACY':5})
        r=solve_C20(s,ds,e);self.assertEqual(r['Q']['NEW'],0);self.assertFalse(r['D']);self.assertTrue(r['validation']['ok'])
    def test_shadow_search_does_not_spend_input_and_checkpoint_recomputes(self):
        s,ds,e=fixture([F.lot(q=9000,mark='100',floor='95')],[F.demand(q=900,mark='100',floor='95')],cash='100000')
        b=new_book(s);old=b.dumps();r=solve_C20(s,ds,e,book=b);self.assertEqual(b.dumps(),old)
        self.assertGreater(D(json.loads(r['budget_after'])['body']['batch']['new']),0)
        p=O/'test-restart';save(p/'INPUT.json',dict(snapshot=s,B_demands=ds,industry_evidence=e));save(p/'RESULT.json',r)
        subprocess.run([sys.executable,'-B',str(O/'c_batch20.py'),str(p/'INPUT.json'),sha(p/'INPUT.json'),str(p/'RESULT.json'),str(p/'RESTORED.json')],check=True)
        self.assertTrue(read(p/'RESTORED.json')['exact']);self.assertFalse(r['submit_allowed'])
    def test_budget_pruning_equals_full_discrete_oracle(self):
        ds=[F.demand(x,q=900,mark='10',floor='9.5',sector='S') for x in 'ABC']
        s,ds,e=fixture([F.lot(q=9000,mark='10',floor='9.5')],ds,cash='10000',scores={'OLDSEC':10,'S':90})
        a=solve_C20(s,ds,e);b=solve_C20(s,ds,e,oracle=True)
        self.assertEqual((a['Q'],a['D']),(b['Q'],b['D']))

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    save(O/'SYNTHETIC_RESULTS.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),
        scope='budget mirror/state component + original native-fee/quantity joint arithmetic; not installed account callbacks',financial_events=0))
    raise SystemExit(not r.wasSuccessful())
