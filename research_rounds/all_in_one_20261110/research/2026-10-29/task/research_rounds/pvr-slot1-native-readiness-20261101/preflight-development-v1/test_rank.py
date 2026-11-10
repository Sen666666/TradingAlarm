"""Affected rank/NA/role/clock/identity gates; real native opening for zero-fill."""
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
from datetime import timedelta
import copy, json, tempfile, unittest, time
import pandas as pd
import native_rank as N

J, O = N.J, N.O
F = J.W.load('slot1_authoritative_native_fixture', J.O/'test_bridge.py')
DETAIL = []

def intents(symbols):
    return [dict(sid=s, role='mobile', rank=n*3+2, cap=100,
                 floor=9.9, budget=1000, CP1_id='canonical-'+s) for n,s in enumerate(symbols)]

def ordered(rows, values):
    keys, log = N.priority_plan(rows, lambda s, _: values.get(s), '2022-01-05')
    return sorted(keys, key=keys.get), keys, log

def account():
    a = F.account(); N.BASE.enable(a); return a

class RankTests(unittest.TestCase):
    def test_all_ready_order(self):
        self.assertEqual(ordered(intents('ABC'), dict(A=1,B=3,C=2))[0], list('BCA'))

    def test_all_NA_identity(self):
        rows = intents('ABC')
        out, keys, log = ordered(rows, {})
        self.assertEqual(out, list('ABC')); self.assertEqual(keys, {r['sid']:r['rank'] for r in rows})
        self.assertTrue(all(not x['PVR_ready'] for x in log))

    def test_mixed_NA_slots_and_rank_gaps(self):
        out, keys, _ = ordered(intents('ABCDE'), dict(A=1,C=3,E=2))
        self.assertEqual(out, list('CBEDA')); self.assertEqual(keys['B'],5); self.assertEqual(keys['D'],11)

    def test_nonfinite_not_neutral(self):
        out, _, log = ordered(intents('ABC'), dict(A=float('nan'),B=50,C=float('inf')))
        self.assertEqual(out,list('ABC')); self.assertEqual([x['PVR_ready'] for x in log],[False,True,False])

    def test_tie_retains_original_full_H1_code_key(self):
        # Original H1 ordering may put code Z before A. PVR tie must not undo it.
        rows = intents(['Z','A','B'])
        self.assertEqual(ordered(rows, dict(Z=50,A=50+1e-14,B=50))[0],['Z','A','B'])

    def test_empty_singleton(self):
        self.assertEqual(ordered([], {})[0],[])
        self.assertEqual(ordered(intents('A'), dict(A=20))[0],['A'])

    def test_duplicate_core_mobile_one_stock_slot(self):
        rows = intents('ABC'); core = dict(rows[0],role='core',CP1_id=None)
        _, keys, log = ordered([rows[0],rows[1],core,rows[2]],dict(A=1,B=3,C=2))
        self.assertEqual(len(keys),3); self.assertEqual(log[0]['roles'],['core','mobile'])
        actual = sorted([dict(r,rank=keys[r['sid']]) for r in rows+[core]],key=lambda r:(r['rank'],r['role']!='core'))
        self.assertEqual([(x['sid'],x['role']) for x in actual],[('B','mobile'),('C','mobile'),('A','core'),('A','mobile')])

    def test_original_targets_receipts_and_H1_score_unchanged(self):
        rows = intents('ABC'); [r.update(score=90-n,kind='add') for n,r in enumerate(rows)]
        a = NS(pending=copy.deepcopy(rows),decisions=[dict(at='2022-01-05 15:10:00+08:00',intents=copy.deepcopy(rows))])
        before = copy.deepcopy(a)
        N.apply_priority(a,lambda s,_:dict(A=1,B=3,C=2)[s],'2022-01-05')
        for old,new in zip(before.pending,a.pending):
            self.assertEqual({k:v for k,v in old.items() if k!='rank'},{k:v for k,v in new.items() if k!='rank'})
        self.assertEqual(a.pending,a.decisions[-1]['intents'])

    def test_reject_duplicate_role_or_ambiguous_original_key(self):
        with self.assertRaises(AssertionError): ordered(intents('A')*2, {})
        rows=intents('AB');rows[1]['rank']=rows[0]['rank']
        with self.assertRaises(AssertionError): ordered(rows,{})

    def test_score_date_is_decision_only_and_future_perturbation_cannot_reorder(self):
        calls=[];panel={('A','2022-01-05'):5,('B','2022-01-05'):10,('A','2022-01-06'):1000}
        def score(s,d):calls.append((s,d));return panel.get((s,d))
        a=NS(pending=intents('AB'),decisions=[dict(at='2022-01-05 15:10:00+08:00',intents=intents('AB'))])
        N.apply_priority(a,score,'2022-01-05');one=copy.deepcopy(a.pending)
        panel['A','2022-01-06']=-1e9
        b=NS(pending=intents('AB'),decisions=[dict(at='2022-01-05 15:10:00+08:00',intents=intents('AB'))])
        N.apply_priority(b,score,'2022-01-05')
        self.assertEqual(one,b.pending);self.assertTrue(all(d=='2022-01-05' for s,d in calls))

    def test_actual_native_target_under_minimum_still_rejected(self):
        i=F.intent();i.update(cap=0,budget=J.D(999))
        x,why=J.LR.preview(i,J.D(10),J.D(1),F.T.RULE,F.T.MINIMUM)
        self.assertIsNone(x);self.assertEqual(why,'open_minimum_exceeds_frozen_contract')
        rows=[dict(i,rank=2)];_,keys,_=ordered(rows,{'A':100})
        self.assertEqual(keys['A'],2);self.assertEqual(rows[0]['cap'],0)

    def test_actual_opening_core_reservation_zero_fill_suppresses_mobile(self):
        a=account();core=F.intent(rid='not-a-core-receipt')
        core.update(kind='core',role='core',CP1_id=None,CP1_trace=None,cap=100,
                    budget=J.D(1001),risk_budget=J.D(2500),rank=5)
        mobile=F.intent(rid='fresh-unconsumed');mobile['rank']=5
        a.pending=[mobile,core];at=core['clock'].earliest_execution_at
        m=NS(raw={'A':pd.DataFrame({'open':[10.]},index=[pd.Timestamp(at.date())])},
             quantity=lambda *_:F.T.RULE,fees=lambda *_:F.T.MINIMUM,window=lambda *_:None)
        r=NS(market=m,facts=a.facts,sector_by_sid={'A':'S'},funding=[])
        r.route=MethodType(N.BASE.Runner.route,r)
        J.Runner.opening(r,a,at)
        admitted=[x for x in r.funding if x['result']=='reserved']
        self.assertEqual(len(admitted),1);self.assertEqual(admitted[0]['role'],'core')
        self.assertEqual(a.quantity('A'),0);self.assertIn('A',a.buys)
        self.assertNotIn('fresh-unconsumed',a.budget.consumed)
        self.assertFalse(any(x['role']=='mobile' for x in r.funding))
        DETAIL.append(dict(case='actual_native_zero_fill',funding=J.W.canon(r.funding),
                           core_reserved=True,actual_fills=0,mobile_not_consumed_or_attempted=True))

    def test_native_opening_route_callbacks_unchanged(self):
        self.assertIs(N.Runner.opening,J.Runner.opening)
        self.assertIs(N.Runner.route,N.BASE.Runner.route)
        self.assertIs(N.Runner.request if hasattr(N.Runner,'request') else None,None)

    def test_actual_partial_state_checkpoint_restart_and_guards(self):
        old=N.SCORES;N.SCORES=NS(manifest_sha256='fixture-score-source',at=lambda *_:None)
        def pair(mode='PVR_SLOT1'):
            p=N.Runner.__new__(N.Runner);p.accounts={'B':account()};p.rank_mode=mode
            p.integration_policy=N.POLICY+':'+mode;p.rank_scores_manifest_sha256=N.SCORES.manifest_sha256
            p.source_freeze={str(Path(N.__file__).resolve()):N.sha(N.__file__)};p.rank_log=[]
            return p
        try:
            p=pair();p.assert_native_wiring()
            with tempfile.TemporaryDirectory(prefix='PVR_SLOT1-checkpoint-',dir='/tmp') as temp:
                root=Path(temp);at=F.BASE
                with N.IO.atomic_runner_outputs(p,N.L,root,canonicalize=J.W.canon):p.checkpoint(root,at)
                restored=pair()
                with N.IO.atomic_runner_outputs(restored,N.L,root/'restart',canonicalize=J.W.canon):
                    self.assertEqual(restored.restore(root/'checkpoint.pkl'),at)
                self.assertEqual(J.W.canon(vars(p.accounts['B'].budget)),J.W.canon(vars(restored.accounts['B'].budget)))
                with self.assertRaises((AssertionError,ValueError)):
                    wrong=pair('H1')
                    with N.IO.atomic_runner_outputs(wrong,N.L,root/'wrong-mode',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
                N.SCORES=NS(manifest_sha256='different-source')
                with self.assertRaises(AssertionError):
                    wrong=pair()
                    with N.IO.atomic_runner_outputs(wrong,N.L,root/'wrong-score',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
                N.SCORES=NS(manifest_sha256='fixture-score-source')
                with self.assertRaises(ValueError):
                    wrong=pair();wrong.route=MethodType(J.Runner.route,wrong)
                    with N.IO.atomic_runner_outputs(wrong,N.L,root/'wrong-route',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
        finally:N.SCORES=old

if __name__=='__main__':
    begin=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RankTests))
    N.IO.write_json(O/'RANK_NATIVE_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-begin,
        details=DETAIL,scope='affected gates only; prior audited native16 reused, not claimed rerun',
        new_full_financial_paths=0),encoder=J.C.encoded)
    raise SystemExit(not result.wasSuccessful())
