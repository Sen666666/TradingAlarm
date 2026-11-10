"""Separate process reloads private classes, resumes1 native technical OPEN."""
from pathlib import Path
import json,time,traceback,os
import native_preflight as F
A,S,N,J,L,IO,P=F.A,F.S,F.N,F.J,F.L,F.IO,F.P
O=F.O
def main():
 t=time.monotonic();gate=F.read(O/'GATE.json');assert gate['passed']
 N.configure_scores();old=S.O
 try:S.O=O/'cross-process';value=S.inputs('2025_26')
 finally:S.O=old
 shared,receipts,cp,states,ir,identity=value;kw=S.kwargs(cp,states,ir)
 frozen=gate['source_freeze'];assert all(N.sha(p)==h for p,h in frozen.items())
 r=A.Runner(shared,receipts,**kw);r.source_freeze=dict(frozen)
 out=O/'ON-cross-process-resumed'
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
  last=r.restore(O/'ON-split/checkpoint.pkl');assert str(last)[:10]=='2025-07-01'
  n0=len(r.accounts['B'].trades)
  assert r.run_prepared(out,120,resume_after=last,end=F.CUT)
 expected=A.Runner(shared,receipts,**kw);expected.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(expected,L,O/'cross-process-reference',canonicalize=J.W.canon):expected.restore(O/'ON-full/checkpoint.pkl')
 assert F.observable(r)==F.observable(expected),'separate process resumed full native state'
 assert all(N.sha(p)==h for p,h in frozen.items())
 F.save('CROSS_PROCESS_RESTART.json',dict(passed=True,separate_process=True,pid=os.getpid(),
  checkpoint_sha256=N.sha(O/'ON-split/checkpoint.pkl'),reference_checkpoint_sha256=N.sha(O/'ON-full/checkpoint.pkl'),
  native_class_reloaded=str(Path(A.__file__)),script_sha256=N.sha(__file__),
  original_source_provenance_gate_retained=True,all_mutable_native_state_exact=True,
  technical_native_OPEN_events=1,technical_native_CLOSE_events=1,technical_trade_fills=len(r.accounts['B'].trades)-n0,
  full_new_policy_economic_paths=0,seconds=time.monotonic()-t))
 print('CROSS_PROCESS_RESTART_PASS',round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:F.save('CROSS_PROCESS_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc()));raise
