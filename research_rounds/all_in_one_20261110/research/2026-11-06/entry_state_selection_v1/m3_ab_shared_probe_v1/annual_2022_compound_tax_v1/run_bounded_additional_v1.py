"""Sequential isolated QA workers, not an annual strategy run. Same fixed assertions,
full market reload per process, strict combined RSS/wall gate, no shared economic state."""
from pathlib import Path
import copy,gc,json,os,pickle,resource,signal,subprocess,sys,time,traceback
from decimal import Decimal as D
import compound_bridge_v1 as E
import additional_adapter_tests_v1 as T
import run_compound_annual_v1 as RUN
P=Path(__file__).resolve().parent;B=P.parent
LIMIT=6*1024**3;WALL=900
def save(out,name,x):
    with (out/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def load_runtime(path):
    s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,halt_evidence=E.AnnualHalts())
    with path.open('rb') as f:saved=pickle.load(f)
    for sid in saved['union']['loaded_sids']:s.load(sid)
    b.restore_runtime(saved)
    assert E.structural_digest(b.capture_runtime())==E.structural_digest(saved)
    return s,b,saved
def identities(s,b):
    sid='000987.SZ';rid='2022|A_UNION_B_SHARED_ENGINEERING_V1|000987.SZ|2'
    assert b.states[sid] is s.archives[rid]
    assert s.before_held.__self__ is b and s.coordinate_matches.__self__ is b
    assert b._native_accrue_day.__globals__['claims'] is s.claims
    assert b._native_accrue_day.__globals__['archives'] is s.archives
    claim=s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]
    assert any(c is claim for c in b._claims_for(rid))
