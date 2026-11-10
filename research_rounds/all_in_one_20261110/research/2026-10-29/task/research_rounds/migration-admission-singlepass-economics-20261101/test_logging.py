"""Observational wrapper identity through genuine native reservations/fills."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy,json,unittest,time
import runner as R
N=R.N;J=R.J;O=R.O
T=J.W.load('SD_logging_native_fixtures',N.O/'test_native.py')

class Tests(unittest.TestCase):
    def test_diagnostics_do_not_change_native_route_state_or_order(self):
        for pending in (False,True):
            a=T.account();b=T.account()
            if pending:T.pending(a);T.pending(b)
            else:T.F.progress(a,'S',T.BASE,'confirm');T.F.progress(b,'S',T.BASE,'confirm')
            i=T.F.intent(rid='same-receipt',sid='B');k=copy.deepcopy(i)
            x,why=J.LR.preview(i,T.D(10),T.D(1),T.T.RULE,T.T.MINIMUM);self.assertIsNone(why)
            at=i['clock'].earliest_execution_at
            for z in (a,b):z.sync(at);z.current_nav=z.balance(at,z.market.marks(at,z.positions))['nav']
            r=NS(sector_by_sid={'B':'S'},sd_route_log=[])
            expected=N.decoupled_route(r,a,i,x,at);actual=R.Runner.route(r,b,k,x,at)
            self.assertEqual(expected,actual);self.assertEqual(i,k);self.assertEqual(T.snapshot(a),T.snapshot(b))
            for z,it in ((a,i),(b,k)):T.F.reserve(z,it,x,expected[0]);z.fill_buy('B',T.win(it,x))
            self.assertEqual(T.snapshot(a),T.snapshot(b));self.assertEqual(len(r.sd_route_log),1)
    def test_wiring_unchanged(self):
        self.assertIs(R.Runner.opening,J.Runner.opening);self.assertIs(R.Runner.planning,J.Runner.planning)
        self.assertEqual(N.L.sha(N.__file__) if hasattr(N,'L') else N.BASE.L.sha(N.__file__),R.EXPECTED)

if __name__=='__main__':
    t=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    R.IO.write_json(O/'LOGGING_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),seconds=time.monotonic()-t,only_added_observational_wrappers=True))
    raise SystemExit(not result.wasSuccessful())
