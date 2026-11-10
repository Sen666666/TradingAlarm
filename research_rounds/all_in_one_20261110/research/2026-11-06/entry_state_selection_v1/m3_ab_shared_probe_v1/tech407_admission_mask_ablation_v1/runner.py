"""Two locked arms, each once after an independent hash-bound release. No retry mode."""
from pathlib import Path
import argparse,collections,contextlib,json,resource,signal,sys,time,traceback
import mask_bridge as M
E=M.E
import report_layers_v2 as L
HERE=Path(__file__).resolve().parent

def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str,allow_nan=True);f.write('\n')
def read(p):return json.loads(Path(p).read_text())
def rss():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
def guard(start,c):
    elapsed=time.monotonic()-start;peak=rss()
    if elapsed>=c['wall_seconds'] or peak>=c['peak_rss_bytes']:raise RuntimeError('RESOURCE_BUDGET_EXCEEDED')
    return dict(elapsed_seconds=elapsed,peak_rss_bytes=peak,wall_limit_seconds=c['wall_seconds'],rss_limit_bytes=c['peak_rss_bytes'],resource_pass=True)
def semantic_payloads(s,b,daily):
    return {'ACTIONS':s.actions,'DECISIONS':s.decisions,'RANKING_AUDIT':s.ranking_audit,'AUDIT':b.audit,
        'DAY_LEDGER':daily,'ARCHIVES':s.archives,'STATES':b.states,'LAYERS':[E.asdict(x) for x in b.layers],
        'CLAIMS':list(s.claims.values()),'REGISTRATIONS':s.registrations,'CLAIM_LEDGER':s.claim_ledger,
        'EQUITY_BRIDGES':s.bridges,'PROFIT_GATES':s.marks,'ROUND_ND':b.caps,'SOURCE_ROUNDS':s.rounds,
        'SOURCE_HASHES':M.merge_hashes(s.hashes,b.source_hashes),
        'INTENTIONS':{sid:st for sid,st in b.states.items() if st['state']=='BUY_PENDING'},
        'ORDER_STATUS':[{k:o[k] for k in ('order_id','round_id','sid','kind','q','fee','risk','pool','status')} for o in b.orders.values()]}
def verify_frozen(freeze):
    for section in ('code_hashes','fixed_file_hashes','engineering_QA_hashes'):
        for p,h in freeze[section].items():assert E.bridge.sha(p)==h,('FROZEN_DRIFT',p)

    for p in freeze['absent_action_files']:assert not Path(p).exists(),('PREVIOUSLY_MISSING_INPUT_CREATED',p)

