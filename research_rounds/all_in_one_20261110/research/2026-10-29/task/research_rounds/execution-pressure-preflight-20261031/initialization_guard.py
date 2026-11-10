"""Minimal outer guard for input loading / runner construction, not trading."""
from pathlib import Path
import importlib.util
SOURCE=Path(__file__).resolve().parents[1]/'_shared/research_output_io.py'
spec=importlib.util.spec_from_file_location('pressure_startup_atomic_output',SOURCE)
IO=importlib.util.module_from_spec(spec);spec.loader.exec_module(IO)
def initialize(factory,output_root,stage):
 try:return factory()
 except BaseException as error:
  target=Path(output_root)/'failure/INITIALIZATION_ERROR.json'
  try:IO.write_json(target,dict(action=stage,error_type=type(error).__name__,reason=str(error)))
  except BaseException as report:error.add_note('Initialization failure report unavailable at '+str(target)+': '+str(report))
  raise
def smoke():
 import tempfile,json
 root=Path(tempfile.mkdtemp(prefix='pressure-constructor-error-',dir='/tmp'))
 class FailingConstructor:
  def __init__(self):raise RuntimeError('injected runner construction failure')
 try:initialize(FailingConstructor,root,'runner_construct')
 except RuntimeError:pass
 else:raise AssertionError('initialization unexpectedly succeeded')
 record=json.loads((root/'failure/INITIALIZATION_ERROR.json').read_text())
 assert record['action']=='runner_construct' and record['reason']=='injected runner construction failure'
 IO.write_json(Path(__file__).with_name('INITIALIZATION_GUARD_SMOKE.json'),dict(passed=True,tests=1,temp_evidence_root=str(root),details=record,economic_paths=0,actual_market_or_account_initialization=False))
if __name__=='__main__':smoke()
