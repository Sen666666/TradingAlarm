"""Actual R1 Pair empty-state export/restore only; no account/market/events."""
from pathlib import Path
import hashlib,json,tempfile
import adapter_r1 as R
J=R.J;L=R.L;O=R.O
IO=J.W.load('R1_real_pair_atomic_output',O.parent/'_shared/research_output_io.py')
H=J.W.load('R1_real_pair_IO_harness',O/'run_one.py')
Wrong=J.W.load('R1_wrong_baseline_IO_harness',R.BASE.O/'run_one.py')
def empty(cls):
 r=cls.__new__(cls)
 for name in ('daily','opportunities','funding','stage_events','balance_audit','r1_previews','r1_reservations'):setattr(r,name,[])
 r.accounts={};r.source_freeze={};return r
def files(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and 'failure' not in p.parts}
def main():
 root=Path(tempfile.mkdtemp(prefix='real-R1-output-smoke-',dir='/tmp'));at=J.M.N.iso('2025-07-07T15:10:00+08:00');r=empty(H.Pair);cls=type(r);save=L.save;checks=[]
 with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):
  assert r.planning.__func__ is R.Runner.planning and r.route.__func__ is R.Runner.route
  r.checkpoint(root,at);r.dump_joint(root/'pair')
 assert type(r) is cls and L.save is save;checks.append('actual empty R1 Pair checkpoint/dump success; trading bindings unchanged')
 provenance=json.loads((root/'checkpoint.provenance.json').read_text());assert provenance['engine_identity']['trading_class']['module_path']==str((O/'run_one.py').resolve())
 assert all(provenance['engine_identity']['functions'][x]['code_sha256'] for x in ['planning','opening','route']);checks.append('new checkpoint records actual class/module/file plus function origin and code SHA at generation')
 restored=empty(H.Pair)
 with IO.atomic_runner_outputs(restored,L,root,canonicalize=J.W.canon):assert restored.restore(root/'checkpoint.pkl')==at
 assert restored.planning.__func__ is R.Runner.planning;checks.append('actual empty R1 Pair restore passes before/after identity assertions')
 prior=files(root)
 class BrokenRecords(list):
  def __iter__(self):raise RuntimeError('injected actual Pair export failure')
 r.opportunities=BrokenRecords()
 try:
  with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):r.dump_joint(root/'pair')
 except RuntimeError:pass
 else:raise AssertionError('expected export error')
 assert prior==files(root) and type(r) is cls and L.save is save;checks.append('actual export failure preserves all published files and reports error')
 r.opportunities=[];r.unpicklable=lambda:None
 try:
  with IO.atomic_runner_outputs(r,L,root,canonicalize=J.W.canon):r.checkpoint(root,at)
 except Exception:pass
 else:raise AssertionError('expected pickle error')
 assert prior==files(root) and type(r) is cls and L.save is save;del r.unpicklable;checks.append('actual checkpoint serialization failure preserves old files and class/save')
 conflict=root/'preflight-conflict';conflict.mkdir();(conflict/'prefix-full-source').write_bytes(b'blocking file');(conflict/'failure').mkdir()
 try:
  with IO.atomic_runner_outputs(r,L,conflict,canonicalize=J.W.canon):raise AssertionError('must not enter body')
 except (NotADirectoryError,FileExistsError):pass
 else:raise AssertionError('expected preflight failure')
 assert (conflict/'failure/ERROR.json').exists() and type(r) is cls and L.save is save;checks.append('preflight path conflict now writes ERROR even before class/save modification')
 wrong=empty(Wrong.Pair)
 try:
  with IO.atomic_runner_outputs(wrong,L,root,canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
 except ValueError as e:assert 'identity mismatch' in str(e)
 else:raise AssertionError('wrong baseline Pair accepted')
 checks.append('wrong same-name baseline Pair is rejected before restore')
 legacy=root/'legacy-test-copy.pkl';legacy.write_bytes((root/'checkpoint.pkl').read_bytes())
 try:
  with IO.atomic_runner_outputs(restored,L,root,canonicalize=J.W.canon):restored.restore(legacy)
 except ValueError as e:assert 'must not be backfilled' in str(e)
 else:raise AssertionError('legacy missing identity accepted')
 assert not legacy.with_suffix('.provenance.json').exists();checks.append('legacy missing generation identity fails explicitly, no backfill')
 assert not list(root.rglob('*.tmp')) and not list(root.rglob('.checkpoint-staging-*')) and not list(root.rglob('.journal-staging-*'))
 payload=dict(passed=True,checks=len(checks),details=checks,actual_R1_class=cls.__module__+'.'+cls.__name__,temp_evidence_root=str(root),economic_events=0,accounts_initialized=0,new_historical_paths=0,source_sha256=hashlib.sha256((O.parent/'_shared/research_output_io.py').read_bytes()).hexdigest(),limitations=['single-file atomicity, not a multi-file transaction or power-loss test','completed historical R1 checkpoints remain legacy without generation-time class fields; no backfill'])
 IO.write_json(O/'REAL_PAIR_IO_SMOKE.json',payload);print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
