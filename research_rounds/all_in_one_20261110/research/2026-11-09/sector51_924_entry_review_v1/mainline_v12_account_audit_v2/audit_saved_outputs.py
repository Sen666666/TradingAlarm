"""Explicit saved-v2 audit entry. No strategy imports, Data, history or pickle loads."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import argparse,ast,importlib.util,json,sys
sys.dont_write_bytecode=True
import accounting_core as au
import compression_integrity as compressed
import prefix_independent as prefix
import checkpoint_metadata as checkpoint
import audit_streamed_branches as branch_audit
from analyze_saved_paths import analyze
HOME=Path(__file__).resolve().parent;ROOT=HOME.parent
EXPECTED_ROOT=ROOT/'mainline_candidate_v12_winner_funding_cash_688200_v2'
V1=ROOT/'mainline_candidate_v12_winner_funding_competition/once_20250120'
HELPER_SHA='928c7af9608badf81285d41bdad1bc85d9998cbb0779673ec025c8ebb0cf3339'
EXTRA=('688200.SH','2024-10-11','688200.SH|LOCAL_DISTRIBUTION_007')
def read(p):return au.read(p)
def save(n,x):au.save(n,x)
def states(path):
    out=defaultdict(lambda:dict(events=[]))
    for x in read(path/'RETRY_TICKETS.json'):
        sd=x.get('original_signal_day')
        if sd:out[x['sid']+'|'+sd]['events'].append(x)
    for x in read(path/'TICKET_STATE.json').values():out[x['sid']+'|'+x['signal_day']].update(status=x['status'],ticket_id=x['ticket_id'],final_ticket=x)
    for x in read(path/'FUNDING_WAIT_LOG.json'):
        r=x['original_request'];out[r['sid']+'|'+r['signal_day']].setdefault('funding_wait',[]).append(x)
    for x in out.values():x.setdefault('status','LIFECYCLE_LOG_ONLY')
    return dict(out)

def certified_frontier(status,ledger,base_calendar):
    assert status['result'] in ('COMPLETED','ATOMIC_BLOCK','CHECKPOINT_STOP'),'not_a_terminal_certified_saved_result'
    assert status.get('runtime_error') is None and not status.get('prefix_error')
    assert ledger and status['last']==ledger[-1] and status['days']==len(ledger)
    end=ledger[-1]['day'];assert '2024-09-02'<=end<='2025-01-20'
    assert [x['day'] for x in ledger]==[d for d in base_calendar if d<=end],'calendar_gap'
    if status['result']=='COMPLETED':assert end=='2025-01-20' and len(ledger)==93
    if status['result']=='ATOMIC_BLOCK':assert status['atomic_block']['atomic_rollback'] is True and status['atomic_block']['day']>end
    if status['result']=='CHECKPOINT_STOP':assert status['storage_error']['economic_day_certified'] is True and status['storage_error']['day']==end
    return end

def check_admission(candidate,end):
    old=read(V1/'EVENT_ADMISSION.json');new=read(candidate/'EVENT_ADMISSION.json')
    assert all(x in new for x in old),'prior_event_removed_or_changed'
    extra=[x for x in new if x not in old];assert len(new)==len(old)+1 and len(extra)==1
    x=extra[0];assert (x['sid'],x['ex_date'],x['event_id'])==EXTRA
    if end>='2024-10-10':
        assert not [h for h in read(candidate/'HOLDINGS.json') if h['sid']=='688200.SH' and h['day']=='2024-10-10']
    bridge=[]
    if end>='2024-10-11':
        bridge=[x for x in read(candidate/'EQUITY_EVENTS.json') if x['sid']=='688200.SH' and x['day']=='2024-10-11']
        assert len(bridge)==1 and bridge[0]['event']=='FACTOR_BRIDGE' and bridge[0]['record_qty']==0
        assert D(bridge[0]['cash_delta'])==D(bridge[0]['receivable_delta'])==0
    return dict(only_added_event=extra,zero_equity_bridge=bridge,record_holdings_zero=end>='2024-10-10')

def bind_frozen(candidate,status):
    parent=candidate.parent;approval=read(parent/'EXPERIMENT_APPROVAL.json');frozen=read(parent/'FROZEN_INPUTS.json')
    assert approval['approved'] is True and approval['one_shot'] is True and approval['end']=='2025-01-20'
    assert frozen['hashes']==read(candidate/'SOURCE_HASHES.json')
    assert approval['source_manifest_sha256']==au.sha(parent/'SOURCE_HASHES.json')
    for p,h in approval['code_and_qa_hashes'].items():assert au.sha(p)==h,('approved_source_drift',p)
    for p,h in read(parent/'SOURCE_HASHES.json')['files'].items():assert au.sha(p)==h,('manifest_source_drift',p)
    reviewpath=Path(approval['independent_review_path']);assert reviewpath.resolve().is_relative_to(ROOT/'mainline_winner_funding_review_v1')
    assert au.sha(reviewpath)==approval['independent_review_sha256']
    review=read(reviewpath);assert review['result']=='PASS_V12_CASH688200_CONTINUATION_INTERFACE' and not review['remaining_blockers']
    assert review['source_manifest_sha256']==approval['source_manifest_sha256']
    old=read(V1/'SOURCE_HASHES.json');new=read(candidate/'SOURCE_HASHES.json')
    for p,h in old.items():
        # Old run-specific approval/runner are provenance, not executable inputs of v2.
        if Path(p).parent==V1.parent and Path(p).name in ('run_approved_once.py','EXPERIMENT_APPROVAL.json'):continue
        assert new.get(p)==h or au.sha(p)==h,('old_input_drift',p)
    for p,h in read(au.BASE/'SOURCE_HASHES.json').items():assert new.get(p)==h,('original_M7_input_changed',p)
    return dict(review_path=str(reviewpath),review_sha256=au.sha(reviewpath),review_scope=review.get('scope'),source_manifest_sha256=approval['source_manifest_sha256'],source_timing_not_proved_by_saved_qy=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit-saved-output',action='store_true',required=True)
    ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--run-status',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();p=args.candidate.resolve()
    assert p.parent==EXPECTED_ROOT and p.name=='once_20250120','exact_v2_saved_output_only'
    assert args.run_status.resolve()==EXPECTED_ROOT/'RUN_STATUS.json'
    status=read(args.run_status);ledger=read(p/'DAY_LEDGER.json')
    end=certified_frontier(status,ledger,[x['day'] for x in read(au.BASE/'DAY_LEDGER.json')])
    assert status['orders']==len(read(p/'ORDERS.json'))
    assert not args.output.exists(),'new_independent_result_directory_required'
    args.output.mkdir(parents=True);out=args.output.resolve();au.O=out
    result=dict(verdict='AUDIT_IN_PROGRESS',certified_end=end,day_count=len(ledger),full_93_day_completed=end=='2025-01-20' and status['result']=='COMPLETED',run_status=status)
    save('AUDIT_STATUS',result)
    hashes=dict(candidate=au.verify_hashes(p),baseline=au.verify_hashes(au.BASE),v1=au.verify_hashes(V1))
    compression=compressed.verify(p/'FUNDING_BRANCH_BOOKS.json.gz',read(p/'COMPRESSED_OUTPUTS.json'),read(p/'OUTPUT_HASHES.json'))
    save('COMPRESSED_OUTPUT_AUDIT',compression)
    static=bind_frozen(p,status);admission=check_admission(p,end);save('EXACT_EVENT_ADMISSION_AUDIT',admission)
    oldprefix=prefix.audit(V1,p,end);save('V1_PREFIX_INDEPENDENT_AUDIT',oldprefix)
    assert au.sha(au.HELPER)==HELPER_SHA
    sp=importlib.util.spec_from_file_location('reviewed_saved_account_helper',au.HELPER);helper=importlib.util.module_from_spec(sp);sp.loader.exec_module(helper)
    a,ar=au.account(p,end,helper);b,br=au.account(au.BASE,end,helper)
    rows,cohorts,new,winners=au.compare(br,ar,end,states(p))
    for name,v in [('M12_ACTUAL_ROUNDS',ar),('M7_COMMON_ROUNDS',br),('FIXED_OPPORTUNITY_COMPARISON',rows),('FIXED_COHORT_SUMMARY',cohorts),('CANDIDATE_NEW_OPPORTUNITIES',new),('FIXED_WINNER_COMPARISON',winners)]:save(name,v)
    delta={k:a[k]-b[k] for k in ('NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct')}
    delta['fees']=a['trading']['fees']-b['trading']['fees']
    result.update(M12=a,M7=b,delta=delta,cohorts=cohorts,hashes=hashes,static_binding=static)
    result=analyze(p,end,out,result,br,ar)
    save('ACCOUNT_ECONOMICS_BEFORE_BRANCHES',result)
    branch_audit.main(p,out);sem=read(out/'SAVED_FUNDING_SEMANTICS.json')
    assert sem['verdict']=='PASS_ALL_CERTIFIED_SAVED_BRANCH_SEMANTICS' and not sem['issues']
    receipt=status.get('latest_checkpoint');cpqa=dict(verdict='NO_CHECKPOINT_RECEIPT',pickle_opened=False)
    if receipt:
        log=EXPECTED_ROOT/'CHECKPOINT_RECEIPTS.jsonl'
        external=[json.loads(line) for line in log.read_text().splitlines() if line.strip()]
        assert any(x['receipt_sha256']==receipt['receipt_sha256'] and x['path']==receipt['path'] for x in external),'checkpoint_not_in_external_receipt_log'
        cpqa=checkpoint.audit(receipt['path'],receipt['receipt_sha256'],EXPECTED_ROOT,end)
    save('CHECKPOINT_METADATA_AUDIT',cpqa)
    result.update(verdict='PASS_CERTIFIED_ACCOUNTING_PREFIX_AND_SAVED_BRANCHES',saved_semantics=sem,checkpoint_metadata=cpqa,limits=['Same-window actual results only. Fixed original winner labels are retrospective evaluation labels, never entry information.','No strategy/Data/history or pickle loading in this auditor.','Saved assertions do not establish PIT or source timing; source-bound independent static review remains separate.','Open-round marks and hypothetical liquidation are not realized trades or guaranteed protection.'])
    save('INDEPENDENT_M12_V2_VS_M7',result)
    save('AUDIT_SEAL',dict(engine_sha256=au.sha(EXPECTED_ROOT/'engine.py'),audit_sources={x.name:au.sha(x) for x in HOME.glob('*.py')},output_files={x.name:au.sha(x) for x in out.iterdir() if x.is_file() and x.name!='AUDIT_SEAL.json'}))
    print(json.dumps(dict(verdict=result['verdict'],end=end,days=len(ledger),NAV_delta=delta['NAV'],output=str(out)),default=str))
if __name__=='__main__':main()
