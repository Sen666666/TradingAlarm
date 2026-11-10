"""Synthetic + source-AST QA only. Does not run a historical economic loop."""
import ast,copy,hashlib,json,random,unittest
from unittest.mock import patch
import numpy as np,pandas as pd
from runtime import O,SOURCE,sha,read,make_loop,select_source
from priority import reorder_slots,selector,DmiConsumer
from joint_engine import JointConsumer
from joint_policy import rank_key
from test_joint_engine import FakeEngine,FakeMarket,price_row,ab_row,CAL
from features import load_math
from dmi_gates import require_release

class PriorityTests(unittest.TestCase):
    def test_release_missing_blocks_before_economics(self):
        self.assertFalse((O/'ROOT_DMI_AUTHORIZATION.json').exists())
        for w in ('2022','2024'):
            with self.assertRaises(PermissionError):require_release(w)
            self.assertFalse((O/('DMI_RUN_ONCE_'+w+'.json')).exists())
    def test_all_slot_invariants_random_synthetic(self):
        rng=random.Random(73114)
        for _ in range(1000):
            rows=[];d={}
            for i in range(rng.randint(0,25)):
                lane=rng.choice(['AB','PRICE','PRICE']);known=lane=='AB' or rng.choice([True,False])
                sid='SYN_'+str(i).zfill(2)
                row=dict(sid=sid,day=CAL[0],sector='SYN',owner_lane=lane,PVR_known=known,PVR_score=rng.choice([10.,50.,70.,90.]) if known else np.nan)
                d[sid]=rng.choice([-1.,-.2,0.,.5,1.,np.nan]);rows.append((row,{}))
            rows.sort(key=lambda rc:rank_key(rc[0]))
            out,audit=reorder_slots(rows,lambda sid,day:d[sid])
            self.assertEqual(sorted(r['sid'] for r,c in rows),sorted(r['sid'] for r,c in out))
            for x in audit:
                if not x['mutable']:self.assertEqual(x['original_numeric_rank'],x['dmi_numeric_rank'])
            self.assertEqual(sum(r['owner_lane']=='AB' for r,c in rows[:2]),sum(r['owner_lane']=='AB' for r,c in out[:2]))
            mutable=[r for r in audit if r['mutable']]
            self.assertEqual([r['sid'] for r in mutable],[r['sid'] for r in sorted(mutable,key=lambda x:(-d[x['sid']],-x['PVR_score'],x['sid']))])
    def test_negative_d_has_no_entry_gate(self):
        rows=[(dict(sid=s,day=CAL[0],sector='SYN',owner_lane='PRICE',PVR_known=True,PVR_score=p),{}) for s,p in [('SYN_A',90),('SYN_B',50),('SYN_C',20)]]
        d={'SYN_A':-.9,'SYN_B':-.3,'SYN_C':-.1}
        out,a=reorder_slots(rows,lambda sid,day:d[sid])
        self.assertEqual([r['sid'] for r,c in out[:2]],['SYN_C','SYN_B'])
    def test_unknown_original_numeric_hole_preserved(self):
        rows=[(dict(sid=s,day=CAL[0],sector='SYN',owner_lane=l,PVR_known=k,PVR_score=p),{}) for s,l,k,p in [('SYN_A','PRICE',True,90),('SYN_B','AB',True,80),('SYN_C','PRICE',True,70),('SYN_D','PRICE',False,np.nan)]]
        d={'SYN_A':np.nan,'SYN_C':1.,'SYN_D':2.}
        out,a=reorder_slots(rows,lambda sid,day:d[sid]);self.assertEqual([r['sid'] for r,c in out],[r['sid'] for r,c in rows])
    def test_same_stock_and_state_feasibility_precede_rerank(self):
        e=FakeEngine();m=FakeMarket(e)
        # Explicit synthetic fixture only: production constructor remains gated.
        c=DmiConsumer.__new__(DmiConsumer);JointConsumer.__init__(c,e,m,'2022')
        c.dmi_rank_audit=[];c._dmi={('SYN_A',CAL[0]):-.8,('SYN_B',CAL[0]):1.,('SYN_C',CAL[0]):.5,('SYN_D',CAL[0]):.9}
        c.states['SYN_D']=dict(state='UNKNOWN',round_id='SYN_OLD')
        c.select_close(CAL[0],[ab_row('SYN_A',score=80)],[price_row('SYN_A',score=90),price_row('SYN_B',score=70),price_row('SYN_C',score=60),price_row('SYN_D',score=99)])
        self.assertEqual(c.states['SYN_A']['owner_lane'],'AB')
        self.assertEqual(c.states['SYN_D']['state'],'UNKNOWN')
        self.assertEqual(len(c.dmi_rank_audit),3)
        self.assertEqual(next(x for x in c.dmi_rank_audit if x['sid']=='SYN_A')['dmi_numeric_rank'],1)
        self.assertNotIn('SYN_D',[x['sid'] for x in c.dmi_rank_audit])
    def test_missing_dynamic_feature_is_error_not_unknown_zero(self):
        rows=[(dict(sid='SYN',day=CAL[0],sector='X',owner_lane='PRICE',PVR_known=True,PVR_score=50),{})]
        with self.assertRaises(KeyError):reorder_slots(rows,lambda sid,day:{}[sid])
    def test_math_scalar_and_resets(self):
        calc,rma=load_math();rng=np.random.default_rng(14);v=rng.random(100)
        z=rma(v);ref=np.full(len(v),np.nan);ref[13]=np.mean(v[:14])
        for i in range(14,len(v)):ref[i]=(13*ref[i-1]+v[i])/14
        self.assertLess(np.nanmax(np.abs(z-ref)),1e-14)
        ix=pd.bdate_range('2020-01-01',periods=70);c=np.arange(70)+10.
        p=pd.DataFrame(dict(open=c,high=c+1,low=c-1,close=c,segment_id=0,price_eligible=True,observed_bar=True,is_observed_bar=True,source_invalid=False,synthetic_event_bar=False),index=ix)
        q=calc(p,ix);self.assertTrue(q.d.iloc[:14].isna().all());self.assertTrue((q.d.iloc[14:]==1).all())
        pp=p.copy();pp.loc[ix[30],'source_invalid']=True;q=calc(pp,ix)
        self.assertTrue(q.d.loc[ix[30]:ix[44]].isna().all());self.assertEqual(q.d.iloc[45],1)
        pp=p.copy();pp.loc[ix[30]:,'segment_id']=1;q=calc(pp,ix)
        self.assertTrue(q.d.loc[ix[30]:ix[43]].isna().all());self.assertEqual(q.d.iloc[44],1)
        pp=p.drop(ix[30]);q=calc(pp,ix);self.assertTrue(q.d.loc[ix[30]:ix[44]].isna().all())
        pp=p.copy();pp[['open','high','low','close']]=10.;q=calc(pp,ix);self.assertTrue((q.d.iloc[14:]==0).all())


