"""Fresh process restores imported own Dec30 state, executes Jan3 only."""
import os,time,traceback
import preflight as F
H,A,N,J,L,IO,E,O=F.H,F.A,F.N,F.J,F.L,F.IO,F.E,F.O
def main():
 t=time.monotonic();gate=H.read(O/'TECHNICAL_GATE.json');assert gate['passed']
 N.configure_scores(H.SCORES)
 shared,receipts,cp,states,ir,identity=H.inputs();kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
 frozen=gate['sources'];assert all(H.sha(p)==h for p,h in frozen.items())
 r=H.Continuation(shared,receipts,**kw);r.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(r,L,O/'cross-process/restored-Dec30',canonicalize=J.W.canon):assert r.restore(O/'imported-Dec30/checkpoint.pkl')==H.PARENT_AT
 inventory=F.bounded_run(r,O/'cross-process/Jan3')
 expected=H.Continuation(shared,receipts,**kw);expected.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(expected,L,O/'cross-process/reference',canonicalize=J.W.canon):assert expected.restore(O/'first-session/full-input/checkpoint.pkl')==F.AT
 assert E.equal(F.economic_state(r),F.economic_state(expected))and r.episode_starts==expected.episode_starts
 parent=__import__('pickle').loads((H.PARENT/'checkpoint.pkl').read_bytes());acc=F.accounting(r,parent)
 assert all(H.sha(p)==h for p,h in frozen.items())
 H.save(O/'CROSS_PROCESS_GATE.json',dict(passed=True,separate_process=True,pid=os.getpid(),
  zero_event_imported_checkpoint_sha256=H.sha(O/'imported-Dec30/checkpoint.pkl'),reference_Jan3_checkpoint_sha256=H.sha(O/'first-session/full-input/checkpoint.pkl'),
  all_economic_state_and_exports_same=True,episode_lookup_same=True,accounting=acc,event_inventory=inventory,
  actual_native_OPEN_events=1,actual_native_CLOSE_events=1,Jan4_or_later_events=0,full_year_economic_paths=0,
  scripts_sha256={str(H.O/'cross_process.py'):H.sha(H.O/'cross_process.py'),str(H.O/'preflight.py'):H.sha(H.O/'preflight.py')},seconds=time.monotonic()-t))
 print('CROSS_PROCESS_JAN3_PASS',round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:H.save(O/'CROSS_PROCESS_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),full_year_economic_paths=0));raise
