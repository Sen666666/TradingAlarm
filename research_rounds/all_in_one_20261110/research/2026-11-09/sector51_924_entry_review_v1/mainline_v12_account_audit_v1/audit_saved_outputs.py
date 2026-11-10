"""M12 independent saved-output audit. Never imports strategy/Data or runs history."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
import argparse, ast, importlib.util, json, sys
sys.dont_write_bytecode=True
import accounting_core as au
O=Path(__file__).resolve().parent;R=O.parent;BASE=au.BASE;END='2025-01-20';Z=D(0)
read=au.read;sha=au.sha;save=au.save;near=au.near;sm=au.sm
ADDENDUM=R/'mainline_winner_funding_design_v1/EXECUTION_FREEZE_ADDENDUM.md'
FIELDS=R/'mainline_winner_funding_design_v1/EXECUTION_FREEZE_FIELDS.json'
PINNED={str(ADDENDUM):'3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1',str(FIELDS):'d038f72c0d15a9d62ab954365f22eb6ed5fb5f1176c09bbaad45a71639f4c77e',str(au.HELPER):'928c7af9608badf81285d41bdad1bc85d9998cbb0779673ec025c8ebb0cf3339'}
def prepare():
    for p,h in PINNED.items():assert sha(p)==h,('pinned_source',p)
    provenance=read(O/'CORE_PROVENANCE.json');assert sha(provenance['source'])==provenance['source_sha256']
    tree=ast.parse(au.HELPER.read_text())
    assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) and ('engine' in ast.unparse(n) or 'Data' in ast.unparse(n)) for n in ast.walk(tree))
    spec=importlib.util.spec_from_file_location('reviewed_pure_saved_accounting_helper',au.HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    hashes=au.verify_hashes(BASE)
    for n,h in read(au.TAIL/'OUTPUT_SEAL.json').items():assert sha(au.TAIL/n)==h,('fixed_cohort_output',n)
    for p,h in read(au.TAIL/'SOURCE_HASHES.json').items():assert sha(p)==h,('fixed_cohort_source',p)
    b,br=au.account(BASE,END,helper)
    assert b['days']==93 and b['trading']['orders']==3596 and len(br)==1677
    near(b['NAV'],'1275326.0427500672225','fixed_M7_end_NAV')
    fixed={x['opportunity_key']:x for x in read(au.TAIL/'ALL_OPPORTUNITIES.json')}
    for x in br:near(x['marked_net_pnl'],fixed[x['opportunity_key']]['marked_net_pnl'],('fixed_M7_identity',x['opportunity_key']))
    return helper,b,br,hashes
def states(path):
    """Identity-only lifecycle read; no G/F-or-CP gate imported."""
    out=defaultdict(lambda:dict(events=[]));tickets=read(path/'TICKET_STATE.json')
    for x in read(path/'RETRY_TICKETS.json'):
        sd=x.get('original_signal_day')
        if sd:out[x['sid']+'|'+sd]['events'].append(x)
    for x in tickets.values():
        k=x['sid']+'|'+x['signal_day'];out[k].update(status=x['status'],terminal_reason=x.get('reason'),ticket_id=x['ticket_id'],final_ticket=x)
    for name in ('FUNDING_WAIT.json','FUNDING_WAITS.json','FUNDING_WAIT_LOG.json'):
        if not (path/name).exists():continue
        for x in read(path/name):
            sd=x.get('original_signal_day',x.get('signal_day'))
            if sd:out[x['sid']+'|'+sd].setdefault('funding_wait',[]).append(x)
    for k,v in out.items():v.setdefault('status','LIFECYCLE_LOG_ONLY')
    return dict(out)
def check_run(candidate,status_path):
    status=read(status_path);ls=read(candidate/'DAY_LEDGER.json')
    assert status['result']=='COMPLETED' and status['days']==93 and len(ls)==93
    assert ls[0]['day']=='2024-09-02' and ls[-1]['day']==END
    assert not status.get('blockers') and status.get('atomic_block') is None and status.get('runtime_error') is None
    if 'last' in status:assert status['last']==ls[-1]
    if 'orders' in status:assert status['orders']==len(read(candidate/'ORDERS.json'))
    parent=candidate.parent;details=dict(run_status=status,status_sha256=sha(status_path),candidate=str(candidate),day_count=93,end=END)
    for name in ('RUN_STARTED.json','EXPERIMENT_APPROVAL.json','FROZEN_INPUTS.json','SYNTHETIC_QA.json','INPUT_TYPE_QA.json'):
        p=parent/name
        if p.exists():details[name]=dict(path=str(p),sha256=sha(p))
    frozen=parent/'FROZEN_INPUTS.json'
    if frozen.exists():
        f=read(frozen)
        if 'hashes' in f:assert f['hashes']==read(candidate/'SOURCE_HASHES.json'), 'run_sources_not_frozen'
        for p,h in f.get('code_hashes',{}).items():assert sha(p)==h,('frozen_code_changed',p)
    approval=parent/'EXPERIMENT_APPROVAL.json'
    if approval.exists():
        a=read(approval)
        assert a.get('approved') and a.get('one_shot') and a.get('end')==END
        for p,h in a.get('code_hashes',{}).items():assert sha(p)==h,('approved_code_changed',p)
    details['coverage']='Saved output and declared run-source binding; runner temporal/source behavior needs independent static review.'
    save('RUNNER_FREEZE_REVIEW',details)
    return status
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prepare-baseline',action='store_true')
    ap.add_argument('--candidate',type=Path)
    ap.add_argument('--run-status',type=Path)
    ap.add_argument('--semantics',type=Path,help='Independent saved-semantic result, never candidate self-report')
    args=ap.parse_args()
    assert args.prepare_baseline or (args.candidate and args.run_status),'Explicit completed saved output and status required'
    helper,b,br,bhash=prepare()
    prep=dict(verdict='PASS_BASELINE_SAVED_ACCOUNTING',baseline=str(BASE),baseline_hashes=bhash,summary=b,fixed_round_count=len(br),source_hashes=PINNED,audit_source_sha256=sha(__file__),history_executed=False,strategy_imported=False,candidate_executed=False)
    if args.prepare_baseline:
        save('PREPARATION_BASELINE_CHECK',prep);print(json.dumps(dict(verdict=prep['verdict'],days=b['days'],NAV=b['NAV'],orders=b['trading']['orders'],rounds=len(br)),default=str));return
    path=args.candidate.resolve()
    assert path!=BASE and path.parent.name=='mainline_candidate_v12_winner_funding_competition','Only exact M12 candidate allowed'
    status=check_run(path,args.run_status)
    chash=au.verify_hashes(path)
    baseline_sources=read(BASE/'SOURCE_HASHES.json');candidate_sources=read(path/'SOURCE_HASHES.json')
    for source,value in baseline_sources.items():assert candidate_sources.get(source)==value,('frozen_M7_input_or_dependency_changed',source)
    assert read(path/'EVENT_ADMISSION.json')==read(BASE/'EVENT_ADMISSION.json'),'admitted_cash_boundary_changed'
    a,ar=au.account(path,END,helper)
    assert [x['day'] for x in read(path/'DAY_LEDGER.json')]==[x['day'] for x in read(BASE/'DAY_LEDGER.json')]
    rows,cohorts,new,winners=au.compare(br,ar,END,states(path))
    delta={k:a[k]-b[k] for k in ('NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct')}
    for name,value in [('M7_COMMON_ROUNDS',br),('M12_ACTUAL_ROUNDS',ar),('FIXED_OPPORTUNITY_COMPARISON',rows),('FIXED_COHORT_SUMMARY',cohorts),('CANDIDATE_NEW_OPPORTUNITIES',new),('FIXED_WINNER_COMPARISON',winners),('CANDIDATE_OPEN_ROUNDS',[x for x in ar if x['open_at_cutoff']])]:save(name,value)
    review_path=R/'mainline_winner_funding_review_v1/V12_INDEPENDENT_INTERFACE_QA.json'
    static_review=read(review_path)
    assert static_review['result']=='PASS_FOR_ONE_FROZEN_OFFLINE_EXPERIMENT' and not static_review['remaining_blockers']
    assert static_review['engine_sha256']==sha(path.parent/'engine.py') and static_review['tests_sha256']==sha(path.parent/'synthetic_tests.py')
    assert static_review['source_manifest_sha256']==sha(path.parent/'SOURCE_HASHES.json')
    for p,h in read(path.parent/'SOURCE_HASHES.json')['files'].items():assert sha(p)==h,('independent_static_source_drift',p)
    static_evidence=dict(report=str(review_path),sha256=sha(review_path),engine_sha256=static_review['engine_sha256'],scope=static_review['scope'],not_certified=static_review['not_certified'])
    if args.semantics:
        assert args.semantics.resolve()==(O/'SAVED_FUNDING_SEMANTICS.json').resolve(),'only_independent_semantic_artifact'
        for n,h in read(args.semantics)['sources'].items():assert sha(path/n)==h,('semantic_output_binding',n)
    semantics=read(args.semantics) if args.semantics else dict(verdict='NOT_YET_AUDITED',coverage='Accounting alone does not certify selection/source semantics.')
    result=dict(verdict='PASS_SAVED_OUTPUT_ACCOUNTING',accounting_verdict='PASS',saved_semantics_verdict=semantics['verdict'],static_future_input_provenance_verdict='PASS_SOURCE_BOUND_STATIC_SELECTION_BOUNDARY_NOT_PIT',independent_static_evidence=static_evidence,common_end=END,full_target_completed=True,candidate_output=str(path),run_status=status,hashes={'M7':bhash,'M12':chash},M12=a,M7=b,delta=delta,cohorts=cohorts,new_opportunities=dict(count=len(new),actual_net=sm(new,'marked_net_pnl')),sources=PINNED,saved_semantics=semantics,limits=['Only original M7 is the strategy comparator; corrected V11 v2 is code-reuse provenance only.','Observed development window, not OOS, PIT or production proof.','Fixed baseline winners/losers are evaluation labels and never selection inputs.','Unfilled baseline losses are reference-only opportunity costs, not earned candidate profits.','Actual late account PnL is measured from its own Nov6 NAV, not merely terminal NAV difference.','Open rounds remain marked, not invented terminal sales.','Saved quantities and candidate health assertions cannot prove source timing; static review and poisoned-future-field tests must be separately source-bound.','Original full-day OHLC no_fill is an inherited modeling limitation. Conditional q/y guarantees do not guarantee actual matching outcomes.'])
    save('INDEPENDENT_M12_VS_M7',result)
    from analyze_actual_paths import analyze
    analyze(path,result,br,ar)
    save('AUDIT_SEAL',dict(audit_source_sha256=sha(__file__),helper_sha256=sha(au.HELPER),inputs=PINNED,outputs={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name not in ('AUDIT_SEAL.json','FINAL_AUDIT_SEAL.json')}))
    print(json.dumps(dict(verdict=result['verdict'],end=END,delta=delta,late=result['nov6_segment']),ensure_ascii=False,default=str))
if __name__=='__main__':main()