def worker(phase,out):
    out.mkdir(exist_ok=False);start=time.monotonic();checks=[]
    def passed(name,detail=None):
        checks.append(dict(name=name,status='PASS',detail=detail));print('PASS',name,flush=True)
    try:
        reference=P/'qa_attempt_02';seal=E.read(reference/'OUTPUT_SEAL.json')
        for name,h in seal.items():assert E.sha(reference/name)==h,name
        if phase=='digest':
            import pandas as pd,numpy as np
            from digest_reference_v1 import structural_digest_reference as old
            fixtures=[{pd.Timestamp('2022-06-22'):D('1.00'),'2022-06-22 00:00:00':D('1'),('x',1):{1,2,3}},
              {'unicode':'登记','float':float('nan'),'array':np.array([1.2,3.4]),'na':pd.NA},
              pd.DataFrame({'a':[1,2],'b':[D('1.00'),D('2.00')]},index=pd.DatetimeIndex(['2022-01-04','2022-01-05']))]
            for x in fixtures:assert old(x)==E.structural_digest(x)
            sys.path.insert(0,'/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code')
            import sector_account
            with (reference/'PREFIX_CHECKPOINT.pkl').open('rb') as f:x=pickle.load(f)
            before=old(x);gc.collect();after=E.structural_digest(x);assert before==after
            save(out,'DIGEST_EQUIVALENCE.json',dict(reference=before,streamed=after,
                checkpoint_sha256=E.sha(reference/'PREFIX_CHECKPOINT.pkl'),all_fields_and_order_preserved=True))
            passed('exact_old_typed_JSON_vs_streamed_hash_on_heterogeneous_fixtures_and_actual47MiB_checkpoint')
        elif phase=='layers':
            s,b,saved=load_runtime(reference/'PREFIX_CHECKPOINT.pkl')
            identities(s,b);passed('sealed221_phase_253_action_prefix_full_source_reload_and_identity')
            T.run(b,saved,out,passed,checkpoint_separate=True)
            save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes))
        elif phase=='pre':
            s,b,saved=load_runtime(reference/'PREFIX_CHECKPOINT.pkl');identities(s,b)
            sid='000987.SZ';day=s.pd.Timestamp('2022-06-23');cash=b.cash()
            b._stage(day,'OPEN')
            valid=b._prepare_compound(b.states[sid],day)
            forged=copy.deepcopy(valid);forged['stock_reserve_total']=D(0)
            data=dict(forged);data.pop('plan_hash');forged['plan_hash']=E.M.digest(data)
            before=E.structural_digest(b.capture_runtime())
            try:b._commit_compound(forged,b.states[sid],day)
            except ValueError as error:assert 'exact real event and tax contract' in str(error)
            else:raise AssertionError('Self-rehashed wrong research expense accepted')
            assert E.structural_digest(b.capture_runtime())==before
            b._compound_open_preamble(day);identities(s,b)
            assert b.states[sid]['core']==405 and b.research_tax_total()==21 and b.cash()==cash-21
            assert len(b.share_ledger)==len(b.research_tax_ledger)==1
            post=b.capture_runtime()
            with (out/'POST_EX_CHECKPOINT.pkl').open('xb') as f:pickle.dump(post,f,protocol=5)
            with (out/'POST_EX_CHECKPOINT.pkl').open('rb') as f:loaded=pickle.load(f)
            assert E.structural_digest(post)==E.structural_digest(loaded)
            assert loaded['own']['states'][sid] is loaded['source']['archives'][b.states[sid]['round_id']]
            save(out,'STATE_DIGEST.json',dict(digest=E.structural_digest(post),checkpoint_sha256=E.sha(out/'POST_EX_CHECKPOINT.pkl')))
            save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes))
            passed('independent_pre_ex_process_real_source_bindings_atomic_issue_tax_accrual_and_pickle_identity')
        elif phase=='post':
            previous=out.parent/'pre'
            for name,h in E.read(previous/'OUTPUT_SEAL.json').items():assert E.sha(previous/name)==h,name
            s,b,saved=load_runtime(previous/'POST_EX_CHECKPOINT.pkl');identities(s,b)
            expected=E.read(previous/'STATE_DIGEST.json')['digest']
            assert E.structural_digest(b.capture_runtime())==expected
            sid='000987.SZ';day=s.pd.Timestamp('2022-06-23')
            assert b.states[sid]['core']==405 and b.research_tax_total()==21
            before=E.structural_digest(b.capture_runtime())
            try:b._prepare_compound(b.states[sid],day)
            except E.M.Unsupported as error:assert str(error)=='DUPLICATE_EQUITY_EVENT'
            else:raise AssertionError('Duplicate post-checkpoint equity accepted')
            assert E.structural_digest(b.capture_runtime())==before
            claim=s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)];assert claim['recognized'] and not claim['settled']
            cash=b.cash();s.pay_day(E.ARM,day);assert b.cash()==cash+48
            paid=b.cash();s.pay_day(E.ARM,day);assert b.cash()==paid and b.research_tax_total()==21
            assert len(b.share_ledger)==len(b.research_tax_ledger)==1
            save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes))
            passed('separate_fresh_post_ex_process_full_market_reload_claim_identity_no_double_stock_tax_or_pay')
        elif phase=='gates':
            gate=out/'release_gate';gate.mkdir();RUN.claim_once(gate)
            try:RUN.claim_once(gate)
            except FileExistsError:pass
            else:raise AssertionError('One-use gate reused')
            try:RUN.load_release(gate)
            except FileNotFoundError:pass
            else:raise AssertionError('Missing release accepted')
            save(gate,'RUN_CONTRACT.json',{'dependencies':{str(P/'RESEARCH_TAX_POLICY.json'):E.sha(P/'RESEARCH_TAX_POLICY.json')}})
            save(gate,'PRE_RUN_STAGE_SEAL.json',{'RUN_CONTRACT.json':E.sha(gate/'RUN_CONTRACT.json')})
            save(gate,'INDEPENDENT_REVIEW_RELEASE.json',dict(status='PASS',scope=RUN.SCOPE,
               reviewed_stage_sha256=E.sha(gate/'PRE_RUN_STAGE_SEAL.json'),synthetic_gate_fixture_only=True))
            RUN.load_release(gate)
            with (gate/'RUN_CONTRACT.json').open('a') as f:f.write(' ')
            try:RUN.load_release(gate)
            except ValueError:pass
            else:raise AssertionError('Changed reviewed contract accepted')
            assert not RUN.budget_verdict({'wall_seconds':1,'peak_rss_bytes':100},1,50)['passed']
            assert not RUN.budget_verdict({'wall_seconds':1,'peak_rss_bytes':100},.5,100)['passed']
            for cfg,want in [({'wall_seconds':.15,'peak_rss_bytes':LIMIT},'HARD_WALL_BUDGET'),
                             ({'wall_seconds':10,'peak_rss_bytes':1},'HARD_RSS_BUDGET')]:
                p=subprocess.Popen(['/bin/sleep','10'],start_new_session=True)
                reason,rss=RUN.supervise(p,cfg,time.monotonic());assert reason==want and p.returncode==-9
            passed('current_new_runner_exact_release_scope_hash_once_gate_and_real_dummy_budget_kills')
        else:raise ValueError('Unknown fixed QA phase')
        save(out,'CHECKS.json',checks)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if peak>=LIMIT or time.monotonic()-start>=WALL:raise RuntimeError('QA_RESOURCE_LIMIT_EXCEEDED')
        save(out,'RESULT.json',dict(status='PASS_FIXED_QA_ONLY',phase=phase,checks=len(checks),
             seconds=time.monotonic()-start,peak_rss_bytes=peak,limit_bytes=LIMIT,
             economic_run=False,full_source_reload=phase in ('layers','pre','post'),shared_market_or_economic_cache=False))
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),seconds=time.monotonic()-start,
             peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss));raise
    finally:save(out,'OUTPUT_SEAL.json',{str(p.relative_to(out)):E.sha(p) for p in out.rglob('*') if p.is_file()})

