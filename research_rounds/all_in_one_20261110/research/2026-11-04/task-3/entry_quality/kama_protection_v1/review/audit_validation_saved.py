"""Independently recount saved two-arm records, not indicators or shadows."""
from pathlib import Path
from collections import Counter
import gzip
import hashlib
import json
import math
import numpy as np

HERE=Path(__file__).resolve().parent
F=HERE.parents[1]/'kama_observation_v1/frequency_matched_v1'
V=F/'validation_run_v1'

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(x,y):
    assert (x is None)==(y is None),(x,y)
    if x is not None:assert math.isclose(x,y,rel_tol=1e-11,abs_tol=1e-12),(x,y)
def dist(values):
    values=[float(x)for x in values if x is not None and math.isfinite(x)]
    if not values:return {'n':0}
    v=np.array(values)
    return dict(n=len(v),mean=float(v.mean()),median=float(np.median(v)),p10=float(np.quantile(v,.1)),p90=float(np.quantile(v,.9)),min=float(v.min()),max=float(v.max()))
def distribution_eq(actual,expected):
    assert actual['n']==expected['n']
    for k in ['mean','median','p10','p90','min','max']:
        if k in expected:near(actual[k],expected[k])
def order(t):
    k,e=t['KAMA'],t['EMA'];ko,eo=k['outcome'],e['outcome']
    if ko==eo=='EXIT_SIGNAL':return 'BOTH_EXIT_KAMA_EARLIER'if k['exit_day']<e['exit_day']else'BOTH_EXIT_EMA_EARLIER'if e['exit_day']<k['exit_day']else'BOTH_EXIT_SAME_DAY'
    if ko=='EXIT_SIGNAL'and eo=='RIGHT_CENSORED':return 'KAMA_EXIT_EMA_RIGHT_CENSORED'
    if eo=='EXIT_SIGNAL'and ko=='RIGHT_CENSORED':return 'EMA_EXIT_KAMA_RIGHT_CENSORED'
    if ko==eo=='RIGHT_CENSORED':return 'BOTH_RIGHT_CENSORED'
    return 'UNKNOWN_PRESENT_'+ko+'__'+eo