def run(arm):
    assert sys.platform=='darwin'
    contract=read(HERE/'RUN_CONTRACT.json');freeze=read(HERE/'FROZEN_INPUTS.json');release=read(HERE/'INDEPENDENT_REVIEW_RELEASE.json')
    assert release['result']=='PASS_PRE_RUN_ENGINEERING_ONLY'
    assert release['contract_sha256']==E.bridge.sha(HERE/'RUN_CONTRACT.json')
    assert release['freeze_sha256']==E.bridge.sha(HERE/'FROZEN_INPUTS.json')
    assert release['arms']==['all1709','tech407']
    verify_frozen(freeze)
    if arm=='tech407':
        # A failed baseline does not authorize the second economic arm.
        prior=read(HERE/'run_all1709_once/RUN_STATUS.json')
        assert prior['status']=='COMPLETED_RESOURCE_PASS'
        assert read(HERE/'BASELINE_EXACT_EQUIVALENCE.json')['all_match'] is True
    lock=HERE/(arm+'.ONCE.lock')
    save(lock,dict(arm=arm,started_utc=time.time(),contract_sha256=release['contract_sha256'],freeze_sha256=release['freeze_sha256'],retry_allowed=False))
    out=HERE/('run_'+arm+'_once');out.mkdir(exist_ok=False)
    start=time.monotonic();s=None;b=None;daily=[];phase='LOAD';last=None;first_uncertified=None;summary=None
    def alarm(sig,frame):raise TimeoutError('WALL_BUDGET_EXCEEDED_HARD_ALARM')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,contract['wall_seconds'])
    def artifacts():
        if b is None:return
        for name,value in semantic_payloads(s,b,daily).items():
            if not (out/(name+'.json')).exists():save(out/(name+'.json'),value)
        for name,value in [('MASK_AUDIT',getattr(b,'mask_audit',[])),('OPEN_MASK_AUDIT',getattr(b,'open_mask_audit',[]))]:
            if not (out/(name+'.json')).exists():save(out/(name+'.json'),value)
    try:
        save(out/'STARTED.json',dict(arm=arm,contract=contract,started_utc=time.time(),release=release))
        with (out/'execution.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            s=E.bridge.load_original('2024_924');b=M.make_bridge(s,arm)
            assert len(s.manifest)==1709 and len(s.EVENTS)==165
            assert len(s.ev)==6878 and s.ev.window.eq('2024_924').all()
            assert set(M.members())<=set(s.manifest)
            event_signature=E.hashlib.sha256(s.ev.to_json(date_format='iso').encode()).hexdigest()
            source_groups={d:tuple(g.event_id) for d,g in b.groups.items()}
            end=s.pd.Timestamp(contract['end']);days=s.cal[(s.cal>=s.pd.Timestamp(contract['start']))&(s.cal<=end)]
            assert len(days)==439 and str(days[0].date())==contract['first_common_day']
            assert s.ev.day.max()<=s.pd.Timestamp(contract['birth_end'])
            for n,day in enumerate(days):
                t=time.monotonic();phase='OPEN' if n else 'INITIAL_CLOSE'
                if n:
                    result=b.open_phase(day);openrow=result['reconciliation'];del result
                else:openrow=None
                phase='CLOSE';closerow=b.close_phase(day)
                daily.append(dict(day=day,OPEN=openrow,CLOSE=closerow,seconds=time.monotonic()-t,actions=len(s.actions),archives=len(s.archives),audit_rows=len(b.audit),peak_rss_bytes=rss()))
                last=day
                if first_uncertified is None and (not closerow['certified'] or openrow is not None and not openrow['certified']):
                    first_uncertified=dict(day=day,OPEN=openrow,CLOSE=closerow)
                    print('FIRST_UNCERTIFIED',json.dumps(first_uncertified,default=str),flush=True)
                if n%25==0 or n==len(days)-1:print('DAY',arm,str(day.date()),n+1,len(days),len(s.actions),'NAV',closerow['NAV'],'seconds',time.monotonic()-start,'rss',rss(),flush=True)
                guard(start,contract)
            phase='TERMINAL_REPORT'
            for sid,st in b.states.items():
                if st['state']=='HELD':s.record(st,'OPEN_CENSORED_AT_2026_06_30',end)
                elif st['state']=='BUY_PENDING':s.record(st,'BUY_PENDING_CENSORED_AT_DATA_END',end)
            s.finalize();reports=L.reports(b,end)
            for name,value in [('ROUND_REPORT',reports['rounds']),('LAYER_REPORT',reports['layers']),('EXACT_TRADE_JOURNAL',reports['exact_trade_journal'])]:save(out/(name+'.json'),value)
            artifacts()
            assert E.hashlib.sha256(s.ev.to_json(date_format='iso').encode()).hexdigest()==event_signature
            assert {d:tuple(g.event_id) for d,g in b.groups.items()}==source_groups
            if arm=='tech407':assert all(a['sid'] in b.admission_members for a in s.actions if a['side']=='buy_core')
            consumed=M.merge_hashes(s.hashes,b.source_hashes)
            for p,h in consumed.items():
                assert E.bridge.sha(p)==h,('CONSUMED_SOURCE_DRIFT',p)
                assert freeze['potential_input_hashes'].get(p,freeze['fixed_file_hashes'].get(p,freeze['code_hashes'].get(p)))==h,('UNFROZEN_CONSUMED_INPUT',p)
            verify_frozen(freeze)
            guard(start,contract)
            summary=dict(status='ECONOMIC_COMPLETED_PENDING_FINAL_RESOURCE_CHECK',arm=arm,days=len(days),last_complete=last,
                action_counts=dict(collections.Counter(a['side'] for a in s.actions)),actions=len(s.actions),archive_rounds=len(s.archives),
                promotions=sum(a['type']=='PROMOTED' for a in b.audit),claims=len(s.claims),settled_claims=sum(c['settled'] for c in s.claims.values()),equity_bridges=len(s.bridges),
                first_uncertified=first_uncertified,final_reconciliation=daily[-1]['CLOSE'],reports=reports['counts'],complete_certified_NAV_path=first_uncertified is None,
                source_event_rows=len(s.ev),source_members=len(s.manifest),original_2024_equity_events=len(s.EVENTS),source_event_signature=event_signature,
                conditional_proxy_only=True,continuous_all_market_strategy=False)
            save(out/'RESULT.json',summary)
        phase='OUTPUT_SEAL'
        save(out/'OUTPUT_SEAL.json',{p.name:E.bridge.sha(p) for p in out.iterdir() if p.is_file()})
        for name,h in read(out/'OUTPUT_SEAL.json').items():assert E.bridge.sha(out/name)==h
        resources=guard(start,contract);save(out/'FINAL_RESOURCE_QA.json',dict(resources,stage='AFTER_REPORT_EXPORT_SEAL_AND_SEAL_VERIFY',darwin_ru_maxrss_bytes=True))
        resources=guard(start,contract);save(out/'RUN_STATUS.json',dict(status='COMPLETED_RESOURCE_PASS',**resources,output_seal_sha256=E.bridge.sha(out/'OUTPUT_SEAL.json'),final_resource_sha256=E.bridge.sha(out/'FINAL_RESOURCE_QA.json')))
        guard(start,contract)
        print('COMPLETED',arm,json.dumps(summary,default=str));signal.setitimer(signal.ITIMER_REAL,0)
    except BaseException as err:
        signal.setitimer(signal.ITIMER_REAL,0)
        # Failed outputs and permanent lock are kept, never rewritten or retried.
        artifact_error=None
        try:artifacts()
        except BaseException as export_err:artifact_error=repr(export_err)
        failure=dict(status='FAILED_NO_RETRY',phase=phase,last_complete=last,error=repr(err),traceback=traceback.format_exc(),artifact_error=artifact_error,elapsed_seconds=time.monotonic()-start,peak_rss_bytes=rss(),first_uncertified=first_uncertified)
        save(out/'FAILURE.json',failure)
        if not (out/'RUN_STATUS.json').exists():save(out/'RUN_STATUS.json',failure)
        else:save(out/'POST_STATUS_FAILURE.json',failure)
        raise
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('arm',choices=['all1709','tech407']);run(a.parse_args().arm)
