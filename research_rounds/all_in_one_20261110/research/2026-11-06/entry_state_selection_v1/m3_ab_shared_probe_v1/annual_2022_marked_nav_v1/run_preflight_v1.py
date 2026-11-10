"""Bounded preparation only: synthetic checks and exact saved prefix to May18."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,copy,time,traceback,hashlib,subprocess,resource
import annual_bridge_v1 as E
import marked_nav_v1 as M
import run_annual_v1 as RUN
HERE=Path(__file__).resolve().parent;B=HERE.parent;OLD=B/'known_evidence_union_diagnostic_v1'
def normalize(x):return json.loads(json.dumps(x,default=str))
def save(out,name,x):RUN.save(out,name,x)
def main():
    label=sys.argv[1]
    if not label.startswith('qa_attempt_') or not label[11:].isdigit():raise ValueError('New QA label required')
    out=HERE/label;out.mkdir(exist_ok=False);start=time.monotonic();checks=[]
    save(out,'START.json',dict(scope='SYNTHETIC_AND_SAVED_PREFIX_ONLY',prefix_end='2022-05-18',new_annual_economic_runs=0))
    def passed(name,detail=None):
        checks.append(dict(name=name,status='PASS',detail=detail));print('PASS',name,flush=True)
    try:
        import test_known_halt_v1 as H
        import test_candidate_v1 as T
        s=E.bridge.load_original('2022');result=H.suite(s);save(out,'LEGACY_20.json',result);del s
        s=E.bridge.load_original('2022');result=T.suite(s);save(out,'CANDIDATE_26.json',result);del s
        h=E.AnnualHalts()
        import pandas as pd
        for sid,day in [('600595.SH','2022-01-13'),('600403.SH','2022-04-15'),('600595.SH','2022-05-19')]:assert h.get(sid,pd.Timestamp(day))
        for sid,day in [('600595.SH','2022-05-18'),('600595.SH','2022-05-20'),('600403.SH','2022-05-19'),('000001.SZ','2022-05-19')]:assert h.get(sid,pd.Timestamp(day)) is None
        assert h.get('600595.SH',pd.Timestamp('2022-05-19'))['known_at']=='2022-05-18T21:19:59+08:00'
        passed('exact_three_halt_sessions_no_planned_resume_extension',dict(halts=len(h.rows),artifact_count=len(h.hashes)))
        may=json.loads((HERE/'MAY19_HALT_EVIDENCE.json').read_text())['halts'][0]
        for clock in ['2022-05-19T09:30:00+08:00','2022-05-19T09:30:01+08:00','2022-05-19']:
            bad=copy.deepcopy(may);bad['clock']['published_at']=clock
            assert E.C.HaltEvidence([bad],synthetic=True).get('600595.SH',pd.Timestamp('2022-05-19')) is None
        passed('equal_late_or_timezone_missing_clock_not_admitted')
        protected=json.loads((HERE/'PROTECTED_OLD_INPUTS.json').read_text())
        for p,hsh in protected.items():assert E.sha(p)==hsh,p
        passed('all_old_FAILED_locks_and_evidence_unchanged',len(protected))
        # Reporting receives only immutable finished reconciliation dictionaries.
        oldrows=json.loads((OLD/'economic_run_2022_once/PHASE_LEDGER.json').read_text())
        before=E.digest(oldrows);stats,curve=M.stats(oldrows)
        assert E.digest(oldrows)==before
        assert stats['close_observations']==87 and stats['supported_stale_close_count']==2
        assert stats['annual_endpoint_return'] is None and stats['annual_marked_close_maximum_drawdown'] is None
        assert stats['complete_marked_close_path'] and curve[-1]['marked_NAV'] is None
        assert D(stats['last_close_marked_NAV'])==D('1170149.9869376717060')
        save(out,'SAVED_PREFIX_REPORT_ONLY.json',stats)
        passed('old_6_supported_gap_phases_reported_without_filling_May19_UNKNOWN_or_mutating_risk',dict(supported_substitutions=sum(x['supported_indicative_substitution'] for x in curve),last_unknown=curve[-1]))
        r=copy.deepcopy(oldrows[-1]);r['reconciliation']['indicative_NAV_NOT_CERTIFIED']='1200000'
        assert M.marked_row(r)['marked_NAV'] is None
        r['reconciliation']['NAV_gap_reason']='KNOWN_HALT_STALE_MARK'
        assert M.marked_row(r)['marked_NAV'] is None
        r['reconciliation']['unknown']=[];r['reconciliation']['stale_marks']=[]
        try:M.marked_row(r)
        except ValueError:pass
        else:raise AssertionError('unsupported carry accepted')
        passed('ordinary_UNKNOWN_and_mixed_halt_UNKNOWN_never_get_reporting_carry')
        # End-point and drawdown arithmetic independently fixed fixture; no post-end rows.
        fake=[]
        for day,value in [('2022-01-04','1200000'),('2022-01-05','1320000'),('2022-12-30','1188000')]:
            fake.append(dict(day=day,phase='CLOSE',reconciliation=dict(NAV=value,certified=True,unknown=[])))
        st,_=M.stats(fake)
        assert st['annual_endpoint_return']==D('-.01') and st['annual_marked_close_maximum_drawdown']==D('-.1')
        fake[1]['reconciliation'].update(NAV=None,certified=False,unknown=[{'sid':'X'}],NAV_gap_reason='ASSET_OR_SOURCE_UNKNOWN')
        st,_=M.stats(fake)
        assert st['annual_endpoint_return']==D('-.01') and st['annual_marked_close_maximum_drawdown'] is None
        passed('year_end_endpoint_distinct_from_complete_path_DD_no_annualization')
        # Verify release gate and one-use lock with new directory only.
        gate=out/'gate_fixture';gate.mkdir();RUN.claim_once(gate)
        try:RUN.claim_once(gate)
        except FileExistsError:pass
        else:raise AssertionError('one-use lock reused')
        try:RUN.load_release(gate)
        except FileNotFoundError:pass
        else:raise AssertionError('missing release allowed')
        save(gate,'RUN_CONTRACT.json',{'dependencies':{str(HERE/'MAY19_HALT_EVIDENCE.json'):E.sha(HERE/'MAY19_HALT_EVIDENCE.json')}})
        save(gate,'PRE_RUN_STAGE_SEAL.json',{'RUN_CONTRACT.json':E.sha(gate/'RUN_CONTRACT.json')})
        save(gate,'INDEPENDENT_REVIEW_RELEASE.json',dict(status='PASS',scope=RUN.SCOPE,reviewed_stage_sha256=E.sha(gate/'PRE_RUN_STAGE_SEAL.json'),fixture_only=True))
        RUN.load_release(gate)
        with (gate/'RUN_CONTRACT.json').open('a') as f:f.write(' ')
        try:RUN.load_release(gate)
        except ValueError:pass
        else:raise AssertionError('tamper accepted')
        passed('exclusive_single_use_lock_missing_and_changed_release_fail_closed')
        assert RUN.budget_verdict({'wall_seconds':1,'peak_rss_bytes':100},1,50)['passed'] is False
        assert RUN.budget_verdict({'wall_seconds':1,'peak_rss_bytes':100},.5,100)['passed'] is False
        for cfg,expected in [({'wall_seconds':.15,'peak_rss_bytes':6*1024**3},'HARD_WALL_BUDGET'),({'wall_seconds':10,'peak_rss_bytes':1},'HARD_RSS_BUDGET')]:
            child=RUN.subprocess.Popen(['/bin/sleep','10'],start_new_session=True)
            reason,rss=RUN.supervise(child,cfg,time.monotonic())
            assert reason==expected and child.returncode==-9
        passed('strict_wall_RSS_boundaries_and_actual_supervisor_dummy_kills')
        # Original data execution is bounded to the exact already-observed prefix.
        s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,halt_evidence=E.AnnualHalts());rows=[]
        days=s.cal[(s.cal>=pd.Timestamp('2022-01-04'))&(s.cal<=pd.Timestamp('2022-05-18'))]
        assert len(days)==87
        annualdays=s.cal[(s.cal>=pd.Timestamp('2022-01-01'))&(s.cal<=pd.Timestamp('2022-12-31'))]
        assert str(annualdays[-1].date())=='2022-12-30'
        original_events=copy.deepcopy(s.EVENTS);original_digest=E.digest(original_events)
        for n,day in enumerate(days):
            for phase in (('CLOSE',) if n==0 else ('OPEN','CLOSE')):
                rec=b.open_phase(day)['reconciliation'] if phase=='OPEN' else b.close_phase(day)
                row=dict(day=day,phase=phase,reconciliation=rec)
                old=oldrows[len(rows)]
                assert normalize(rec)==old['reconciliation'],(day,phase,'reconciliation drift')
                assert not E.blocking_unknowns(b,day,phase)
                rows.append(row)
        assert len(rows)==173
        actions=json.loads((OLD/'economic_run_2022_once/ACTIONS.json').read_text())
        assert normalize(s.actions)==actions and len(actions)==217
        assert E.digest(s.EVENTS[:436])==original_digest and len(s.EVENTS)==437
        save(out,'PREFIX_PHASES.json',rows);save(out,'PREFIX_ACTIONS.json',s.actions)
        deps=json.loads((OLD/'RUN_CONTRACT.json').read_text())['dependencies']
        old_overlap=len(set(b.source_hashes)&set(deps))
        assert old_overlap>0
        try:dict(s.hashes,**b.source_hashes,**deps)
        except TypeError as error:duplicate_error=repr(error)
        else:raise AssertionError('original duplicate mapping failure not reproduced')
        merged=E.merge_hashes(s.hashes,b.source_hashes,deps)
        for p,hsh in merged.items():assert E.sha(p)==hsh,('Source drift',p)
        key=next(iter(set(b.source_hashes)&set(deps)))
        try:E.merge_hashes(b.source_hashes,{key:'0'*64})
        except ValueError:pass
        else:raise AssertionError('conflicting duplicate accepted')
        save(out,'ACTUAL_HASH_MERGE_TEST.json',dict(bridge_hash_count=len(b.source_hashes),source_hash_count=len(s.hashes),contract_count=len(deps),duplicate_expansion_keys=old_overlap,merged_count=len(merged),original_error=duplicate_error,same_value_duplicates_verified=True,conflicting_value_rejected=True))
        passed('real_source_and_contract_key_intersection_merge_reproduces_old_failure_then_passes',dict(duplicate_expansion_keys=old_overlap,merged_count=len(merged)))
        save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes))
        save(out,'PREFIX_COMPARISON.json',dict(status='PASS',sessions=len(days),phases=len(rows),actions=len(s.actions),all_reconciliations_equal=True,all_actions_equal=True,old436_unchanged=True,union_count=437,fixed_end='2022-05-18',annual_common_sessions=len(annualdays),annual_end=str(annualdays[-1].date()),new_annual_economic_runs=0))
        passed('173_original_phases_and_217_actions_exact_unchanged_through_May18')
        # New finalization works on actual overlapping maps, not only empty fixtures.
        for p,hsh in protected.items():assert E.sha(p)==hsh,p
        save(out,'CHECKS.json',checks)
        save(out,'RESULT.json',dict(status='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW',legacy_groups=20,candidate_groups=26,new_groups=len(checks),prefix_sessions=87,prefix_phases=173,prefix_actions=217,new_annual_economic_runs=0,seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
    finally:save(out,'OUTPUT_SEAL.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file()})
if __name__=='__main__':main()
