"""Own-state0event import then root-authorized Jan2-only physical prefix."""
from pathlib import Path
from types import MappingProxyType
from decimal import Decimal as Dec
import argparse,ast,copy,gc,pickle,time,traceback
import cycle2024_adapter as C
N,J,L,IO,E,O=C.N,C.J,C.L,C.IO,C.E,C.O
CUT='2024-01-02';AT=J.M.N.iso(CUT+'T15:10:00+08:00')
helper=C.OLD/'first_session_preflight.py'
nodes=[n for n in ast.parse(helper.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in {'historical_append_proof','accounting'}]
env=dict(E=E,J=J,D=Dec,CUT=CUT,AT=AT)
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(helper),'exec'),env)
append_proof,accounting=env['historical_append_proof'],env['accounting']
def state(r):
 x=E.observable(r);x['runner'].pop('cycle_transition',None);return x
def bounded_run(r,out):
 assert not(out/'DONE.json').exists(),'do not repeat committed technical prefix'
 assert r.cycle_last_completed==C.PARENT_AT
 bind=r.assert_cycle_binding();assert bind['last_permitted_technical_event']==str(AT)
 assert not(C.root(r.cycle_policy)/'FULL_2024_RUN_AUTHORIZATION.json').exists(),'technical entry has no full-year grant'
 inventory=C.D.next_events((r.bundle,r.market,r.facts))
 assert inventory[0]['at']=='2024-01-02 09:30:00+08:00'and inventory[-1]['at']==str(AT)
 cursor=r.claim_cursor(C.PARENT_AT)
 try:
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert L.PreparedRunner.run_prepared(r,out,120,resume_after=cursor,end=CUT)
 finally:r.cycle_claimed=False
 assert r.cycle_last_completed==AT;return inventory

