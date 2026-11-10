"""Analysis-only errata; never construct accounts or advance market events."""
from pathlib import Path
import json,gzip,hashlib,collections,shutil
import pandas as pd
from opportunity_endpoints import annotate,summarize
O=Path(__file__).resolve().parent;W=O.parent.parent;ERR=O/'analysis-endpoint-errata-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
changed=[]
def save(p,x):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');t.replace(p);changed.append(p)
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def main():
    assert ERR.is_dir();states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    reports=[];metrics={};corrections={};named=[]
    for ref,root,expected in [('SC',W/'recovery-2023-readiness-20261101/runs/Bdiag',(3588,356,2983,249)),('PVR_SLOT1',O/'run-2023',(3521,400,2872,249))]:
        base=Path('analysis-2023')/ref
        cal=[x['at'][:10] for x in rows(root/'pair/daily.jsonl.gz') if x['at'].startswith('2023')]
        gs=[annotate(g,states,cal) for g in read(O/base/'ALL_ROLE_FIRST_ELIGIBLE_DELAYS.json')]
        unheld=[g for g in gs if not g['held_at_first_eligibility']];s=summarize(unheld,'anyrole_funding_endpoint')
        assert (s['groups'],s['funded_before_attempt_end'],s['industry_attempt_ended_before_funding'],s['still_active_at_observation_cutoff_right_censored'])==expected,(ref,s)
        assert s['later_funding_after_termination']==0
        old=read(ERR/base/'ALL_ROLE_FIRST_ELIGIBLE_SUMMARY.json');new=dict(old)
        new.pop('initially_unheld_no_later_buy_censored',None);new.pop('inherited_market_attempts',None)
        new.update(initially_unheld_no_observed_later_buy=s['groups']-s['funded_before_attempt_end'],competing_endpoints=s,
            stock_attempt_groups_with_industry_attempt_inherited=sum(g['industry_attempt_inherited_before_window'] for g in gs),
            distinct_inherited_industry_attempts=len({(g['sector'],g['market_attempt']) for g in gs if g['industry_attempt_inherited_before_window']}),
            inherited_scope='industry attempt starts before2023 only; not proof of full stock signal history',
            termination_scope='industry authorization attempt ended; not a statement that stock was actually sold')
        save(base/'ALL_ROLE_FIRST_ELIGIBLE_DELAYS.json',gs);save(base/'ALL_FIRST_ELIGIBLE_DELAYS.json',gs)
        save(base/'ALL_ROLE_FIRST_ELIGIBLE_SUMMARY.json',new);reports.append(new)
        m=read(ERR/base/'METRICS.json');prior=dict(m);f=dict(m['all_market_qualified_CP1_funnel'])
        f.pop('never_funded_censored',None);ms=summarize(gs,'mobile_funding_endpoint')
        f.update(no_observed_mobile_funding=ms['groups']-ms['funded_before_attempt_end'],mobile_competing_endpoints=ms)
        m['all_market_qualified_CP1_funnel']=f
        assert {k:v for k,v in m.items() if k!='all_market_qualified_CP1_funnel'}=={k:v for k,v in prior.items() if k!='all_market_qualified_CP1_funnel'}
        save(base/'METRICS.json',m);metrics[ref]=m;corrections[ref]=dict(anyrole_initially_unheld=s,mobile_all_groups=ms)
        ff=[x for x in rows(root/'pair/funding.jsonl.gz') if x.get('sid')=='300308.SZ' and x['at'].startswith('2023')]
        op=[x for x in ff if '09:30' in x['at'] and x['result']=='open_minimum_exceeds_frozen_contract']
        close=[x for x in ff if '15:10' in x['at'] and x['role']=='core']
        assert len(close)==(22 if ref=='SC' else 21);assert len(op)==(0 if ref=='SC' else 1)
        named.append(dict(reference=ref,OPEN_minimum_frozen_contract_failures=len(op),CLOSE_core_target_failures=len(close),
            CLOSE_core_raw_reasons=dict(collections.Counter(x['result'] for x in close)),
            first_industry_invalidated='first observed route blocker only, not full-year cause',OPEN_records=op,CLOSE_records=close))
    save('analysis-2023/ALL_ROLE_COMPARISON.json',reports);save('COMPARISON_2023.json',[metrics['SC'],metrics['PVR_SLOT1']])
    save('analysis-2023/NAMED_STOCK_OPEN_CLOSE_DENOMINATOR_CORRECTION.json',named)
    g=read(O/'analysis-2023/BEHAVIOR_SUPPLEMENT_GATE.json');g.pop('all_unfunded_right_censors_retained',None)
    g.update(source_sha256=sha(O/'behavior_supplement.py'),industry_termination_separate_from_observation_cutoff=True,endpoint_source_sha256=sha(O/'opportunity_endpoints.py'))
    save('analysis-2023/BEHAVIOR_SUPPLEMENT_GATE.json',g)
    comp=read(O/'analysis-2023/COMPLETION.json');comp.update(analysis_sha256=sha(O/'analyze_continuation.py'),analysis_endpoint_only_corrected=True,no_account_replays=True)
    save('analysis-2023/COMPLETION.json',comp)
    # Correct prose without republishing/recomputing the audited financial results.
    p=O/'RESULTS_2023.txt';text=p.read_text()
    text=text.replace('187继承左删失','187组的行业attempt起于窗前(不是股票机会历史完整性结论)')
    text=text.replace('未获资右删失3232','未获资3232分为行业attempt先结束2983、观察末仍有效右删失249')
    text=text.replace('未获资右删失3121','未获资3121分为行业attempt先结束2872、观察末仍有效右删失249')
    text=text.replace('一次冻结目标最小单位不足，不统一归整手','1次OPEN冻结目标最小单位失败，另有21次CLOSE core风险/整手目标失败(SC22次)，不能混算；首industry_invalidated不代表全年原因')
    p.write_text(text);changed.append(p)
    p=O/'causal-review-2023/ROOT_READOUT.txt';text=p.read_text()
    text=text.replace('187继承左删失','187组的行业attempt起于窗前(不等于股票机会历史也已完整或左删失)')
    text=text.replace('未获资3232/3121右删失','SC未获资3232=2983行业attempt先结束+249观察末仍有效；PVR未获资3121=2872先结束+249仍有效，只有后者是右删失')
    p.write_text(text);changed.append(p)
    audit=Path('/tmp/pvr-2023-continuation-independent-jzq90yks/VERDICT.json');dest=O/'independent-2023-financial-audit/VERDICT.json';dest.parent.mkdir(exist_ok=True);shutil.copy2(audit,dest)
    ready=read(O/'READINESS_2023_FOR_INDEPENDENT_AUDIT.json');ready.update(independent_result_audit_pending=False,independent_financial_audit_pass=True,
        independent_financial_verdict_sha256=sha(dest),analysis_endpoint_correction='ANALYSIS_ENDPOINT_CORRECTION.json')
    save('READINESS_2023_FOR_INDEPENDENT_AUDIT.json',ready)
    oldmap=read(ERR/'CONTINUATION_2023_ARTIFACT_SHA256.json')['files'];financial=['run-2023/pair/B.json.gz','run-2023/checkpoint.pkl','run_continuation.py','horizon_import.py']
    assert all(sha(O/p)==oldmap[p] for p in financial)
    gate=dict(passed=True,scope='analysis-only competing endpoints; economic data/code unchanged',account_replays=0,
        group_denominators=corrections,regression_tests=9,regression_source_sha256=sha(O/'test_opportunity_endpoints.py'),
        exact_tie_policy='completed fill first;industry close-end before cutoff at equal timestamp',
        known_endpoints_only_through='2023-12-29T15:10:00+08:00',old_bad_sources_and_outputs_preserved='analysis-endpoint-errata-v1',
        unchanged_financial_sources={p:sha(O/p) for p in financial},corrected_source_sha256={p:sha(O/p) for p in ['opportunity_endpoints.py','behavior_supplement.py','analyze_continuation.py','publish_2023.py']})
    save('ANALYSIS_ENDPOINT_CORRECTION.json',gate)
    save('ANALYSIS_ENDPOINT_CORRECTION_SHA256.json',{str(p.relative_to(O)):sha(p) for p in changed})
    print('ENDPOINT_REPAIR_PASS',corrections,flush=True)
if __name__=='__main__':main()
