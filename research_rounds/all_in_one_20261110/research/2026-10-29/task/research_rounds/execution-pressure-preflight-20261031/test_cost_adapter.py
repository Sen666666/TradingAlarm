"""Actual native ledger cost2 and empty actual pressure-runner identity gates."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import pressure_runner as R
from initialization_guard import IO
import test_bridge as T
J=R.J;D=J.D
class Tests(unittest.TestCase):
 def test_cost2_real_buy_and_sell_fee_slip_and_cash_bridge(self):
  a=T.account();a.cost_multiplier=2;J.C.activate(a);i=T.intent();x,r,why=T.routed(a,i);self.assertIsNone(why);self.assertEqual(x['price'],D('10.0100'))
  T.reserve(a,i,x,r);f=a.fill_buy('A',T.win(i,x,raw=10));self.assertIsNotNone(f)
  expected=sum(T.T.MINIMUM.incremental('buy',f.gross_cny,{}, {},2,shares=f.shares,par_value=D(1)).values(),D(0));self.assertEqual(f.fees_cny,expected)
  decision=i['clock'].earliest_execution_at+T.timedelta(days=1);clock=T.T.admission.Clock(decision,decision+T.timedelta(days=1),decision.date());a.sell('A',clock,T.T.quote(price=10),[z['id'] for z in a.live('A')],'fixture_exit')
  price=D('9.9900');s=a.fill_exit('A',T.T.window(sid='A',at=clock.earliest_execution_at,price=price,raw_open=D(10),fees=T.T.MINIMUM,eid='cost2-sell'));self.assertIsNotNone(s)
  self.assertEqual(s.fees_cny,sum(T.T.MINIMUM.incremental('sell',s.gross_cny,{}, {},2,shares=s.shares,par_value=D(1)).values(),D(0)))
  a.settle_due(s.at);self.assertEqual(D(T.journal_bridge(a,s.at)['independent_NAV_difference']),0)
 def test_opening_source_only_cost_window_arguments_changed(self):
  import inspect,textwrap
  original=textwrap.dedent(inspect.getsource(J.Runner.opening))
  self.assertEqual(R.OPENING.replace("self.market.window(sid,at,'sell',a.cost_multiplier)","self.market.window(sid,at,'sell',1)").replace("self.market.window(sid,at,'buy',a.cost_multiplier)","self.market.window(sid,at,'buy',1)"),original)
 def test_reference_routes_original_exact(self):
  self.assertIs(R.B3CostRunner.route,J.Runner.route);self.assertIs(R.DiagCostRunner.route,R.BASE.Runner.route)
  self.assertIs(R.B3CostRunner.planning,J.Runner.planning);self.assertIs(R.DiagCostRunner.planning,J.Runner.planning)
 def test_actual_pressure_classes_checkpoint_identity_and_wrong_reference_rejected(self):
  for cls,other in [(R.B3CostRunner,R.DiagCostRunner),(R.DiagCostRunner,R.B3CostRunner)]:
   root=Path(tempfile.mkdtemp(prefix='pressure-engine-identity-',dir='/tmp'));a=R.empty(cls);at=J.M.N.iso('2025-07-07T15:10:00+08:00')
   with IO.atomic_runner_outputs(a,R.L,root,canonicalize=J.W.canon):a.checkpoint(root,at)
   b=R.empty(cls)
   with IO.atomic_runner_outputs(b,R.L,root,canonicalize=J.W.canon):self.assertEqual(b.restore(root/'checkpoint.pkl'),at)
   wrong=R.empty(other)
   with self.assertRaisesRegex(ValueError,'identity mismatch'):
    with IO.atomic_runner_outputs(wrong,R.L,root,canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 IO.write_json(R.O/'COST_ADAPTER_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),no_history=True,delay_gate_not_claimed=True))
 raise SystemExit(not result.wasSuccessful())