def main():
    receipt=read(V/'RUN_RECEIPT.json');start=read(V/'RUN_START.json')
    assert receipt['status']=='COMPLETE_LOCKED_VALIDATION'
    assert receipt['locked_EMA_period']==16 and receipt['computed_EMA_periods']==[16]
    assert all(w['errors']==0 for w in receipt['workers'])
    assert receipt['source_sha256']==start['source_sha256']
    for p,h in receipt['source_sha256'].items():assert sha(p)==h,p
    rows=[]
    for j in range(3):
        with gzip.open(V/f'WORKER_{j}_ANCHORS.jsonl.gz','rt')as f:part=[json.loads(line)for line in f]
        w=read(V/f'WORKER_{j}.json');assert not w['errors']
        assert dict(Counter(r['group']for r in part))==w['group_raw']
        rows.extend(part)
    assert len(rows)==receipt['raw_anchors']==15313
    assert len({(r['group'],r['sid'],r['anchor_day'])for r in rows})==len(rows)
    groups={g:[r for r in rows if r['group']==g]for g in ['VALIDATION_2024_SEP_DEC','SEMICONDUCTOR_2025_2026H1']}
    groups['VALIDATION_2024_924_ONWARD']=[r for r in groups['VALIDATION_2024_SEP_DEC']if r['anchor_day']>='2024-09-24']
    for g,n in [('VALIDATION_2024_SEP_DEC',12412),('SEMICONDUCTOR_2025_2026H1',2901),('VALIDATION_2024_924_ONWARD',11904)]:assert len(groups[g])==n
    frequency=read(V/'FREQUENCY_AND_COVERAGE.json');summary=read(V/'TRACE_SUMMARY.json')
    report={};counts_keys=['protection','I_competing','no_exit20','protection_commonP0','protection_I_raised','protection_band_raised']
    for r in rows:
        if 'trace'in r:
            t=r['trace'];E=t['E_reference'];assert E>t['P0']>0
            for arm in ['KAMA','EMA']:
                a=t[arm];assert a['observations']>=0
                if a['observations']==0:
                    assert all(a[k]is None for k in ['MFE_while_held','MAE_while_held','max_close_drawdown_while_held'])
                if a['outcome']=='EXIT_SIGNAL':
                    assert a['exit_age']==a['observations']>=1
                    assert a['exit_day']>=t['entry_day']
                    q=a['next_OPEN'];p=q.get('OPEN')
                    if p is not None:
                        assert p>0 and q['day']>a['exit_day']
                        near(a['exit_OPEN_unit_price_change'],p/E-1)
                    else:assert a['exit_OPEN_unit_price_change']is None
                    if a['exit_age']<=20 and p is not None:
                        assert a['H20_kind']=='EARLY_EXIT_REFERENCE_HELD_FLAT'
                        near(a['H20_unit_price_change'],p/E-1)
                if r.get('H20_counts')is not None:
                    j=0 if arm=='KAMA' else 1
                    expected='no_exit20'
                    if a['outcome']=='EXIT_SIGNAL'and a['exit_age']<=20:
                        expected='protection'if a['exit_reason']=='EXIT_STORED_LINE'else'I_competing'
                    for k in counts_keys[:3]:assert r['H20_counts'][k][j]==int(k==expected)
                    assert sum(r['H20_counts'][k][j]for k in counts_keys[3:])==r['H20_counts']['protection'][j]
            if r.get('H20_counts')is not None and all(t[arm]['H20_kind']=='COMMON_20TH_CLOSE_NEXT_OPEN_MARK_NOT_EXIT'for arm in ['KAMA','EMA']):
                near(t['KAMA']['H20_unit_price_change'],t['EMA']['H20_unit_price_change'])
    for g,rs in groups.items():
        fr=frequency[g];su=summary[g];assert fr['raw_anchors']==len(rs)==su['all_raw_anchors']
        assert fr['anchor_gates']==dict(Counter(r['anchor_gate']for r in rs))
        assert fr['H20_gates']==dict(Counter(r['H20_gate']for r in rs))
        for name,selected in [('main',[r for r in rs if r.get('H20_counts')is not None]),('dev_style_EMA480_warm_subgroup',[r for r in rs if r.get('H20_counts')is not None and r['dev_style_EMA480_warm']])]:
            n=len(selected);assert fr[name]['common_n']==n
            for key in counts_keys:
                assert fr[name]['counts'][key]==[sum(r['H20_counts'][key][j]for r in selected)for j in range(2)]
            for j in range(2):assert sum(fr[name]['counts'][k][j]for k in counts_keys[:3])==n
            near(fr[name]['validation_frequency_gap_percentage_points'],100*abs(fr[name]['counts']['protection'][0]-fr[name]['counts']['protection'][1])/n)
        eligible=[r for r in rs if r.get('trace')is not None];assert su['anchor_eligible_n']==len(eligible)
        assert su['exit_comparisons_split_censor']==dict(Counter(order(r['trace'])for r in eligible))
        assert su['common_market_end_reasons']==dict(Counter(r['trace']['common_market_end_reason']for r in eligible))
        h20=[r for r in eligible if r.get('H20_counts')is not None]
        quoted=[r for r in h20 if all(r['trace'][arm]['H20_unit_price_change']is not None for arm in ['KAMA','EMA'])]
        qp=su['H20_common_quote_unit_proxy'];assert qp['common_H20_evaluable_n']==len(h20) and qp['both_quotes_available_n']==len(quoted)
        for arm in ['KAMA','EMA']:
            aa=su['arms'][arm];observed=[r['trace'][arm]for r in eligible if r['trace'][arm]['observations']>0]
            assert aa['outcomes']==dict(Counter(r['trace'][arm]['outcome']for r in eligible))
            for key in ['MFE_while_held','max_close_drawdown_while_held']:
                distribution_eq(aa[key],dist(a[key]for a in observed))
            distribution_eq(qp[arm],dist(r['trace'][arm]['H20_unit_price_change']for r in quoted))
        distribution_eq(qp['KAMA_minus_EMA'],dist(r['trace']['KAMA']['H20_unit_price_change']-r['trace']['EMA']['H20_unit_price_change']for r in quoted))
        label=[r for r in eligible if r['trace']['common_market_end_reason']in('ORIGINAL_I_INVALID','SOURCE_END')and r['trace']['common_MFE']is not None]
        threshold=float(np.quantile([r['trace']['common_MFE']for r in label],.9));wd=su['winner_diagnostic'];near(wd['q90'],threshold)
        tail=[r for r in label if r['trace']['common_MFE']>=threshold]
        assert wd['label_evaluable_n']==len(label) and wd['tail_n']==len(tail)
        assert wd['tail_source_end_lower_bound_n']==sum(r['trace']['common_label_is_observed_lower_bound']for r in tail)
        assert wd['exit_comparisons_split_censor']==dict(Counter(order(r['trace'])for r in tail))
        report[g]=dict(raw_n=len(rs),anchor_ready_n=len(eligible),H20_M=fr['main']['common_n'],protection_counts=fr['main']['counts']['protection'],
            frequency_gap_pp=fr['main']['validation_frequency_gap_percentage_points'],H20_quote_pairs=len(quoted),H20_delta_mean_fraction=qp['KAMA_minus_EMA'].get('mean'),
            H20_gap_not_equal_frequency=(fr['main']['validation_frequency_gap_percentage_points']>1),winner_tail_n=len(tail),winner_tail_source_end_lower_bound_n=wd['tail_source_end_lower_bound_n'])
    fixed=read(V/'FIXED_EARLY_STRONG_CASES.json')
    assert {(r['sid'],r['anchor_day'])for r in fixed}=={('002583.SZ','2024-09-20'),('300085.SZ','2024-09-12')}
    bykey={(r['group'],r['sid'],r['anchor_day']):r for r in rows}
    assert all(bykey[(r['group'],r['sid'],r['anchor_day'])]==r for r in fixed)
    paths=[V/'RUN_RECEIPT.json',V/'RUN_START.json',V/'FREQUENCY_AND_COVERAGE.json',V/'TRACE_SUMMARY.json',V/'FIXED_EARLY_STRONG_CASES.json',F/'paired_trace.py',F/'run_validation.py',F/'core.py',F/'dev_run_v1/LOCK_EMA.json',*[V/f'WORKER_{j}_ANCHORS.jsonl.gz'for j in range(3)],*[V/f'WORKER_{j}.json'for j in range(3)]]
    result=dict(status='PASS_BOUNDED_SAVED_VALIDATION_COUNTS_AND_LABEL_SUMMARIES_WITH_LIMITS',raw_rows=15313,windows=report,
        locked_N16_source_identity_and_only_period_verified=True,all_saved_H20_counts_match_saved_trace_causes=True,
        scope='Full saved15313 row/key/partition/frequency/outcome/quote arithmetic and summarized distributions/q90 re-count. Static source review of full prefix and protection clocks.',
        limits=['No independent source-price/indicator/protection reconstruction','Native source guards statically read; original same-day segmentation not independently rebuilt per row','Validation frequencies are unequal; no equal-frequency marginal-quality attribution','Seed-support populations differ; dev-style warm480 subgroup remains descriptive','SOURCE_END future winner labels are observed lower bounds; semi tail includes175 such anchors','Overlapping anchors are dependent, unweighted reference-price paths with no actual executions or account capital'],
        remaining_blocks_for_reviewed_saved_scope=[],new_model_runs=0,new_accounts=0,source_sha256={str(p.resolve()):sha(p)for p in paths})
    out=HERE/'VALIDATION_SAVED_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'windows':report},ensure_ascii=False));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
