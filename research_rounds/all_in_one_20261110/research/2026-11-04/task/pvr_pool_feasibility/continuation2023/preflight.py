"""NO60 horizon:0event import, then authorized Jan3-only physical prefix."""
from pathlib import Path
from types import MappingProxyType
from decimal import Decimal as D
import ast,copy,json,pickle,time,traceback
import horizon_adapter as H
A,N,J,L,IO,E,O,P=H.A,H.N,H.J,H.L,H.IO,H.E,H.O,H.P
CUT='2023-01-03';AT=J.M.N.iso(CUT+'T15:10:00+08:00')

# Unchanged audited accounting/append-only helpers, no old controller entry.
helper_path=H.OLD2023/'first_session_preflight.py'
helper_ast=ast.parse(helper_path.read_text())
helper_nodes=[n for n in helper_ast.body if isinstance(n,ast.FunctionDef)and n.name in ['economic_state','historical_append_proof','accounting']]
_env=dict(E=E,J=J,D=D,CUT=CUT,AT=AT)
exec(compile(ast.Module(body=helper_nodes,type_ignores=[]),str(helper_path),'exec'),_env)
economic_state=_env['economic_state'];append_proof=_env['historical_append_proof'];accounting=_env['accounting']
def save(p,x):H.save(p,x)
def snapshot(r):
 immutable={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds'}
 return dict(accounts={k:{n:v for n,v in a.__dict__.items()if n not in ['market','facts']}for k,a in r.accounts.items()},
  runner={k:v for k,v in r.__dict__.items()if k not in immutable})

def bounded_run(r,out):
 assert not(O/'FULL_2023_RUN_AUTHORIZATION.json').exists(),'Jan3 technical entry only'
 assert not(out/'DONE.json').exists(),'do not repeat a completed prefix'
 assert r.horizon_last_completed==H.PARENT_AT
 inventory=r.next_event_inventory(CUT)
 assert inventory[0]['at']=='2023-01-03 09:30:00+08:00'and inventory[-1]['at']==str(AT)
 cursor=r._claim_cursor(H.PARENT_AT)
 try:
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert H.H._run_original(r,out,120,resume_after=cursor,end=CUT)
 finally:r._cursor_claimed=False
 assert r.horizon_last_completed==AT
 return inventory

def main():
 begun=time.monotonic();assert not(O/'FULL_2023_RUN_AUTHORIZATION.json').exists()
 assert not(O/'TECHNICAL_GATE.json').exists(),'do not repeat completed gate'
 binding=H.create_binding()
 prefix=H.H.score_prefix_proof();save(O/'SCORE_PREFIX_PROOF.json',prefix)
 N.configure_scores(H.SCORES)
 shared,receipts,cp,states,ir,identity=H.inputs();loaded=time.monotonic()-begun
 frozen=H.source_freeze();save(O/'HORIZON_SOURCE_FREEZE.json',dict(sources=frozen,input_identity=identity,full_year_authorized=False,before_state_import=True))
 kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
 r=H.Continuation(shared,receipts,**kw);r.source_freeze=dict(frozen)
 proof=r.import_verified_parent();save(O/'VERIFIED_HORIZON_IMPORT.json',proof)
 parent=pickle.loads((H.PARENT/'checkpoint.pkl').read_bytes())
 before=copy.deepcopy(snapshot(r));lookup=dict(r.episode_starts)
 inventory=r.next_event_inventory(CUT);assert E.equal(before,snapshot(r))
 imported=O/'imported-Dec30'
 with IO.atomic_runner_outputs(r,L,imported,canonicalize=J.W.canon):r.checkpoint(imported,H.PARENT_AT)
 assert E.equal(before,snapshot(r))and r.episode_starts==lookup
 restored=H.Continuation(shared,receipts,**kw);restored.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(restored,L,O/'zero-event-restart',canonicalize=J.W.canon):assert restored.restore(imported/'checkpoint.pkl')==H.PARENT_AT
 assert E.equal(before,snapshot(restored))and restored.episode_starts==lookup
 failures={}
 try:restored.import_verified_parent()
 except AssertionError as e:failures['duplicate_parent_import']=str(e)
 claim=copy.copy(restored);claim._claim_cursor(H.PARENT_AT)
 try:claim._claim_cursor(H.PARENT_AT)
 except AssertionError as e:failures['duplicate_cursor_claim']=str(e)
 wrong=copy.copy(restored)
 try:wrong._claim_cursor(AT)
 except AssertionError as e:failures['skip_Jan3_wrong_cursor']=str(e)
 try:restored.run_prepared(O/'FORBIDDEN-full-year',1,resume_after=H.PARENT_AT,end=CUT)
 except AssertionError as e:failures['full_year_without_root_grant']=str(e)
 assert E.equal(before,snapshot(restored))
 for label,change in [('wrong_oldPVR_parent',{'parent_checkpoint':str(H.OLD/'runs/2022/checkpoint.pkl')}),
  ('wrong_new_score',{'new_score_manifest_sha256':H.OLD_SCORE_SHA}),('wrong_parent_NAV',{'parent_NAV':'715009.3354426633890'})]:
  bad=dict(binding,**change);path=O/'negative-bindings'/(label+'.json');save(path,bad)
  shell=H.Continuation(shared,receipts,binding=path,**kw);shell.source_freeze=dict(frozen);virgin=copy.deepcopy(snapshot(shell))
  try:shell.import_verified_parent(path)
  except AssertionError as e:failures[label]=str(e)
  assert label in failures and E.equal(virgin,snapshot(shell)),label
 oldclass=A.Runner.__new__(A.Runner)
 try:
  with IO.atomic_runner_outputs(oldclass,L,O/'wrong-generation-class',canonicalize=J.W.canon):IO.assert_checkpoint_identity(oldclass,imported/'checkpoint.pkl')
 except ValueError as e:failures['new_checkpoint_wrong_generating_class']=str(e)
 assert len(failures)==8,failures
 save(O/'IMPORT_GATE.json',dict(passed=True,scope='zero-event own-state horizon import only',actual_new_account_events=0,
  account_fields=proof['account_field_count'],strategy_fields=proof['strategy_field_count'],all_parent_book_streams_exact=True,
  own_parent_NAV=proof['parent_NAV'],held_stocks=proof['held_stocks'],pending_intents=proof['pending_intents'],
  future_lookup_only=True,prefix_score_cells=prefix['cells'],negative_guards=failures,event_inventory=inventory,
  source_freeze=frozen,input_load_seconds=loaded,elapsed_seconds=time.monotonic()-begun))
 print('ZERO_EVENT_IMPORT_PASS',proof['parent_NAV'],'fields',proof['account_field_count'],proof['strategy_field_count'],'pending',proof['pending_intents'],round(time.monotonic()-begun,2),flush=True)
 # Same already-authorized technical Jan3 branch; no full-year entry invoked.
 full=O/'first-session/full-input';bounded_run(r,full)
 full_append=append_proof(r,parent);full_accounting=accounting(r,parent)
 save(O/'first-session/FULL_ACCOUNTING.json',full_accounting)
 phy,rr,pk=A.S.physical_inputs(shared,receipts,cp,states,ir,CUT)
 fullscores=N.SCORES;cutscore=copy.copy(fullscores)
 cutscore.values=MappingProxyType({s:MappingProxyType({d:v for d,v in rs.items()if d<=CUT})for s,rs in fullscores.values.items()})
 calls=[]
 def past_only(sid,d):assert d<=CUT;calls.append((sid,d));return N.FrozenScores.at(cutscore,sid,d)
 cutscore.at=past_only;N.SCORES=cutscore
 try:
  q=H.Continuation(phy,rr,**pk);q.source_freeze=dict(frozen);q.import_verified_parent()
  assert E.equal(q.accounts['B'].pending,parent['accounts']['B']['pending'])
  assert bounded_run(q,O/'first-session/physical-input')==inventory
  assert E.equal(economic_state(q),economic_state(r)),'full vs physical economic state'
  assert q.episode_starts=={k:v for k,v in r.episode_starts.items()if v<=AT.date().toordinal()}
  assert q.rank_log==r.rank_log and append_proof(q,parent)==full_append
  physical_accounting=accounting(q,parent);save(O/'first-session/PHYSICAL_ACCOUNTING.json',physical_accounting)
 finally:N.SCORES=fullscores
 restarted=H.Continuation(shared,receipts,**kw);restarted.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(restarted,L,O/'first-session/same-process-restart',canonicalize=J.W.canon):assert restarted.restore(full/'checkpoint.pkl')==AT
 assert E.equal(economic_state(restarted),economic_state(r))and restarted.episode_starts==r.episode_starts
 assert all(H.sha(p)==h for p,h in frozen.items())
 save(O/'TECHNICAL_GATE.json',dict(passed=True,scope='Jan3-only technical prefix, full year remains unauthorized',
  own_parent_NAV=proof['parent_NAV'],parent_cursor=str(H.PARENT_AT),last_completed=str(AT),
  complete_economic_state_and_event_streams_exact=True,old_history_append_only=full_append,
  full_accounting=full_accounting,physical_PVR_values_truncated=True,physical_score_max_date=max(d for s,d in calls),
  same_process_restore_all_state_exact=True,independent_process_restart_pending=True,
  prefix_checkpoint_for_later_continuation=str(full/'checkpoint.pkl'),prefix_checkpoint_sha256=H.sha(full/'checkpoint.pkl'),
  actual_native_OPEN_invocations=2,actual_native_CLOSE_invocations=2,Jan4_or_later_events=0,
  new_simulated_fills_by_branch=dict(full=full_accounting['new_fills'],physical=physical_accounting['new_fills']),
  full_year_economic_paths=0,sources=frozen,seconds=time.monotonic()-begun))
 print('JAN3_PHYSICAL_PASS',round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),full_year_economic_paths=0));raise
