"""New-process own-state restore and Jan2 replay only; no Jan3/full2024 run."""
import argparse,os,time,traceback,pickle
import cycle2024_preflight as F
C,N,J,L,IO,E=F.C,F.N,F.J,F.L,F.IO,F.E
def main(policy):
 t=time.monotonic();root=C.root(policy);gate=C.read(root/'TECHNICAL_GATE.json');assert gate['passed']and not(root/'CROSS_PROCESS_GATE.json').exists()
 N.configure_scores(C.NEW_SCORE);shared,receipts,cp,states,ir,identity=C.inputs();kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
 frozen=gate['source_freeze'];assert all(C.sha(p)==h for p,h in frozen.items());cls=C.CLASSES[policy]
 r=cls(shared,receipts,**kw);r.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(r,L,root/'cross-process/restored-Dec29',canonicalize=J.W.canon):assert r.restore(root/'imported-Dec29/checkpoint.pkl')==C.PARENT_AT
 inventory=F.bounded_run(r,root/'cross-process/Jan2')
 expected=cls(shared,receipts,**kw);expected.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(expected,L,root/'cross-process/reference',canonicalize=J.W.canon):assert expected.restore(root/'first-session/full-input/checkpoint.pkl')==F.AT
 assert E.equal(F.state(r),F.state(expected))and r.episode_starts==expected.episode_starts
 parent=pickle.loads((C.PARENTS[policy]/'checkpoint.pkl').read_bytes());accounting=F.accounting(r,parent)
 assert all(C.sha(p)==h for p,h in frozen.items())
 C.save(root/'CROSS_PROCESS_GATE.json',dict(passed=True,policy=policy,separate_process=True,pid=os.getpid(),
  restored_parent_checkpoint_sha256=C.sha(root/'imported-Dec29/checkpoint.pkl'),
  reference_Jan2_checkpoint_sha256=C.sha(root/'first-session/full-input/checkpoint.pkl'),
  complete_state_and_lookup_exact=True,accounting=accounting,event_inventory=inventory,
  actual_native_OPEN_invocations=1,actual_native_CLOSE_invocations=1,Jan3_or_later_events=0,full_year_paths=0,
  seconds=time.monotonic()-t))
 print('CYCLE2024_CROSS_PASS',policy,round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--policy',choices=['original','no60'],required=True);a=ap.parse_args()
 try:main(a.policy)
 except BaseException as e:C.save(C.root(a.policy)/'CROSS_PROCESS_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),full_year_paths=0));raise