def ast_evidence():
    original,cls=select_source();methods={n.name:copy.deepcopy(n) for n in cls.body if isinstance(n,ast.FunctionDef)}
    captured={};real_compile=compile
    def spy(source,filename,*args,**kwargs):
        if isinstance(source,ast.AST) and any(x in filename for x in (':isolated_gate_owner',':price_slot_sort_only')):captured[filename]=copy.deepcopy(source)
        return real_compile(source,filename,*args,**kwargs)
    with patch('builtins.compile',side_effect=spy):make_loop();selector()
    loop=next(v.body[0] for k,v in captured.items() if k.endswith(':isolated_gate_owner'))
    expected=copy.deepcopy(methods['run_authorized']);expected.body=expected.body[3:];expected.name='isolated_loop'
    assert ast.dump(loop)==ast.dump(expected)
    sel=next(v.body[0] for k,v in captured.items() if k.endswith(':price_slot_sort_only'))
    before=copy.deepcopy(sel);changed=0
    for n in ast.walk(before):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='rank_options':
            # Locate its parent assignment for reversal.
            for a in ast.walk(before):
                if isinstance(a,ast.Assign) and a.value is n:a.value=n.args[0];changed+=1
    assert changed==1 and ast.dump(before)==ast.dump(methods['select_close'])
    evidence=dict(result='PASS_AST_SINGLE_INTERVENTION',loop_removed_statements=[ast.unparse(x) for x in methods['run_authorized'].body[:3]],loop_rest_exact=True,selector_single_change='ordered = self.rank_options(original sorted(options,key=rank_key))',selector_every_other_ast_node_exact=True,baseline_class='Unmodified JointConsumer; never uses transformed selector',production_original_sha256=sha(SOURCE/'joint_engine.py'),loop_ast_sha256=hashlib.sha256(ast.dump(loop).encode()).hexdigest(),selector_ast_sha256=hashlib.sha256(ast.dump(sel).encode()).hexdigest())
    return evidence,ast.unparse(loop),ast.unparse(sel)

def main():
    from run_economic import save
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PriorityTests))
    if not result.wasSuccessful():raise AssertionError('SYNTHETIC_QA_FAILED')
    evidence,loop,sel=ast_evidence()
    save(O/'AST_DERIVATION_QA.json',evidence)
    (O/'DERIVED_LOOP.txt').write_text(loop+'\n');(O/'DERIVED_SELECTOR.txt').write_text(sel+'\n')
    save(O/'PRELIMINARY_QA.json',dict(result='PASS_SYNTHETIC_AND_AST_QA',tests=result.testsRun,random_queues=1000,feature_qa=read(O/'features/QA.json'),economic_runs=0,new_arm_locked=True))
if __name__=='__main__':main()
