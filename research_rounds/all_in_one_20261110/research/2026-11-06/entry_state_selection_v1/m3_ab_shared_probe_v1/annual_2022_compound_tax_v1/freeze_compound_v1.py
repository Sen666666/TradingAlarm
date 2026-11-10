"""Create one exact independently reviewable final bundle. Never release or run economics."""
from pathlib import Path
import json,hashlib,sys,pickle,time,platform,importlib.metadata
import compound_bridge_v1 as E
import run_compound_annual_v1 as RUN
P=Path(__file__).resolve().parent;B=P.parent
def read(p):return json.loads(Path(p).read_text())
def save(name,x):RUN.save(P,name,x)
def verify_output(root):
    sealed=read(root/'OUTPUT_SEAL.json')
    for relative,h in sealed.items():
        if E.sha(root/relative)!=h:raise ValueError('QA output drift '+str(root/relative))
def main():
    final=P/sys.argv[1];assert final.name=='qa_bounded_additional_02'
    prefix=P/'qa_attempt_02';meta=P/'qa_checkpoint_metadata_01'
    for path in (prefix,final,meta):verify_output(path)
    pr=read(prefix/'RESULT.json');fr=read(final/'RESULT.json');mr=read(meta/'RESULT.json')
    assert pr['status']=='AUTHOR_QA_PASS_PENDING_INDEPENDENT_REVIEW' and pr['prefix_phases']==221 and pr['prefix_actions']==253
    assert fr['status']=='AUTHOR_BOUNDED_ADDITIONAL_QA_PASS_PENDING_INDEPENDENT_REVIEW'
    assert fr['maximum_combined_peak_rss_bytes']<6*1024**3 and fr['elapsed_seconds']<900
    assert mr['status']=='PASS_SUPPLEMENTAL_METADATA_ONLY'
    assert not (P/'ECONOMIC_RUN_ONCE.lock').exists() and not (P/'economic_run_2022_compound_once').exists()
    bundle,policy,facthashes=E.verify_fixed_facts()
    oldroot=B/'annual_2022_marked_nav_v1';old=read(oldroot/'RUN_CONTRACT.json')
    assert platform.python_version()==old['python_version']
    assert all(importlib.metadata.version(k)==v for k,v in old['packages'].items())
    protected=read(oldroot/'PROTECTED_OLD_INPUTS.json')
    for name in ('annual_2022_marked_nav_v1','composite_equity_interface_v1','composite_equity_recovery_design_v1'):
        protected=E.merge_hashes(protected,{str(p):E.sha(p) for p in (B/name).rglob('*') if p.is_file()})
    deps=E.merge_hashes(old['dependencies'],protected,read(prefix/'SOURCE_HASHES.json'),facthashes)
    for phase in ('layers','pre','post'):
        deps=E.merge_hashes(deps,read(final/phase/'SOURCE_HASHES.json'))
    for name in ('annual_2022_marked_nav_v1','known_evidence_union_diagnostic_v1','known_halt_contract_v1',
       'known_halt_dividend_candidate_v1','indexed_execution_v1','source_bridge_v1','shared_feasibility_v1',
       'execution_bridge_v1','composite_equity_interface_v1'):
        deps=E.merge_hashes(deps,{str(p):E.sha(p) for p in (B/name).glob('*.py')})
    for p,h in deps.items():assert E.sha(p)==h,('Dependency drift',p)
    save('PROTECTED_PREVIOUS_INPUTS.json',protected)
    # Original fee rows are copied byte-for-byte, not reconstructed or repriced.
    fee=(oldroot/'FROZEN_2022_FEE_SCHEDULES.json').read_bytes()
    p=P/'FROZEN_2022_FEE_SCHEDULES.json';assert not p.exists();p.write_bytes(fee)
    contract={k:v for k,v in old.items() if k not in ('dependencies','source_engine_unchanged')}
    contract.update(version='ANNUAL_2022_COMPOUND_PAR20_V1',scope=RUN.SCOPE,
      financial_contract='Original signals, selection, budgets, actual trading fees and cash NET80 unchanged; new explicit same-day share accounting and nonrefundable par20 stock research expense alter the conditional account path.',
      original_source_files_unchanged=True,runtime_consumer_contract_extended=True,
      old_event_domain_count=437,additional_pure_cash=4,additional_compound=1,maximum_distinct_event_count=442,
      old_registry_and_coordinate_only_permissions_unchanged=True,
      additional_event_ids=[x['economic_event_id'] for x in bundle['new_pure_cash']+bundle['new_compound']],
      compound_cash_is_same_event_not_duplicate_443=True,
      entitlement_rule='Old437 retained; four independently reviewed cash events and one same-ex-day integer capitalization event admitted only after their exact public clocks. Unsupported responsibility remains UNKNOWN.',
      research_stock_cost_policy=policy,accounting_contract=read(P/'ACCOUNTING_CONTRACT_DRAFT.json'),
      nominal_risk_scope='Research debit affects available cash, wallet NAV, later freshly frozen budgets and native cash profitability gates. Original ADD existing-risk/probe price-gap numerators and already frozen round Nd are unchanged. Nominal limits do not guarantee total losses including all research tax.',
      reporting_NAV='cash after exactly once owner-round research debit + gross raw CLOSE inventory + recognized receivables; original proved-halt carry only, no hypothetical selling fee.',
      reporting_addback='If shown, cumulative research cost addback is on the SAME realized conditional path only; it is not an unadjusted strategy counterfactual.',
      win_rates='Closed execution-and-settlement rounds/layers only at stated end/phase. Values now include cash NET80 and par20 stock research cost, not real investor tax. Open denominators separate.',
      prefix_equivalence={'through':'2022-06-22 CLOSE','phases':221,'actions':253,
         'method':'Direct all original economic field and action comparisons, not runtime-hash substitution; time/RSS excluded.',
         'new_fact_registration_audit_separate':True,'first_permitted_economic_change':'2022-06-23 OPEN'},
      fixed_fixture='000987 actual old300/new105/total405, raw OPEN6.70, cash NET80 receivable48, explicit stock research cost21. Forced exit variants are synthetic intent only, not strategy results.',
      checkpoint_contract='Exact original source reload and new adapter constructor rebuild bound functions; pickle contains state/data, not bound methods. Restore compound registrations, share/tax ledger and applied set, preserve archive/state identity. Separate-process pre/post tests reject double issue/tax/pay.',
      digest_contract='Streamed typed-v1 JSON hash is byte-identical to original tree digest. It is not the economic-prefix comparator. Supplemental pinned pickle5/pandas metadata fingerprint covers axis names, dtype, timezone, labels, values and attrs omitted by legacy typed-v1.',
      fact_audit='PASS_FACTS_ONLY receipt transcribed from independent reviewer, three evidence seals/all82 members verified. Not actual-tax or strategy/PIT certification.',
      par_scope='Historical CNY1 face value from April2 2022-published 2021 audit, not exhaustive subsequent amendment or 2022 exemption proof. par20 is explicitly approved research proxy.',
      qa_resource_history='First combined-fixture process passed logical assertions but exceeded6GiB; retained as resource failure. Final sequential isolated tests retained assertions, full source reloads, no shared state/cache and strict combined900s/6GiB.',
      dependencies=deps)
    assert (contract['wall_seconds'],contract['peak_rss_bytes'],contract['phase_stop_seconds'],contract['phase_stop_rss_bytes'])==(900,6*1024**3,780,5*1024**3)
    save('RUN_CONTRACT.json',contract)
    # Exercise the exact nonempty source maps from actual original-prefix checkpoint.
    sys.path.insert(0,'/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code')
    import sector_account
    with (prefix/'PREFIX_CHECKPOINT.pkl').open('rb') as f:runtime=pickle.load(f)
    source=runtime['union']['source_data_hashes'];adapter=runtime['union']['source_hashes']
    overlap=set(adapter)&set(deps);assert overlap
    try:dict(source,**adapter,**deps)
    except TypeError as err:old_error=repr(err)
    else:raise AssertionError('Original real-intersection duplicate failure not reproduced')
    merged=E.merge_hashes(source,adapter,deps)
    for p,h in merged.items():assert E.sha(p)==h,p
    key=next(iter(overlap))
    try:E.merge_hashes(adapter,{key:'0'*64})
    except ValueError:pass
    else:raise AssertionError('Conflicting dependency hash accepted')
    save('FINAL_ACTUAL_MERGE_CHECK.json',dict(actual_source_count=len(source),actual_adapter_count=len(adapter),
      final_contract_dependency_count=len(deps),actual_intersection_count=len(overlap),merged_count=len(merged),
      duplicate_expansion_reproduced=old_error,same_value_merge=True,conflicting_value_rejected=True))
    attempts=[]
    for path in sorted(P.glob('qa_*')):
        if not path.is_dir():continue
        if (path/'RESULT.json').exists():result=read(path/'RESULT.json')
        elif (path/'FAILURE.json').exists():result=read(path/'FAILURE.json')
        else:continue
        attempts.append(dict(name=path.name,result=result))
    save('ATTEMPT_HISTORY.json',dict(attempts=attempts,
      explicit_resource_failure=read(P/'QA_ADDITIONAL_01_RESOURCE_FAILURE.json'),
      changes=['qa_attempt_01 retained: Timestamp-key JSON digest failed before first Jan4 phase completed.',
       'qa_attempt_02: all221 original economic phases/253 actions match, fixed000987 accounting and atomic failure cases pass.',
       'Report-only net-pnl-basis labels added; affected report paths retested in final bounded layer fixtures.',
       'Typed digest replaced by exact-streamed same JSON; actual checkpoint/reference equivalence separately proved.',
       'Real commit rederives exact admitted tax/event plan; self-rehashed altered expense negative passes.',
       'Final isolated worker processes restore the same assertions below unchanged resource limits.'],
      new_annual_economic_runs=0))
    save('AUTHOR_PRE_RUN_READOUT.json',dict(status='AUTHOR_READY_PENDING_INDEPENDENT_REVIEW',
      prefix=pr,final_bounded_QA=fr,supplemental_metadata_QA={'status':mr['status'],'negative_cases':mr['mutation_negatives'],'peak_rss_bytes':mr['peak_rss_bytes']},
      fixed_000987=read(prefix/'FIXED_000987_EX_OPEN.json'),
      dependencies=len(deps),protected_previous_files=len(protected),reviewed_fact_members=82,
      maximum_candidate_event_domain=442,final_actual_merge=read(P/'FINAL_ACTUAL_MERGE_CHECK.json'),
      independent_review_needed=['Old437 invariance and new five known-at clocks without future-factor injection',
        'Atomic actual cash/quantity/claim/tax state and exact single global cash effect',
        'Nonrefundable research expense vs actual fees and unchanged nominal risk/frozenNd',
        'Issued shares cost/identity/odd-quantity rules, active and closed ADD ownership/report isolation',
        '221/253 original economic prefix and fixed source fixture scope',
        'Separate-process checkpoint reconstruction and no replayed issue/tax/pay',
        'Year-end censoring/closed denominators/gross inventory vs same-path addback and hypothetical liquidation',
        'Final real dependency intersection and original post-export/post-seal 900s/6GiB gates'],
      economic_release_exists=False,new_annual_economic_runs=0,created_utc=time.time()))
    save('PRE_RUN_STATUS.json',dict(status='FROZEN_PENDING_INDEPENDENT_REVIEW',economic_run_started=False,
      old_failure_and_resource_notes_retained=True,not_a_full_2022_result=True))
    files=[p for p in P.rglob('*') if p.is_file() and p not in (P/'PRE_RUN_STAGE_SEAL.json', P/'INDEPENDENT_REVIEW_RELEASE.json')]
    save('PRE_RUN_STAGE_SEAL.json',{str(p.relative_to(P)):E.sha(p) for p in sorted(files)})
    print(json.dumps(dict(stage_sha256=E.sha(P/'PRE_RUN_STAGE_SEAL.json'),stage_files=len(files),
      dependencies=len(deps),protected_previous_files=len(protected),prefix_phases=221,prefix_actions=253,
      final_combined_QA_peak=fr['maximum_combined_peak_rss_bytes'],new_annual_economic_runs=0),indent=2))
if __name__=='__main__':main()
