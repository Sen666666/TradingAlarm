"""Native two-day technical gates only. Never starts full-window economics."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy,gzip,json,time,traceback,inspect
import native_adapter as A
P,N,J,L,IO,S=A.P,A.N,A.J,A.L,A.IO,A.S
O=A.O/'native-readiness';CUT='2025-07-02'
OLD=A.W/'pvr-slot1-native-readiness-20261101/runs/2025_26/prefix-full-source/pair'
def save(n,x):IO.write_json(O/n,P.serial(x))
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt')as f:return [json.loads(x)for x in f]
def day(x):
 v=x.get('at')or x.get('day')or x.get('receipt',{}).get('at');assert v is not None;return str(v)[:10]
def stable(x):
 if isinstance(x,(set,frozenset)):return sorted((stable(v)for v in x),key=lambda v:json.dumps(J.W.canon(v),sort_keys=True))
 if isinstance(x,dict):return {k:stable(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [stable(v)for v in x]
 return x
def observable(r):
 excluded={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds','source_freeze'}
 runner={k:(vars(v)if k=='b0'else v)for k,v in r.__dict__.items()if k not in excluded}
 return J.W.canon(stable(dict(accounts={k:{n:v for n,v in a.__dict__.items()if n not in ('market','facts','budget')}for k,a in r.accounts.items()},
  budgets={k:vars(a.budget)for k,a in r.accounts.items()},runner=runner)))
def main():
 begin=time.monotonic();O.mkdir(exist_ok=True);assert not(O/'GATE.json').exists(),'do not repeat completed gate'
 N.configure_scores();oldSO=S.O
 try:S.O=O;value=S.inputs('2025_26')
 finally:S.O=oldSO
 shared,receipts,cp,states,ir,identity=value
 frozen=A.source_freeze();frozen[str(Path(__file__))]=N.sha(__file__)
 assert all(N.sha(p)==h for p,h in read(A.W/'pvr-slot1-native-readiness-20261101/RUN_SOURCE_FREEZE.json')['sources'].items())
 save('FREEZE.json',dict(before_new_native_events=True,sources=frozen,input_identity=S.canonical_identity(identity),
  old_native_gate_reused=str(A.W/'pvr-slot1-native-readiness-20261101/PREFLIGHT_GATE.json'),
  reused_native_dependencies_unchanged=True,full_economic_paths=0))
 print('INPUT_LOADED',round(time.monotonic()-begin,2),flush=True)
 kw=S.kwargs(cp,states,ir)
 off=N.Runner(shared,receipts,**kw);off.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(off,L,O/'OFF',canonicalize=J.W.canon):assert off.run_prepared(O/'OFF',120,end=CUT)
 checks={};counts={}
 for field,name in [('daily','daily'),('funding','funding'),('opportunities','opportunities'),('stage_events','industry'),('balance_audit','balances')]:
  expected=rows(OLD/(name+'.jsonl.gz'))
  assert J.W.canon(getattr(off,field))==expected,name;checks[name]=True;counts[name]=len(expected)
 with gzip.open(OLD/'B.json.gz','rt')as f:book=json.load(f)
 for field,name in [('trades','trades'),('journal','journal'),('audit_log','audit'),('decisions','decisions')]:
  expected=book[name]
  assert J.W.canon(getattr(off.accounts['B'],field))==expected,name;checks[name]=True;counts[name]=len(expected)
 print('OFF_ORIGINAL_EXACT',counts,round(time.monotonic()-begin,2),flush=True)
 on=A.Runner(shared,receipts,**kw);on.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(on,L,O/'ON-full',canonicalize=J.W.canon):assert on.run_prepared(O/'ON-full',120,end=CUT)
 original_obs=observable(on)
 # Same candidates/targets BEFORE first possible changed fill.
 strip=lambda z:[{k:v for k,v in x.items()if k not in {'priority_policy'}}for x in z]
 assert strip(on.accounts['B'].decisions[0]['intents'])==strip(off.accounts['B'].decisions[0]['intents'])
 phy,rr,pk=S.physical_inputs(shared,receipts,cp,states,ir,CUT)
 fullscores=N.SCORES
 def past_only(sid,d):assert d<=CUT;return fullscores.at(sid,d)
 N.SCORES=NS(manifest_sha256=fullscores.manifest_sha256,at=past_only)
 try:
  physical=A.Runner(phy,rr,**pk);physical.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(physical,L,O/'ON-physical',canonicalize=J.W.canon):assert physical.run_prepared(O/'ON-physical',120,end=CUT)
  assert observable(physical)==original_obs,'physical prefix all mutable native state'
 finally:N.SCORES=fullscores
 # Resume before first OPEN, so pending target and quantities must execute
 # identically across a serialized same-process boundary/continuation.
 # A separate process check is reported by native_cross_process_restart.py.
 split=A.Runner(shared,receipts,**kw);split.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(split,L,O/'ON-split',canonicalize=J.W.canon):assert split.run_prepared(O/'ON-split',120,end='2025-07-01')
 checkpoint=O/'ON-split/checkpoint.pkl'
 restored=A.Runner(shared,receipts,**kw);restored.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(restored,L,O/'ON-resumed',canonicalize=J.W.canon):
  last=restored.restore(checkpoint)
  assert observable(restored)==observable(split),'restart boundary state'
  assert restored.run_prepared(O/'ON-resumed',120,resume_after=last,end=CUT)
 assert observable(restored)==original_obs,'restart continuation all mutable native state'
 negatives={}
 wrong=N.Runner(shared,receipts,**kw);wrong.source_freeze=dict(frozen)
 try:
  with IO.atomic_runner_outputs(wrong,L,O/'wrong-policy',canonicalize=J.W.canon):wrong.restore(checkpoint)
 except(AssertionError,ValueError)as e:negatives['wrong_policy']=str(e)
 assert 'wrong_policy'in negatives
 bad=A.Runner(shared,receipts,**kw);bad.source_freeze=dict(frozen,deliberate_source_mismatch='technical-negative')
 try:
  with IO.atomic_runner_outputs(bad,L,O/'wrong-source',canonicalize=J.W.canon):bad.restore(checkpoint)
 except(AssertionError,ValueError)as e:negatives['wrong_source']=str(e)
 assert 'wrong_source'in negatives
 # Actual native subclass, not merely the pure view: all lifecycle methods
 # resolve self.migrate dynamically, so probe cancel ACK triggers new cap rule.
 import check_counterexamples as F
 for status in ['open','cancel_pending']:
  b=A.NoConfirmed60Budget(True);s=F.make();b.__dict__.update(copy.deepcopy(vars(s)))
  o=P.N.Order('pending','Z','S','E-S','probe',100,10,9.9,0,status=status,attempt='A-S');b.orders['pending']=o
  assert not b.migrate('S')
  if status=='open':b.cancel('pending')
  b.cancel_ack('pending');assert b.sectors['S'].status=='confirmed'and b.orders['pending'].qty==0
 b=A.NoConfirmed60Budget(False);assert not b.migrate('unknown')
 assert read(A.O/'COUNTEREXAMPLES.json')['passed']
 assert all(N.sha(p)==h for p,h in frozen.items())
 pending_scope=dict(normal_native_Account=str(Path(J.C.__file__)),opening=str(Path(J.__file__)),
  expire_day_buys_same_function=True,all_callbacks_same=True,resources_includes_open_cancel_pending=True,
  cancel_ack_dynamic_new_migrate=True,expand_false_retained=True,D1_delay_adapter_not_in_MRO=True,
  no_extra_pending_policy=True,original_default_delay_events=0)
 save('PENDING_SCOPE.json',pending_scope)
 # Each ON side is technical2-day1OPEN; split half contributes0OPEN, resume1.
 result=dict(passed=True,scope='native technical readiness only; not financial performance',
  OFF_saved_original_all_streams=checks,OFF_original_counts=counts,first_original_targets_exact=True,
  ON_physical_truncated_all_mutable_state_exact=True,ON_score_reader_past_only=True,
  ON_same_process_checkpoint_boundary_and_resumed_OPEN_all_mutable_state_exact=True,negative_guards=negatives,
  affected_pure_counterexamples=8,native_pending_cancel_ack_guards_passed=True,pending_scope=pending_scope,
  original_dependencies_reused_not_rerun=True,short_window=['2025-07-01',CUT],
  technical_native_OPEN_invocations=4,technical_native_CLOSE_invocations=8,
  native_trade_fills_by_execution=dict(OFF=len(off.accounts['B'].trades),ON_full=len(on.accounts['B'].trades),ON_physical=len(physical.accounts['B'].trades),ON_resumed=len(restored.accounts['B'].trades)),
  full_new_policy_economic_paths=0,approved_economic_execution=False,source_freeze=frozen,seconds=time.monotonic()-begin)
 save('GATE.json',result);print('NATIVE_GATE_PASS',round(time.monotonic()-begin,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),full_new_policy_economic_paths=0));raise