def main():
    if sys.argv[1:2]==['--worker']:
        worker(sys.argv[2],Path(sys.argv[3]));return
    name=sys.argv[1];assert name.startswith('qa_bounded_additional_') and name[22:].isdigit()
    out=P/name;out.mkdir(exist_ok=False);start=time.monotonic();results=[];max_combined=0
    original={str(p):E.sha(p) for p in (B/'annual_2022_marked_nav_v1/economic_run_2022_annual_once').iterdir() if p.is_file()}
    protected=E.read(B/'annual_2022_marked_nav_v1/PROTECTED_OLD_INPUTS.json')
    code_start={str(p):E.sha(p) for p in P.glob('*.py')}
    try:
        for phase in ('digest','layers','pre','post','gates'):
            log=out/(phase+'.log')
            with log.open('x') as stream:
                child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',phase,str(out/phase)],
                  stdout=stream,stderr=stream,start_new_session=True)
                while child.poll() is None:
                    elapsed=time.monotonic()-start
                    ps=subprocess.run(['/bin/ps','-o','rss=','-p',str(child.pid)+','+str(os.getpid())],capture_output=True,text=True)
                    if ps.returncode and child.poll() is None:raise RuntimeError('QA RSS supervisor unavailable')
                    rss=sum(int(v.strip()) for v in ps.stdout.splitlines() if v.strip())*1024
                    max_combined=max(max_combined,rss)
                    if elapsed>=WALL or rss>=LIMIT:
                        os.killpg(child.pid,9);child.wait();raise RuntimeError('HARD_COMBINED_QA_RESOURCE_LIMIT')
                    time.sleep(.1)
                if child.returncode:raise RuntimeError('QA child failed '+phase+' exit '+str(child.returncode))
            r=E.read(out/phase/'RESULT.json')
            combined_peak=r['peak_rss_bytes']+resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if combined_peak>=LIMIT:raise RuntimeError('POST_WRITE_COMBINED_QA_RESOURCE_LIMIT')
            max_combined=max(max_combined,combined_peak);results.append(r);print('PASS',phase,r['peak_rss_bytes'],flush=True)
        for path,h in code_start.items():assert E.sha(path)==h,('code drift',path)
        for path,h in original.items():assert E.sha(path)==h,path
        for path,h in protected.items():assert E.sha(path)==h,path
        save(out,'RESULT.json',dict(status='AUTHOR_BOUNDED_ADDITIONAL_QA_PASS_PENDING_INDEPENDENT_REVIEW',
           phases=results,original_six_logical_groups_all_retained=True,new_digest_and_current_runner_gates_added=True,
           maximum_combined_peak_rss_bytes=max_combined,limit_bytes=LIMIT,wall_seconds=WALL,
           elapsed_seconds=time.monotonic()-start,old317_and_annual38_unchanged=True,
           no_new_annual_economic_run=True,no_shared_economic_or_market_objects_between_processes=True))
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start,
             maximum_combined_peak_rss_bytes=max_combined));raise
    finally:save(out,'OUTPUT_SEAL.json',{str(p.relative_to(out)):E.sha(p) for p in out.rglob('*') if p.is_file()})
if __name__=='__main__':main()
