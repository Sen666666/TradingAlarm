"""Fictitious correctness only. Never runs an historical economic loop."""
import ast,copy,unittest
import numpy as np,pandas as pd
from runtime import O,SOURCE,sha,save,make_loop,select_source
from generation import compute
from entry_gate import GateMixin,GateUnknown,selector_tree,GATE_BLOCK
from joint_engine import JointConsumer
from test_joint_engine import FakeEngine,FakeMarket,price_row,ab_row,CAL,JointTests
from test_execution_book import book,permission,terminal,fill,ROOT as EXECROOT
from run_economic import clean

class FixtureConsumer(GateMixin,JointConsumer):
    def __init__(self,e,m,w):super().__init__(e,m,w);self.entry_gate_audit=[];self._entry_features={}
    def add(self,row,status='ALLOW'):
        self._entry_features[row['sid'],pd.Timestamp(row['day'])]=dict(root_id=row['root_id'],gate_status=status,entry_active=status=='ALLOW',generation=1,generation_birth=CAL[0],entry_U=18.,receipt_identity=repr(row['receipt_id']),signal_factor=row['adjustment_factor'],signal_raw_close=row['raw_close'],signal_identity=row['root_id'][1])
        return row
class AllAllowConsumer(GateMixin,JointConsumer):
    def _entry_permission(self,row):return True

def make():
    e=FakeEngine();m=FakeMarket(e);return e,m,FixtureConsumer(e,m,'2022')

def fixture():
    d=pd.date_range('2020-01-01',periods=30,freq='B')
    q=pd.DataFrame(dict(open=9.,high=10.,low=8.,close=9.,price_eligible=True,observed_bar=True,is_observed_bar=True,source_invalid=False,synthetic_event_bar=False,source_kind='F',source_path='P',segment_id=1.),index=d)
    q.loc[d[20],['open','close','high']]=[10.,11.,11.5]
    q.loc[d[21],['open','close','high']]=[11.,12.,12.5]
    q.loc[d[22],['open','close','high']]=[10.,10.,11.]
    q.loc[d[23],['open','close','high']]=[12.,13.,13.5]
    q.loc[d[24]:,['open','close','high']]=[12.,13.,13.5]
    x=pd.DataFrame(dict(born=False,failed=False,root_unknown=False,active=False,root_day=pd.NaT,U=np.nan),index=d)
    x.loc[d[20]:,'active']=True;x.loc[d[20]:,'root_day']=d[20];x.loc[d[20]:,'U']=10.;x.loc[d[20],'born']=True
    return q,x

class GenerationTests(unittest.TestCase):
    def test_birth_high_no_reset_retire_rebirth(self):
        q,x=fixture();g=compute(q,x)
        self.assertEqual(g.iloc[20].event,'ORIGINAL_BIRTH')
        self.assertEqual((g.iloc[21].generation,g.iloc[21].entry_U),(1,10.))
        self.assertEqual(g.iloc[22].gate_status,'DENY_ENTRY_GENERATION_INACTIVE')
        self.assertEqual(g.iloc[22].event,'ENTRY_GENERATION_RETIRED')
        self.assertEqual((g.iloc[23].generation,g.iloc[23].entry_U),(2,12.5))
    def test_parent_fail_precedes_high_regeneration(self):
        q,x=fixture();q=q.iloc[:24];x=x.iloc[:24].copy();x.iloc[-1,x.columns.get_loc('failed')]=True;x.iloc[-1,x.columns.get_loc('active')]=False
        g=compute(q,x);self.assertEqual(g.iloc[-1].event,'PARENT_FAILED');self.assertFalse(g.iloc[-1].entry_active);self.assertEqual(g.iloc[-1].generation,1)
    def test_parent_unknown_precedes_high_regeneration(self):
        q,x=fixture();q=q.iloc[:24];x=x.iloc[:24].copy();x.iloc[-1,x.columns.get_loc('root_unknown')]=True;x.iloc[-1,x.columns.get_loc('active')]=False
        g=compute(q,x);self.assertEqual(g.iloc[-1].gate_status,'UNKNOWN_PARENT_ROOT');self.assertFalse(g.iloc[-1].entry_active)
    def test_source_invalid_permanently_retires_only_entry_metadata(self):
        for col,val in [('source_invalid',True),('source_path','DIFFERENT')]:
            q,x=fixture();q.loc[q.index[22],col]=val;g=compute(q,x)
            self.assertTrue(g.iloc[22].gate_status.startswith('UNKNOWN'));self.assertFalse(g.iloc[23].entry_active);self.assertTrue(x.iloc[23].active)
    def test_no_parent_never_grants(self):
        q,x=fixture();g=compute(q.iloc[:20],x.iloc[:20]);self.assertTrue(g.gate_status.eq('DENY_NO_PARENT_ROOT').all());self.assertFalse(g.entry_active.any())
    def test_physical_prefix_and_future_mutation(self):
        q,x=fixture();g=compute(q,x);pg=compute(q.iloc[:24].copy(),x.iloc[:24].copy());pd.testing.assert_frame_equal(g.loc[pg.index],pg,check_exact=True)
        q.loc[q.index[24]:,'close']=1000.;pd.testing.assert_frame_equal(compute(q,x).loc[pg.index],pg,check_exact=True)

