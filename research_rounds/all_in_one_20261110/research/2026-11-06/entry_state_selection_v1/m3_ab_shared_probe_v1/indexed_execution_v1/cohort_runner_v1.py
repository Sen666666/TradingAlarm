"""Single authorized birth-cohort run. No parameters or dates selected from outcomes."""
from pathlib import Path
import sys,json,time,resource,traceback,contextlib,collections
import engine_indexed_v1 as E
import report_layers_v1
HERE=Path(__file__).resolve().parent
CONTRACT=json.loads((HERE/'COHORT_EXECUTION_CONTRACT.json').read_text())
def save(path,value):
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def rss():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
def run():
    window=sys.argv[1];cfg=CONTRACT['cohorts'][window];out=HERE/('cohort_'+window);out.mkdir(exist_ok=False)
    hashes=CONTRACT['code_hashes']
    for p,h in hashes.items():assert E.bridge.sha(p)==h
    save(out/'STARTED.json',dict(contract=CONTRACT,window=window,started_utc=time.time()))
    started=time.monotonic();b=None;s=None;daily=[];last_complete=None;first_uncertified=None;phase='LOAD'
    def artifacts():
        if b is None:return
        payloads={'ACTIONS':s.actions,'DECISIONS':s.decisions,'RANKING_AUDIT':s.ranking_audit,'AUDIT':b.audit,
            'DAY_LEDGER':daily,'ARCHIVES':s.archives,'STATES':b.states,'LAYERS':[E.asdict(x) for x in b.layers],
            'CLAIMS':list(s.claims.values()),'REGISTRATIONS':s.registrations,'CLAIM_LEDGER':s.claim_ledger,
            'EQUITY_BRIDGES':s.bridges,'PROFIT_GATES':s.marks,'ROUND_ND':b.caps,'SOURCE_ROUNDS':s.rounds,
            'SOURCE_HASHES':dict(s.hashes,**b.source_hashes),
            'INTENTIONS':{sid:st for sid,st in b.states.items() if st['state']=='BUY_PENDING'},
            'ORDER_STATUS':[{k:o[k] for k in ('order_id','round_id','sid','kind','q','fee','risk','pool','status')} for o in b.orders.values()]}
        for name,value in payloads.items():
            if not (out/(name+'.json')).exists():save(out/(name+'.json'),value)
    try:
        with (out/'execution.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            s=E.bridge.load_original(window);b=E.ExecutionBridge(s);end=s.pd.Timestamp(CONTRACT['end']);start=s.pd.Timestamp(cfg['start'])
            days=s.cal[(s.cal>=start)&(s.cal<=end)]
            assert str(days[0].date())==cfg['first_common_day']
            assert s.ev.window.eq(window).all() and s.ev.day.max()<=s.pd.Timestamp(cfg['birth_end'])
            for n,day in enumerate(days):
                t=time.monotonic();phase='OPEN' if n else 'INITIAL_CLOSE'
                if n:
                    result=b.open_phase(day);openrow=result['reconciliation'];del result
                else:openrow=None
                phase='CLOSE';closerow=b.close_phase(day)
                entry=dict(day=day,OPEN=openrow,CLOSE=closerow,seconds=time.monotonic()-t,
                    actions=len(s.actions),archives=len(s.archives),audit_rows=len(b.audit),peak_rss_bytes=rss())
                daily.append(entry);last_complete=day
                if first_uncertified is None and (not closerow['certified'] or openrow is not None and not openrow['certified']):
                    first_uncertified=dict(day=day,OPEN=openrow,CLOSE=closerow)
                    print('FIRST_UNCERTIFIED',json.dumps(first_uncertified,default=str),flush=True)
                if n%25==0 or n==len(days)-1:
                    print('DAY',window,str(day.date()),'completed',n+1,'/',len(days),'actions',len(s.actions),'archives',len(s.archives),
                        'audit',len(b.audit),'elapsed',round(time.monotonic()-started,2),'rss_bytes',rss(),'NAV',closerow['NAV'],flush=True)
                if time.monotonic()-started>CONTRACT['wall_seconds'] or rss()>CONTRACT['peak_rss_bytes']:
                    raise RuntimeError('RESOURCE_BUDGET_EXCEEDED_AT_DETERMINISTIC_DAY_BOUNDARY')
            phase='TERMINAL_REPORT'
            for sid,st in b.states.items():
                if st['state']=='HELD':s.record(st,'OPEN_CENSORED_AT_2026_06_30',end)
                elif st['state']=='BUY_PENDING':s.record(st,'BUY_PENDING_CENSORED_AT_DATA_END',end)
            s.finalize()
            reports=report_layers_v1.reports(b,end)
            save(out/'ROUND_REPORT.json',reports['rounds']);save(out/'LAYER_REPORT.json',reports['layers']);save(out/'EXACT_TRADE_JOURNAL.json',reports['exact_trade_journal'])
            artifacts()
            for p,h in dict(s.hashes,**b.source_hashes).items():assert E.bridge.sha(p)==h,('source drift',p)
            for p,h in hashes.items():assert E.bridge.sha(p)==h
            summary=dict(status='COMPLETED_AUTHOR_REVIEW_PENDING',window=window,days=len(days),last_complete=last_complete,
                elapsed_seconds=time.monotonic()-started,peak_rss_bytes=rss(),actions=len(s.actions),action_counts=dict(collections.Counter(a['side'] for a in s.actions)),
                archive_rounds=len(s.archives),promotions=sum(a['type']=='PROMOTED' for a in b.audit),claims=len(s.claims),
                settled_claims=sum(c['settled'] for c in s.claims.values()),equity_bridges=len(s.bridges),first_uncertified=first_uncertified,
                final_reconciliation=daily[-1]['CLOSE'],reports=reports['counts'],complete_certified_NAV_path=first_uncertified is None,
                conditional_proxy_only=True,continuous_all_market_strategy=False,old_independent_rounds_are_not_same_funded_control=True)
            save(out/'RESULT.json',summary)
        save(out/'OUTPUT_SEAL.json',{p.name:E.bridge.sha(p) for p in out.iterdir() if p.is_file()})
        print('COMPLETED',window,json.dumps(summary,default=str))
    except BaseException as err:
        artifacts()
        if not (out/'RESULT.json').exists():save(out/'RESULT.json',dict(status='INCOMPLETE_OR_FAILED',error=repr(err),traceback=traceback.format_exc(),
            phase=phase,last_complete=last_complete,elapsed_seconds=time.monotonic()-started,peak_rss_bytes=rss(),first_uncertified=first_uncertified))
        print(traceback.format_exc());raise
if __name__=='__main__':run()
