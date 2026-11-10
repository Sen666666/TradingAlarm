"""Fail-closed single economic run. Execute only after independent fixed-byte release."""
from pathlib import Path
from dataclasses import asdict
from decimal import Decimal as D
import os, sys, json, hashlib, time, subprocess, resource, pickle, copy, types, traceback
import union_bridge_v1 as E
import report_known_halt_v2 as REPORT
HERE=Path(__file__).resolve().parent
SCOPE='RUN_2022_UNION_TO_FIRST_RESPONSIBILITY_UNKNOWN_ONCE'
def save(out,name,value):
    with (out/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=lambda x:asdict(x) if hasattr(x,'__dataclass_fields__') else str(x));f.write('\n')
def load_release(root=HERE):
    root=Path(root);release=json.loads((root/'INDEPENDENT_REVIEW_RELEASE.json').read_bytes())
    if release.get('status')!='PASS' or release.get('scope')!=SCOPE:raise ValueError('Independent release not granted')
    data=(root/'PRE_RUN_STAGE_SEAL.json').read_bytes()
    if hashlib.sha256(data).hexdigest()!=release.get('reviewed_stage_sha256'):raise ValueError('Reviewed seal changed')
    stage=json.loads(data);verified={}
    for relative,h in stage.items():
        p=(root/relative).resolve()
        if Path(relative).is_absolute() or not p.is_relative_to(root.resolve()):raise ValueError('External stage path')
        d=p.read_bytes()
        if hashlib.sha256(d).hexdigest()!=h:raise ValueError('Changed stage dependency '+relative)
        verified[relative]=d
    contract=json.loads(verified['RUN_CONTRACT.json'])
    for p,h in contract['dependencies'].items():
        if E.sha(p)!=h:raise ValueError('Changed external dependency '+p)
    return contract,release