def main(policy):
 begun=time.monotonic();root=C.root(policy);assert not(root/'TECHNICAL_GATE.json').exists(),'completed gate may only restore'
 C.D.assert_data();binding=C.create_binding(policy);N.configure_scores(C.NEW_SCORE)
 shared,receipts,cp,states,ir,identity=C.inputs();loaded=time.monotonic()-begun
 kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir);cls=C.CLASSES[policy]
 frozen=C.source_freeze(policy);C.save(root/'HORIZON_SOURCE_FREEZE.json',dict(sources=frozen,input_identity=identity,full_year_authorized=False))
 r=cls(shared,receipts,**kw);r.source_freeze=dict(frozen)
 proof=r.import_verified_parent();C.save(root/'VERIFIED_HORIZON_IMPORT.json',proof)
 parent=pickle.loads((C.PARENTS[policy]/'checkpoint.pkl').read_bytes())
 imported=root/'imported-Dec29'
 with IO.atomic_runner_outputs(r,L,imported,canonicalize=J.W.canon):r.checkpoint(imported,C.PARENT_AT)
 z=cls(shared,receipts,**kw);z.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(z,L,root/'zero-event-restart',canonicalize=J.W.canon):assert z.restore(imported/'checkpoint.pkl')==C.PARENT_AT
 assert E.equal(state(z),state(r))and z.episode_starts==r.episode_starts
 failures={}
 try:z.import_verified_parent()
 except AssertionError as e:failures['duplicate_parent_import']=str(e)
 claim=copy.copy(z);claim.claim_cursor(C.PARENT_AT)
 try:claim.claim_cursor(C.PARENT_AT)
 except AssertionError as e:failures['duplicate_cursor']=str(e)
 wrong=copy.copy(z)
 try:wrong.claim_cursor(AT)
 except AssertionError as e:failures['skip_Jan2_wrong_cursor']=str(e)
 try:z.run_prepared(root/'FORBIDDEN-full',1,resume_after=C.PARENT_AT,end=CUT)
 except AssertionError as e:failures['no2024_full_grant']=str(e)
 assert len(failures)==4 and E.equal(state(z),state(r))
 # Same source code but other policy runtime must not restore this state.
 other=C.CLASSES['no60'if policy=='original'else'original'].__new__(C.CLASSES['no60'if policy=='original'else'original'])
 try:
  with IO.atomic_runner_outputs(other,L,root/'wrong-policy-generation',canonicalize=J.W.canon):IO.assert_checkpoint_identity(other,imported/'checkpoint.pkl')
 except ValueError as e:failures['wrong_policy_generating_class']=str(e)
 assert len(failures)==5
 C.save(root/'IMPORT_GATE.json',dict(passed=True,account_events=0,parent_cursor=str(C.PARENT_AT),parent_NAV=proof['parent_NAV'],
  account_fields=len(proof['all_account_fields_equal']),strategy_fields=len(proof['all_strategy_fields_equal']),
  all_parent_book_and6_streams_exact=True,full_state_zero_event_restore_exact=True,negative_guards=failures,
  source_freeze=frozen,seconds=time.monotonic()-begun))
 print('CYCLE2024_IMPORT_PASS',policy,proof['parent_NAV'],round(time.monotonic()-begun,2),flush=True)
 del z;gc.collect()
 inventory=bounded_run(r,root/'first-session/full-input')
 full_append=append_proof(r,parent);full_acc=accounting(r,parent);C.save(root/'first-session/FULL_ACCOUNTING.json',full_acc)
 print('CYCLE2024_JAN2_FULL',policy,str(r.accounts['B'].current_nav),full_acc['new_fills'],flush=True)
 phy,rr,pk=C.D.S.physical_inputs(shared,receipts,cp,states,ir,CUT)
 fullscores=N.SCORES;smallscore=copy.copy(fullscores)
 smallscore.values=MappingProxyType({s:MappingProxyType({d:v for d,v in rs.items()if d<=CUT})for s,rs in fullscores.values.items()})
 calls=[]
 def past_only(s,d):assert d<=CUT;calls.append((s,d));return N.FrozenScores.at(smallscore,s,d)
 smallscore.at=past_only;N.SCORES=smallscore
 try:
  q=cls(phy,rr,**pk);q.source_freeze=dict(frozen);qproof=q.import_verified_parent()
  assert E.equal(q.accounts['B'].pending,parent['accounts']['B']['pending'])
  assert bounded_run(q,root/'first-session/physical-input')==inventory
  assert E.equal(state(q),state(r)),'full/physical complete state differs'
  assert q.episode_starts=={k:v for k,v in r.episode_starts.items()if v<=AT.date().toordinal()}
  assert append_proof(q,parent)==full_append
  phy_acc=accounting(q,parent);C.save(root/'first-session/PHYSICAL_ACCOUNTING.json',phy_acc)
 finally:N.SCORES=fullscores
 del q;gc.collect()
 restarted=cls(shared,receipts,**kw);restarted.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(restarted,L,root/'first-session/same-process-restart',canonicalize=J.W.canon):assert restarted.restore(root/'first-session/full-input/checkpoint.pkl')==AT
 assert E.equal(state(restarted),state(r))and restarted.episode_starts==r.episode_starts
 assert all(C.sha(p)==h for p,h in frozen.items())
 C.save(root/'TECHNICAL_GATE.json',dict(passed=True,policy=policy,parent_cursor=str(C.PARENT_AT),parent_NAV=proof['parent_NAV'],
  last_completed=str(AT),complete_state_full_physical_exact=True,all_old_history_append_only=full_append,
  full_accounting=full_acc,same_process_restore_exact=True,separate_process_restore_pending=True,
  physical_score_reads=len(calls),physical_max_score_date=max((d for s,d in calls),default=None),
  source_freeze=frozen,prefix_checkpoint=str(root/'first-session/full-input/checkpoint.pkl'),
  actual_native_OPEN_invocations=2,actual_native_CLOSE_invocations=2,Jan3_or_later_events=0,full_year_paths=0,
  input_load_seconds=loaded,seconds=time.monotonic()-begun))
 print('CYCLE2024_JAN2_PHYSICAL_PASS',policy,round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--policy',choices=['original','no60'],required=True);args=ap.parse_args()
 try:main(args.policy)
 except BaseException as e:C.save(C.root(args.policy)/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),full_year_paths=0));raise
