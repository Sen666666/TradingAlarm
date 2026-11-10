import unittest,copy,json,subprocess
from selector import *
sys.path.insert(0,str(W/'g-s-joint-funding-projection-jf2-20261102'))
import test_projector as F

def fixture(lots,ds,*,cash='500000',ranks=None):
 s,ds=F.bound(F.state(lots,cash=cash),ds);s['analysis_only']=True;ranks=ranks or {}
 for n,z in enumerate(s['lots']):
  z.update(rank_key=[ranks.get(z['sid'],10),z['sid']],fifo=n,B_donor_eligible=z['role']=='mobile' and z['donor_eligible'])
 for n,d in enumerate(ds):d['priority']=[ranks.get(d['sid'],1+n),d['sid']]
 return s,ds

class Tests(unittest.TestCase):
 def test_old_strong_new_weak_not_sold(self):
  s,ds=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')],ranks={'OLD':1,'NEW':2})
  r=solve_B(s,ds);self.assertEqual(r['Q']['NEW'],0);self.assertFalse(r['D']);self.assertEqual(r['mobile_targets']['OLD'],5000)
 def test_old_weak_new_strong_can_replace_only_needed(self):
  s,ds=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')],ranks={'OLD':2,'NEW':1})
  r=solve_B(s,ds);self.assertEqual(r['Q']['NEW'],900);self.assertGreater(r['D']['OLD'],0);self.assertLess(r['D']['OLD'],5000)
  q=r['D']['OLD'];lower=dict(r['D']);lower['OLD']=q-100
  self.assertFalse(evaluate(s,ds,r['Q'],lower)['validation']['ok'])
 def test_same_industry_cap_only_replacement(self):
  old=F.lot(q=1900,floor='99.9',sector='SAME');d=F.demand(q=900,mark='100',floor='99.8',sector='SAME');d['industry_target']=D(200000);d['use']='G'
  s,ds=fixture([old],[d],cash='810000',ranks={'OLD':2,'NEW':1});r=solve_B(s,ds)
  self.assertEqual(r['Q']['NEW'],900);self.assertEqual(r['D']['OLD'],900)
  self.assertFalse(evaluate(s,ds,{'NEW':900},{})['validation']['ok']);self.assertEqual(r['donors']['orders'][0]['q'],900)
 def test_empty_D_feasible_never_sell(self):
  s,ds=fixture([F.lot()],[F.demand(q=900,mark='100',floor='99.9')]);r=solve_B(s,ds)
  self.assertEqual(r['Q']['NEW'],900);self.assertFalse(r['D'])
 def test_no_fresh_old_retains_without_growth(self):
  s,ds=fixture([F.lot()],[]);r=solve_B(s,ds);self.assertEqual(r['mobile_targets']['OLD'],5000);self.assertFalse(r['D']);self.assertFalse(r['Q'])
 def test_core_and_unavailable_mobile_not_borrowed(self):
  core=F.lot('CORE',q=5000,role='core');s,ds=fixture([core],[F.demand(q=900,mark='100',floor='70')]);r=solve_B(s,ds)
  self.assertEqual(r['Q']['NEW'],0);self.assertFalse(r['D'])
  old=F.lot();old['sellable_qty']=0;s,ds=fixture([old],[F.demand(q=900,mark='100',floor='70')]);self.assertFalse(solve_B(s,ds)['D'])
 def test_star_new200_and_old_shares_do_not_override(self):
  s,ds=fixture([F.lot('NEW',q=50,mark='10',floor='9')],[F.demand(q=199,mark='10',floor='9',quantity=F.STAR)])
  r=solve_B(s,ds);self.assertEqual(r['Q']['NEW'],0);self.assertEqual(r['mobile_targets']['NEW'],50)
 def test_multi_mobile_fee_once_core_left_intact(self):
  a=F.lot('OLD',q=200,mark='100',floor='99.9');a['id']='m1'
  b=F.lot('OLD',q=200,mark='100',floor='99.9');b['id']='m2'
  core=F.lot('OLD',q=100,mark='100',floor='99.9',role='core');core['id']='core'
  s,ds=fixture([a,b,core],[F.demand(q=100,mark='100',floor='99.8')],cash='6000');s['decision_nav']=D(100000)
  plan=make_plan(s,ds,{'NEW':100},{'OLD':300});self.assertEqual(len(plan['orders']),1);self.assertEqual(len(plan['rows']),2)
  self.assertEqual(sum((r['net'] for r in plan['rows']),Z),D(300)*100*(ONE-SLIP)-J.fee(300,D(100)*(ONE-SLIP),a['fees'],'sell'))
  self.assertEqual({r['layer'] for r in plan['rows']},{'m1','m2'})
 def test_full_layer_risk_releases_exact_original_decimal(self):
  risk=D('991.0959742198601083396141475');z=F.lot(q=3700,risk=risk);s,ds=fixture([z],[F.demand(q=100)])
  self.assertGreater(risk*D(3700)/3700,risk)  # Reproduce the actual Jan6 tail.
  plan=make_plan(s,ds,{'NEW':100},{'OLD':3700});self.assertEqual(plan['rows'][0]['risk_release'],risk)
  self.assertTrue(J.validate(s,ds,{'NEW':100},plan)['ok'])
 def test_fixed_Q_redundant_donation_is_restored_without_new_buy(self):
  s,ds=fixture([F.lot()],[F.demand(q=100,mark='100',floor='99.9')]);Q={'NEW':100}
  Dmap,restored,checks=trim_redundancy(s,ds,Q,{'OLD':100});self.assertEqual(Dmap,{});self.assertEqual(restored[0]['restored'],100);self.assertEqual(Q,{'NEW':100})
 def test_unknown_and_pending_responsibilities_not_released(self):
  z=F.lot();z['sellable_qty']=None;s,ds=fixture([z],[F.demand(q=900,mark='100',floor='70')]);before=J.digest(s)
  with self.assertRaisesRegex(ValueError,'UNKNOWN'):solve_B(s,ds)
  self.assertEqual(J.digest(s),before)
  z=F.lot(locked=True);s,ds=fixture([z],[F.demand(q=900,mark='100',floor='70')]);self.assertFalse(solve_B(s,ds)['D'])
 def test_necessary_bounds_equal_exhaustive_discrete_oracle(self):
  # Small entire (delta,donor-prefix,last-donor-quantity) domains, not return tuning.
  for floor in ('99.9','90','70'):
   old=F.lot(q=300,mark='100',floor='70');s,ds=fixture([old],[F.demand(q=200,mark='100',floor=floor)],cash='70000')
   x=solve_B(s,ds);y=solve_B(s,ds,oracle=True);self.assertEqual((x['Q'],x['D']),(y['Q'],y['D']))
 def test_NA_original_slot_and_tie_unchanged(self):
  keys,log=priority_plan([dict(sid='a',rank=10,role='mobile'),dict(sid='b',rank=20,role='mobile'),dict(sid='c',rank=30,role='mobile')],lambda s,d:{'a':5.,'b':None,'c':8.}[s],'day')
  self.assertEqual(keys,{'c':10,'b':20,'a':30});self.assertFalse(next(r for r in log if r['sid']=='b')['PVR_ready'])
  keys,_=priority_plan([dict(sid='a',rank=10,role='mobile'),dict(sid='c',rank=30,role='mobile')],lambda s,d:5.,'day');self.assertEqual(keys,{'a':10,'c':30})
 def test_crossprocess_restore_recomputes_same_targets(self):
  s,ds=fixture([F.lot()],[F.demand(q=900,mark='100',floor='70')]);r=solve_B(s,ds);out=O/'restart';out.mkdir(exist_ok=True)
  save(out/'INPUT.json',dict(snapshot=s,demands=ds));save(out/'RESULT.json',r)
  subprocess.run([sys.executable,'-B',str(O/'restore.py'),str(out/'INPUT.json'),sha(out/'INPUT.json'),str(out/'RESULT.json'),str(out/'RESTORED.json')],check=True)
  restored=json.loads((out/'RESTORED.json').read_text());self.assertTrue(restored['exact']);self.assertEqual(restored['financial_events'],0)
  save(out/'NATIVE-SHAPE.json',dict(snapshot=s,A_demands=[],B_demands=ds))
  subprocess.run([sys.executable,'-B',str(O/'restore.py'),str(out/'NATIVE-SHAPE.json'),sha(out/'NATIVE-SHAPE.json'),str(out/'RESULT.json'),str(out/'RESTORED-NATIVE-SHAPE.json')],check=True)
  self.assertEqual(json.loads((out/'RESTORED-NATIVE-SHAPE.json').read_text()),restored)

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 save(O/'SYNTHETIC_RESULTS.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),financial_events=0));raise SystemExit(not r.wasSuccessful())
