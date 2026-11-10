"""Import/restore/source/cursor preflight only; zero 2023 market events."""
from pathlib import Path
from datetime import datetime,timezone
import json,time,copy,pickle,hashlib
import horizon_import as H
N,J,L,IO,E,O,P,W=H.N,H.J,H.L,H.IO,H.E,H.O,H.P,H.W

def snap(r):
    immutable={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days',
               'industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds'}
    return dict(accounts={k:{a:v for a,v in x.__dict__.items() if a not in ('market','facts')}
                          for k,x in r.accounts.items()},
                runner={k:v for k,v in r.__dict__.items() if k not in immutable})

def manifest():
    path=H.DEFAULT_BINDING
    if path.exists():
        b=H.read(path)
        assert b['horizon_import_sha256']==H.sha(H.__file__),'existing bound source changed; preserve/review rather than silently rebind'
        return b
    parent=P/'runs/2022/checkpoint.pkl'
    ids=[W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',
         W/'recovery-2023-readiness-20261101/inputs/COMPLETION.json',
         W/'recovery-2023-readiness-20261101/RIGHTS_2023.json',
         W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',
         W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv',J.M.P/'h1.npz']
    b=dict(created_at_UTC=datetime.now(timezone.utc).isoformat(),scope='PVR_SLOT1_2023_import_preflight_only',
       authority='explicit root delegation permits horizon import/state/data preflight only; no2023account events',
       native_adapter_sha256=H.ADAPTER_SHA,horizon_import_sha256=H.sha(H.__file__),
       parent_checkpoint=str(parent.resolve()),parent_checkpoint_sha256=H.sha(parent),
       parent_provenance_sha256=H.sha(parent.with_suffix('.provenance.json')),
       parent_last_event=str(H.PARENT_AT),old_score_manifest_sha256=H.OLD_SCORE_SHA,
       new_score_manifest_sha256=H.NEW_SCORE_SHA,new_input_identities={str(p.resolve()):H.sha(p) for p in ids},
       market_window=['2023-01-03','2023-12-29'],event_cursor='strictly after2022-12-30 15:10+08:00',
       no_cash_or_risk_or_policy_reset=True,source_algorithm_unchanged=True,finance_authorized=False)
    IO.write_json(path,b);return b

def main():
    begun=time.monotonic();root=O/'import-preflight'
    IO.prepare_targets(dict(checkpoint=root/'checkpoint.pkl',failure=root/'failure/ERROR.json',
                           final=root/'pair'),directory_keys={'final'})
    assert not (O/'FULL_2023_RUN_AUTHORIZATION.json').exists(),'current scope contains no financial authorization'
    binding=manifest();prefix=H.score_prefix_proof();IO.write_json(O/'IMPORT_SCORE_PREFIX_PROOF.json',prefix)
    N.configure_scores(O/'SCORES_MANIFEST.json')
    t=time.monotonic();shared,receipts,cp,states,ir,identity=H.inputs();loaded=time.monotonic()-t
    frozen=H.source_freeze();IO.write_json(O/'HORIZON_SOURCE_FREEZE.json',dict(before_state_import=True,
        economic_events_authorized=False,sources=frozen,identity=identity))
    kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
    r=H.Continuation(shared,receipts,**kw);r.source_freeze=dict(frozen)
    proof=r.import_verified_parent();IO.write_json(O/'VERIFIED_HORIZON_IMPORT.json',proof)
    oldpath=P/'runs/2022/checkpoint.pkl';oldhash=H.sha(oldpath);oldprovhash=H.sha(oldpath.with_suffix('.provenance.json'))
    before=copy.deepcopy(snap(r));lookup=copy.deepcopy(r.episode_starts)
    inventory=r.next_event_inventory();first_open=next(x for x in inventory if x['opening'])
    assert first_open['at']=='2023-01-03 09:30:00+08:00'
    assert any(x['close'] and x['at']=='2023-01-03 15:10:00+08:00' for x in inventory)
    assert E.equal(before,snap(r)),'event inventory changed state'
    with IO.atomic_runner_outputs(r,L,root/'imported-Dec30',canonicalize=J.W.canon):r.checkpoint(root/'imported-Dec30',H.PARENT_AT)
    assert E.equal(before,snap(r)) and r.episode_starts==lookup
    # Actual new identity restore; no import or event is repeated.
    restored=H.Continuation(shared,receipts,**kw);restored.source_freeze=dict(frozen)
    with IO.atomic_runner_outputs(restored,L,root/'restart',canonicalize=J.W.canon):
        assert restored.restore(root/'imported-Dec30/checkpoint.pkl')==H.PARENT_AT
    assert E.equal(before,snap(restored)) and restored.episode_starts==lookup
    failures={}
    try:restored.import_verified_parent()
    except AssertionError as e:failures['duplicate_parent_import']=str(e)
    assert 'duplicate_parent_import' in failures and E.equal(before,snap(restored))
    # Single-use claim logic on an isolated metadata copy: no ledger method called.
    claim=copy.copy(restored);assert claim._claim_cursor(H.PARENT_AT)==H.PARENT_AT
    try:claim._claim_cursor(H.PARENT_AT)
    except AssertionError as e:failures['double_cursor_claim']=str(e)
    wrong=copy.copy(restored)
    try:wrong._claim_cursor(J.M.N.iso('2023-01-03T15:10:00+08:00'))
    except AssertionError as e:failures['skip_Jan3_or_wrong_cursor']=str(e)
    assert {'double_cursor_claim','skip_Jan3_or_wrong_cursor'}<=set(failures)
    assert E.equal(before,snap(restored)) and not restored._cursor_claimed
    # Genuine production entry guard rejects before ANY original event handler.
    try:restored.run_prepared(root/'FORBIDDEN-no-2023-events',1,resume_after=H.PARENT_AT,end='2023-01-03')
    except AssertionError as e:failures['finance_without_explicit_go']=str(e)
    assert 'finance_without_explicit_go' in failures and E.equal(before,snap(restored))
    # Source-data mismatch must reject even when constructor is given that binding.
    bad=copy.deepcopy(binding);bad['new_score_manifest_sha256']=H.OLD_SCORE_SHA
    badpath=root/'invalid-new-score-binding.json';IO.write_json(badpath,bad)
    virgin=H.Continuation(shared,receipts,binding=badpath,**kw);virgin.source_freeze=dict(frozen)
    virgin_before=copy.deepcopy(snap(virgin))
    try:virgin.import_verified_parent(badpath)
    except AssertionError as e:failures['incorrect_new_source_binding']=str(e)
    assert 'incorrect_new_source_binding' in failures and E.equal(virgin_before,snap(virgin))
    # Old SC checkpoint cannot be mistaken for the own-PVR parent.
    bad2=copy.deepcopy(binding);bad2['parent_checkpoint']=str((W/'2022-normal-reference-20261031/runs/B_diag/checkpoint.pkl').resolve())
    badpath2=root/'invalid-SC-parent-binding.json';IO.write_json(badpath2,bad2)
    shell=copy.copy(virgin);shell.horizon_binding_sha256=H.sha(badpath2)
    try:shell.import_verified_parent(badpath2)
    except AssertionError as e:failures['wrong_SC_parent']=str(e)
    assert 'wrong_SC_parent' in failures
    # Unchanged shared generation guard rejects a different runtime trading class.
    oldclass=N.Runner.__new__(N.Runner)
    try:
        with IO.atomic_runner_outputs(oldclass,L,root/'wrong-generation-class',canonicalize=J.W.canon):
            IO.assert_checkpoint_identity(oldclass,root/'imported-Dec30/checkpoint.pkl')
    except ValueError as e:failures['new_checkpoint_wrong_class']=str(e)
    assert 'new_checkpoint_wrong_class' in failures
    pending=r.accounts['B'].pending
    parent=pickle.loads(oldpath.read_bytes())
    assert E.equal(pending,parent['accounts']['B']['pending'])
    keys=[{k:i[k] for k in ['sid','role','rank','original_H1_rank','priority_rank','score','budget','cap','floor','CP1_id']} for i in pending]
    assert len(keys)==79 and all(i['rank']==i['priority_rank'] for i in keys)
    result=dict(passed=True,scope='state/data/import preflight only; no2023account event',account_events=0,
       all_account_fields_restored_exact=len(proof['all_account_fields_equal']),
       all_old_strategy_fields_exact=len(proof['all_strategy_fields_equal']),all5_old_event_streams_exact=True,
       parent_checkpoint_provenance_verified_under_original_class=True,new_checkpoint_own_generation_identity=True,
       old2022_score_prefix=prefix,episode_lookup_old=proof['transition']['pure_lookup_old'],
       episode_lookup_new=proof['transition']['pure_lookup_new'],future_lookup_entries=proof['transition']['future_entries'],
       original79_pending_intents_and_frozen_keys_exact=keys,
       event_inventory_without_execution=inventory,payments_and_actions_state_preserved=True,
       payments_clock='original _payments/settle_due at original event instants; no new payment-only clock',
       actual_new_firstday_physical_prefix_not_run=True,negative_guards=failures,
       single_use_import_and_cursor_claim_tested=True,restored_full_state_exact=True,
       initial_NAV=str(r.accounts['B'].current_nav),held_stocks=len(r.accounts['B'].positions),
       source_native_adapter_sha256=H.sha(N.__file__),horizon_import_sha256=H.sha(H.__file__),
       authorized_binding_sha256=H.sha(H.DEFAULT_BINDING),source_freeze=frozen,
       old_files_unchanged=H.sha(oldpath)==oldhash and H.sha(oldpath.with_suffix('.provenance.json'))==oldprovhash,
       seconds=dict(input_load=loaded,total=time.monotonic()-begun),
       next_financial_scope_if_authorized='ONE PVR_SLOT1 2023 continuation; savedSC2023 reused, no reset/other variant')
    assert result['old_files_unchanged'] and H.source_freeze()==frozen
    IO.write_json(O/'IMPORT_PREFLIGHT_GATE.json',J.W.canon(result))
    print('IMPORT_PREFLIGHT_PASS',result['all_account_fields_restored_exact'],result['all_old_strategy_fields_exact'],
          'pending',len(keys),'events0',round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        IO.write_json(O/'import-preflight/failure/ERROR.json',dict(type=type(e).__name__,reason=str(e),account_events=0));raise
