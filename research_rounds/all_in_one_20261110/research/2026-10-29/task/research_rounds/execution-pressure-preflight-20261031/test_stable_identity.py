"""I/O identity regressions only; no historical events are executed."""
import hashlib,json,marshal,pickle,tempfile,types,unittest
from pathlib import Path
import pressure_runner as R
from initialization_guard import IO

class Tests(unittest.TestCase):
 def test_real_planning_code_identity_survives_checkpoint_unpickle(self):
  code=R.J.Runner.planning.__code__;before=IO._code_fingerprint(code)
  old=R.O/'cost2-runs/B3/prefix-full-source/checkpoint.pkl'
  if not old.exists():old=R.O/'cost2-runs-old-marshal-identity/B3/prefix-full-source/checkpoint.pkl'
  payload=pickle.loads(old.read_bytes())
  self.assertEqual(before,IO._code_fingerprint(code))
  # Changing object references/refcounts must not alter executable identity.
  references=[code,code.co_consts,code.co_names,code.co_varnames]*5
  self.assertEqual(before,IO._code_fingerprint(code));self.assertTrue(payload['accounts'])
 def test_changed_code_constant_and_bound_function_are_rejected(self):
  code=R.J.Runner.planning.__code__
  self.assertNotEqual(IO._code_fingerprint(code),IO._code_fingerprint(code.replace(co_consts=code.co_consts+('injected-change',))))
  root=Path(tempfile.mkdtemp(prefix='stable-code-identity-',dir='/tmp'));r=R.empty(R.B3CostRunner)
  at=R.J.M.N.iso('2025-07-07T15:10:00+08:00')
  with IO.atomic_runner_outputs(r,R.L,root,canonicalize=R.J.W.canon):r.checkpoint(root,at)
  r.planning=types.MethodType(lambda self,at:None,r)
  with self.assertRaisesRegex(ValueError,'identity mismatch'):
   with IO.atomic_runner_outputs(r,R.L,root,canonicalize=R.J.W.canon):r.restore(root/'checkpoint.pkl')
 def test_actual_empty_pressure_restore_stable_before_after(self):
  for cls in (R.B3CostRunner,R.DiagCostRunner):
   root=Path(tempfile.mkdtemp(prefix='stable-real-pressure-',dir='/tmp'));r=R.empty(cls)
   at=R.J.M.N.iso('2025-07-07T15:10:00+08:00')
   with IO.atomic_runner_outputs(r,R.L,root,canonicalize=R.J.W.canon):r.checkpoint(root,at)
   restored=R.empty(cls)
   with IO.atomic_runner_outputs(restored,R.L,root,canonicalize=R.J.W.canon):self.assertEqual(restored.restore(root/'checkpoint.pkl'),at)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 IO.write_json(R.O/'io-identity-fix-evidence/REGRESSION.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),old_io_sha256='e803758e7ed01172dfbb0f0dfa652acd90c9b80b0c1e6ea468fa67ea571a34f2',new_io_sha256=hashlib.sha256(IO.SOURCE.read_bytes()).hexdigest() if hasattr(IO,'SOURCE') else hashlib.sha256(Path(IO.__file__).read_bytes()).hexdigest(),economic_events_executed=0))
 raise SystemExit(not result.wasSuccessful())
