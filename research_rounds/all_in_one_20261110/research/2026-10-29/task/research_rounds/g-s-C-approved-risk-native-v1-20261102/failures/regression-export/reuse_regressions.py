"""Reuses unchanged frozen synthetic methods; no historical input/event."""
from native_risk import *
import unittest, functools, time, argparse
from datetime import timezone
sys.path.insert(0,str(BASE))
import test_native as H
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--enabled',choices=['on','off'],required=True);args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
enabled=args.enabled=='on'
factory=functools.partial(Runner,keep_approved_risk=enabled);factory.restore=Runner.restore
H.Runner=factory;H.ROOT=args.out/'baseline';H.ROOT.mkdir(parents=True,exist_ok=True);H.HERE=HERE
import test_coordination as Q
import test_mixed as X
Q.Runner=factory;Q.Coordination.root=args.out/'coordination';Q.Coordination.root.mkdir(parents=True,exist_ok=True)
X.Runner=factory;X.Mixed.root=args.out/'mixed';X.Mixed.root.mkdir(parents=True,exist_ok=True)
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in [H.Cases,Q.Coordination,X.Mixed])
t=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite)
summary=dict(passed=r.wasSuccessful(),tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),seconds=time.monotonic()-t,risk_switch=enabled,source=Runner(keep_approved_risk=enabled).source_binding(),historical_account_events=0,reused_unchanged_test_sources={str(BASE/f):N.sha(BASE/f) for f in ['test_native.py','test_coordination.py','test_mixed.py']})
IO.write_json(args.out/'RESULTS.json',summary);print(json.dumps(summary));raise SystemExit(not r.wasSuccessful())