class ConsumerTests(unittest.TestCase):
    def test_single_ast_intervention_and_global_bindings(self):
        import joint_engine as j
        m,original=selector_tree();inserted=0
        for n in ast.walk(m):
            for field,val in ast.iter_fields(n):
                if isinstance(val,list):
                    remove=[i for i,v in enumerate(val) if isinstance(v,ast.If) and ast.unparse(v.test)=='not self._entry_permission(pr)']
                    for i in reversed(remove):val.pop(i);inserted+=1
        self.assertEqual(inserted,1);self.assertEqual(ast.dump(m,include_attributes=False),original)
        loop=make_loop()
        for func in [GateMixin.select_close,loop]:
            for k,v in vars(j).items():
                if k not in ['select_close','isolated_loop']:self.assertIs(func.__globals__[k],v)
        for n,v in JointConsumer.__dict__.items():
            if callable(v) and n!='select_close':self.assertIs(getattr(AllAllowConsumer,n),v)
    def test_all_allow_pass_through_every_original_output(self):
        outputs=[]
        for cls in [JointConsumer,AllAllowConsumer]:
            e=FakeEngine();m=FakeMarket(e);c=cls(e,m,'2022')
            e.cash_events=[dict(id='RIGHT',sid='P',record=CAL[1],ex=CAL[3],pay=CAL[4],cash=__import__('decimal').Decimal('.1'))]
            c.process_day(CAL[0],None,[ab_row('A',score=60)],[price_row('P',score=90),price_row('U',score=float('nan'),known=False)])
            for i,d in enumerate(CAL[1:],1):c.process_day(d,CAL[i-1],[],[])
            values={n:getattr(e,n) for n in ['rounds','actions','decisions','ranking_audit','archives','blocks','claims','trace']}
            values.update({n:getattr(c,n) for n in ['states','seq','books','price_audit','offer_audit','frozen_responsibilities','ab_decision_audit']})
            outputs.append(clean(values))
        self.assertEqual(outputs[0],outputs[1])
    def test_deny_before_queue_promotes_original_pvr_next(self):
        e,m,c=make();rows=[c.add(price_row('P1',score=90),'DENY_ENTRY_GENERATION_INACTIVE'),c.add(price_row('P2',score=80)),c.add(price_row('P3',score=70))]
        c.select_close(CAL[0],[],rows);self.assertEqual([r['sid'] for r in e.decisions],['P2','P3']);self.assertTrue(all(r['selected'] for r in e.decisions));self.assertNotIn('P1',c.states)
    def test_ab_precedes_gate_even_missing_gate(self):
        e,m,c=make();c.select_close(CAL[0],[ab_row()],[price_row()]);self.assertEqual(c.states['SYN_A']['owner_lane'],'AB');self.assertFalse(c.entry_gate_audit)
    def test_missing_root_factor_receipt_unknown_never_allow(self):
        for change in ['missing','root','factor','receipt','unknown']:
            e,m,c=make();p=price_row()
            if change!='missing':c.add(p)
            f=c._entry_features.get(('SYN_A',CAL[0]))
            if change=='root':f['root_id']=('OTHER','bad','2022-01-03')
            if change=='factor':f['signal_factor']=2.
            if change=='receipt':f['receipt_identity']='WRONG'
            if change=='unknown':f['gate_status']='UNKNOWN_SOURCE'
            with self.assertRaises(GateUnknown):c.select_close(CAL[0],[],[p])
            self.assertFalse(c.states);self.assertFalse(e.actions)
    def test_pending_nextopen_does_not_reread_gate_or_current_close(self):
        e,m,c=make();p=c.add(price_row());c.select_close(CAL[0],[],[p]);c._entry_features.clear()
        def bomb(*a,**k):raise AssertionError('NO_CLOSE_AT_OPEN')
        m.close=bomb;c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1]);self.assertEqual(c.states['SYN_A']['state'],'HELD');self.assertEqual(len(c.entry_gate_audit),1)
    def test_q0_no_parent_later_fresh_receipt_reads_gate(self):
        e,m,c=make();p=c.add(price_row());c.select_close(CAL[0],[],[p])
        c.sizing.initial_open=lambda *a,**k:dict(result='MINIMUM_LOT_OR_RISK_REJECT_AT_OPEN')
        c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1]);self.assertFalse(c.books);self.assertFalse(c.states)
        p=c.add(price_row(day=CAL[1]),'DENY_ENTRY_GENERATION_INACTIVE');c.select_close(CAL[1],[],[p]);self.assertEqual(len(c.entry_gate_audit),2);self.assertFalse(c.states)
    def test_existing_zero_partial_parent_does_not_call_gate(self):
        for qty in [0,40]:
            e,m,c=make();b=book();o=b.open_target('PROBE',permission(q=100))
            if qty:fill(b,o,qty)
            terminal(b,o,qty);sid=EXECROOT[0];c.books['existing']=b;c.states[sid]=dict(state='BUY_PENDING',round_id='existing',owner_lane='PRICE')
            p=price_row(sid);c.select_close(CAL[0],[],[p]);self.assertFalse(c.entry_gate_audit)
            n=b.submit_remaining('PROBE',permission(day=2,q=200));self.assertEqual(n.quantity,100-qty);self.assertEqual(b.parent('PROBE').target_Q,100)
    def test_flat_but_unresolved_parent_stops_not_new_probe(self):
        e,m,c=make();b=book();o=b.open_target('PROBE',permission());terminal(b,o,0);c.books['orphan']=b;p=c.add(price_row(EXECROOT[0]))
        with self.assertRaisesRegex(GateUnknown,'UNRESOLVED_PARENT'):c.select_close(CAL[0],[],[p])
        self.assertFalse(c.states);self.assertEqual(len(b.parents),1)
    def test_unknown_locked_and_birth_window_closed(self):
        e,m,c=make();p=price_row();c.states['SYN_A']=dict(state='UNKNOWN',round_id='locked');c.select_close(CAL[0],[],[p]);self.assertFalse(c.entry_gate_audit)
        c.states.clear();c.birth_end=CAL[0];c.process_day(CAL[1],CAL[0],[],[p]);self.assertFalse(c.states);self.assertFalse(c.entry_gate_audit)

class AllAllowInheritedJointTests(JointTests):
    def make(self):
        e=FakeEngine();m=FakeMarket(e);return e,m,AllAllowConsumer(e,m,'2022')

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    import test_execution_book
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_execution_book))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    save(O/('TEST_QA.json' if result.wasSuccessful() else 'TEST_FAILED_QA.json'),dict(passed=result.wasSuccessful(),tests_run=result.testsRun,errors=len(result.errors),failures=len(result.failures),economic_runs=0,code_sha256=sha(__file__),scope='GENERATION_AND_CONSUMER_AND_ORIGINAL_SYNTHETIC_EXECUTION_PLUS_ALL_ALLOW_JOINT'))
    raise SystemExit(not result.wasSuccessful())