def claim_once(root=HERE):
    # Durable O_EXCL tombstone remains even after failure/kill. No automatic retry.
    fd=os.open(Path(root)/'ECONOMIC_RUN_ONCE.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.write(fd,json.dumps(dict(pid=os.getpid(),created_utc=time.time())).encode());os.fsync(fd);os.close(fd)

def report_closed(b,day,phase):
    # Native fee/claim allocation, with OPEN stopping day CLOSE hidden even from reports.
    proxy=copy.copy(b);source=types.SimpleNamespace(**b.s.__dict__)
    class View:
        def __init__(self,raw):self.raw=raw
        def get(self,d,default=None):
            row=self.raw.get(d,default)
            if phase=='OPEN' and d==day and row is not None:return {k:v for k,v in row.items() if k not in ('raw_close','raw_high','raw_low','raw_volume')}
            return row
    source.raw={sid:View(raw) for sid,raw in b.s.raw.items()};proxy.s=source
    r=REPORT.reports(proxy,day)
    def stats(rows,pnl,buy):
        closed=[x for x in rows if x.get('status',x.get('layer_status'))=='EXECUTION_AND_SETTLEMENT_CLOSED']
        values=[x[pnl] for x in closed];capital=sum((x[buy] for x in closed),D(0))
        return dict(total_filled=len(rows),execution_and_settlement_closed_denominator=len(closed),excluded_open_or_unsettled=len(rows)-len(closed),
            wins=sum(v>0 for v in values),losses=sum(v<0 for v in values),flat=sum(v==0 for v in values),
            win_rate=None if not closed else D(sum(v>0 for v in values))/D(len(closed)),
            NET80_sum=sum(values,D(0)),actual_buy_cash_sum=capital,pooled_return_on_actual_buy_cash=None if not capital else sum(values,D(0))/capital)
    r['closed_stage_statistics']=dict(rounds=stats(r['rounds'],'whole_round_NET80','whole_round_actual_buy_cash'),
        first_probe=stats([x for x in r['layers'] if x['layer']=='core'],'NET80','buy_cash'),
        ADD=stats([x for x in r['layers'] if x['layer']=='add'],'NET80','buy_cash'))
    return r

def source_row_at_phase(row,current,phase):
    if current and phase=='OPEN':return {k:v for k,v in row.items() if k in ('raw_open','adjustment_factor','source_kind','source_path','segment_id')}
    return dict(row)

def checkpoint(b,out,day,phase,rows,blockers,reason):
    # Include any local-action provenance read for the blocker before sealing source hashes.
    for x in blockers:b.s.local_actions(x['sid'])
    runtime=b.capture_runtime()
    with (out/'CHECKPOINT.pkl').open('xb') as f:pickle.dump(runtime,f,protocol=5)
    # A round-trip proves preservation of state/archive shared identity, Decimal,
    # timestamps, sets, layer and fee schedule classes, not a lossy JSON restart.
    with (out/'CHECKPOINT.pkl').open('rb') as f:loaded=pickle.load(f)
    for sid,st in loaded['own']['states'].items():
        if b.states[sid] is b.s.archives[st['round_id']]:assert st is loaded['source']['archives'][st['round_id']]
        else:assert st==b.states[sid]
    save(out,'CHECKPOINT_INDEX.json',dict(version=1,day=day,phase=phase,reason=reason,
        sha256=E.sha(out/'CHECKPOINT.pkl'),top_level=list(runtime),own_fields=list(runtime['own']),source_fields=list(runtime['source']),union_fields=list(runtime['union']),
        market_restore='Reload exact hashed source via safe bridge; load saved loaded_sids; restore pickle runtime, cp_cache/meta/actions_sources and exact projected catalog. No continuation authorized.',
        no_force_liquidation=True,phase_complete=True,checkpoint_roundtrip_identity_pass=True))
    data={'ACTIONS':b.s.actions,'DECISIONS':b.s.decisions,'RANKING_AUDIT':b.s.ranking_audit,'AUDIT':b.audit,'PHASE_LEDGER':rows,
        'ARCHIVES':b.s.archives,'STATES':b.states,'LAYERS':[asdict(x) for x in b.layers],'ORDERS':b.orders,
        'CLAIMS':list(b.s.claims.values()),'REGISTRATIONS':b.s.registrations,'CLAIM_LEDGER':b.s.claim_ledger,
        'EQUITY_BRIDGES':b.s.bridges,'PROFIT_GATES':b.s.marks,'ROUND_ND':b.caps,'SOURCE_ROUNDS':b.s.rounds,
        'SOURCE_HASHES':dict(b.s.hashes,**b.source_hashes),'UNION_AUDIT':b.union_tape.audit,'FIRST_BLOCKING_UNKNOWN':blockers}
    for name,value in data.items():save(out,name+'.json',value)
    relevant={}
    for x in blockers:
        sid=x['sid'];st=b.s.archives[x['round_id']];prior=b.s.cal[b.s.cal<day][-1]
        def safe_row(d):
            row=b.s.raw[sid].get(d,{})
            return source_row_at_phase(row,d==day,phase)
        relevant[sid]=dict(state=st,manifest=b.s.manifest[sid],prior_day=prior,prior_raw=safe_row(prior),phase_raw=safe_row(day),
            dated_rules={str(k):v for k,v in b.s.meta.items() if k[0]==sid},local_actions=b.s.local_actions(sid),current_close_fields_excluded=phase=='OPEN')
    save(out,'BLOCKING_SOURCE_EVIDENCE.json',relevant)

def budget_verdict(contract,elapsed,peak):
    wall_ok=elapsed<contract['wall_seconds'];rss_ok=peak<contract['peak_rss_bytes']
    return dict(passed=wall_ok and rss_ok,wall_ok=wall_ok,rss_ok=rss_ok,elapsed_seconds=elapsed,peak_rss_bytes=peak,
        status='WITHIN_RESOURCE_BUDGET' if wall_ok and rss_ok else 'INCOMPLETE_RESOURCE_BUDGET')

def worker(contract,out,started):
    b=None;rows=[];day=None;phase='LOAD';reason=None;blockers=[]
    try:
        s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,seed_cash=D(contract['seed']),halt_evidence=E.UnionHalts())
        assert s.ev.window.eq('2022').all() and s.ev.day.max()<=s.pd.Timestamp(contract['birth_end'])
        assert len(s.EVENTS)==436 and len(b.groups)==s.ev.day.nunique()
        days=s.cal[(s.cal>=s.pd.Timestamp(contract['start']))&(s.cal<=s.pd.Timestamp(contract['end']))]
        assert str(days[0].date())==contract['first_common_day']
        for n,day in enumerate(days):
            for phase in (('CLOSE',) if n==0 else ('OPEN','CLOSE')):
                result=b.open_phase(day)['reconciliation'] if phase=='OPEN' else b.close_phase(day)
                row=dict(day=day,phase=phase,reconciliation=result,actions=len(s.actions),archives=len(s.archives),elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                rows.append(row);blockers=E.blocking_unknowns(b,day,phase)
                if blockers:reason='FIRST_NEW_RESPONSIBILITY_UNKNOWN';break
                if time.monotonic()-started>=contract['phase_stop_seconds'] or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>=contract['phase_stop_rss_bytes']:
                    reason='SOFT_RESOURCE_STOP_AT_COMPLETE_PHASE';break
            if reason:break
        if reason is None:reason='ORIGINAL_COHORT_FOLLOW_END_WITHOUT_NEW_BLOCKER'
        # Stop immediately after the completed original phase; no next CLOSE after OPEN blocker.
        checkpoint(b,out,day,phase,rows,blockers,reason)
        reports=report_closed(b,day,phase)
        for name,key in [('ROUND_REPORT','rounds'),('LAYER_REPORT','layers'),('EXACT_TRADE_JOURNAL','exact_trade_journal'),('CLOSED_STAGE_STATISTICS','closed_stage_statistics')]:save(out,name+'.json',reports[key])
        for p,h in dict(s.hashes,**b.source_hashes,**contract['dependencies']).items():assert E.sha(p)==h,('Source drift',p)
        gaps=[r for r in rows if r['reconciliation']['NAV'] is None]
        summary=dict(status='DIAGNOSTIC_UNKNOWN_STOP_AUTHOR_REVIEW_PENDING' if reason=='FIRST_NEW_RESPONSIBILITY_UNKNOWN' else 'INCOMPLETE_RESOURCE_STOP' if reason=='SOFT_RESOURCE_STOP_AT_COMPLETE_PHASE' else 'COHORT_FOLLOW_END_AUTHOR_REVIEW_PENDING',reason=reason,last_complete_phase=(day,phase),phases=len(rows),days_started=len({r['day'] for r in rows}),
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            first_blocking_unknown=blockers,first_blocking_phase=(day,phase) if blockers else None,first_blocking_source_log=blockers[0] if blockers else None,actions=len(s.actions),claims=len(s.claims),settled_claims=sum(c['settled'] for c in s.claims.values()),
            NAV=rows[-1]['reconciliation']['NAV'],endpoint_return=None,drawdown=None,NAV_gap_phases=len(gaps),
            closed_stage_statistics=reports['closed_stage_statistics'],full_2022_strategy=False,continuous_admission=False,
            birth_cohort_only=True,no_force_liquidation=True,no_automatic_evidence_repair_or_rerun=True,
            actual_record_q_only=True,NET80_not_actual_withholding=True,completion_requires='WORKER_BUDGET_RESULT and FINAL_BUDGET_RESULT both passed')
        before_result=budget_verdict(contract,time.monotonic()-started,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if not before_result['passed']:summary['status']='INCOMPLETE_RESOURCE_BUDGET'
        summary['pre_result_budget']=before_result
        save(out,'RESULT.json',summary)
    except BaseException as err:
        save(out,'FAILURE.json',dict(status='FAILED_NOT_NORMAL_STOP',error=repr(err),traceback=traceback.format_exc(),last_phase=(day,phase),elapsed_seconds=time.monotonic()-started))
        raise
    finally:
        save(out,'OUTPUT_SEAL.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file() and p.name!='execution.log'})
        after_exports=budget_verdict(contract,time.monotonic()-started,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        save(out,'WORKER_BUDGET_RESULT.json',dict(after_exports,reports_exports_and_worker_seal_included=True))
        if not after_exports['passed']:raise RuntimeError('INCOMPLETE_RESOURCE_BUDGET_AFTER_EXPORTS')

def supervise(child,contract,started):
    failure=None;max_rss=0
    while child.poll() is None:
        elapsed=time.monotonic()-started
        ps=subprocess.run(['/bin/ps','-o','rss=','-p',str(child.pid)],capture_output=True,text=True)
        if ps.returncode and child.poll() is None:raise RuntimeError('Cannot enforce RSS monitor')
        current=int(ps.stdout.strip() or 0)*1024;max_rss=max(max_rss,current)
        if elapsed>=contract['wall_seconds'] or current>=contract['peak_rss_bytes']:
            failure='HARD_WALL_BUDGET' if elapsed>=contract['wall_seconds'] else 'HARD_RSS_BUDGET'
            os.killpg(child.pid,9);child.wait();break
        time.sleep(.1)
    return failure,max_rss

def main():
    if sys.argv[1:]==['--worker']:
        # Internal child must have the durable preflight marker and exclusive output.
        contract,release=load_release();out=HERE/'economic_run_2022_once'
        if not (HERE/'ECONOMIC_RUN_ONCE.lock').exists() or not (out/'STARTED.json').exists():raise ValueError('Missing supervisor preflight')
        fd=os.open(out/'WORKER_STARTED.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        started=float(os.environ['UNION_MONOTONIC_START']);worker(contract,out,started);return
    if sys.argv[1:]:raise ValueError('No economic dates or parameters accepted')
    assert sys.platform=='darwin'
    started=time.monotonic();contract,release=load_release();claim_once()
    out=HERE/'economic_run_2022_once';out.mkdir(exist_ok=False)
    save(out,'STARTED.json',dict(contract=contract,release=release,started_utc=time.time(),supervisor_pid=os.getpid(),monotonic_start=started))
    if time.monotonic()-started>=contract['phase_stop_seconds']:raise RuntimeError('Preflight exhausted resource budget')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',UNION_MONOTONIC_START=str(started))
    with (out/'execution.log').open('x') as log:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker'],stdout=log,stderr=log,env=env,start_new_session=True)
        try:failure,max_rss=supervise(child,contract,started)
        except BaseException:
            if child.poll() is None:os.killpg(child.pid,9);child.wait()
            raise
    worker_path=out/'WORKER_BUDGET_RESULT.json'
    worker_budget=json.loads(worker_path.read_text()) if worker_path.exists() else None
    peak=max(max_rss,(worker_budget or {}).get('peak_rss_bytes',0))
    post_exit=budget_verdict(contract,time.monotonic()-started,peak)
    valid=child.returncode==0 and failure is None and worker_budget is not None and worker_budget['passed'] and post_exit['passed']
    save(out,'SUPERVISOR_RESULT.json',dict(status='CHILD_COMPLETED_PENDING_FINAL_BUDGET' if valid else 'INCOMPLETE_OR_FAILED',exit_code=child.returncode,hard_stop=failure,
        post_exit_budget=post_exit,worker_budget=worker_budget,observed_peak_rss_bytes=max_rss,no_retry_lock_retained=True,hard_stop_may_lack_phase_checkpoint=failure is not None))
    save(out,'SUPERVISOR_OUTPUT_SEAL.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file()})
    final_budget=budget_verdict(contract,time.monotonic()-started,peak)
    final_budget.update(passed=bool(valid and final_budget['passed']),reports_exports_parent_seal_included=True,
        status='COMPLETED_WITHIN_BUDGET' if valid and final_budget['passed'] else 'INCOMPLETE_OR_FAILED',
        authoritative_completion_gate=True,child_exit_code=child.returncode)
    save(out,'FINAL_BUDGET_RESULT.json',final_budget)
    # Do not label an exit-window race successful. A small final metadata write is
    # followed by an actual post-write check, not merely the live-child poll loop.
    if not final_budget['passed'] or time.monotonic()-started>=contract['wall_seconds']:
        save(out,'FINAL_BUDGET_FAILURE.json',dict(status='INCOMPLETE_OR_FAILED',elapsed_seconds=time.monotonic()-started,peak_rss_bytes=peak))
        raise SystemExit(2)
if __name__=='__main__':main()
