"""Read saved development counts only. No indicator, protection, or fitting run."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / 'kama_observation_v1/frequency_matched_v1'
OUT = Path(__file__).resolve().parent / 'DEVELOPMENT_LOCK_AUDIT.json'

def read(name):
    return json.loads((F/name).read_text())

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    receipt=read('dev_run_v1/RUN_RECEIPT.json')
    lock=read('dev_run_v1/LOCK_EMA.json')
    counts=read('dev_run_v1/DEVELOPMENT_FREQUENCY_COUNTS.json')
    workers=[read(f'dev_run_v1/WORKER_{j}.json') for j in range(3)]
    assert receipt['status']=='COMPLETE_DEVELOPMENT_COUNTS_ONLY'
    assert lock['status']=='LOCKED_FOR_VALIDATION'
    assert receipt['source_sha256']==lock['source_sha256']
    for path,h in lock['source_sha256'].items():
        assert sha(path)==h, path
    M=sum(w['common_n'] for w in workers)
    assert M==counts['common_n']==receipt['common_n']==lock['common_n']
    gates=Counter(); raw=0; maxdays=[]; statuses=Counter(); bound={}
    for w in workers:
        assert not w['errors']
        gates.update(w['gates'])
        assert sum(w['gates'].values())==sum(r['raw_anchors'] for r in w['reports'])
        assert sum(r['common_n'] for r in w['reports'])==w['common_n']
        for r in w['reports']:
            statuses[r['status']]+=1;raw+=r['raw_anchors']
            day=r.get('maximum_computed_price_day')
            if day is not None:
                assert day<='2023-12-31'
                assert r['validation_data_not_computed'] is True
                maxdays.append(day)
    assert raw==35713==receipt['raw_anchors']
    assert dict(gates)==counts['gate_counts']==receipt['gate_counts']
    assert gates['EVALUABLE_FULL20']+gates['EVALUABLE_I_COMPETING_END']==M
    arms=counts['arms'];assert len(arms)==478
    assert arms[0]['arm']=='KAMA' and arms[0]['period'] is None
    assert [a['period'] for a in arms[1:]]==list(range(4,481))
    names=['protection','I_competing','no_exit20','protection_commonP0','protection_I_raised','protection_band_raised']
    for j,a in enumerate(arms):
        assert a['common_n']==M
        for key in names:
            assert a[key]==sum(w['counts'][key][j] for w in workers)
            assert 0<=a[key]<=M
        assert a['protection']+a['I_competing']+a['no_exit20']==M
        assert sum(a[k] for k in names[3:])==a['protection']
        assert a['protection_frequency']==a['protection']/M
    target=arms[0]['protection']
    err=min(abs(a['protection']-target) for a in arms[1:])
    minimizers=[a['period'] for a in arms[1:] if abs(a['protection']-target)==err]
    expected=max(minimizers)
    chosen=next(a for a in arms[1:] if a['period']==expected)
    assert expected==lock['period']==16
    assert target==lock['KAMA_protection_count']==15254
    assert chosen['protection']==lock['EMA_protection_count']==15050
    pp=100*err/M
    assert pp==lock['absolute_frequency_error_percentage_points'] and pp<=1
    vstart=read('validation_run_v1/RUN_START.json')
    assert vstart['source_sha256'][str((F/'dev_run_v1/LOCK_EMA.json').resolve())]==sha(F/'dev_run_v1/LOCK_EMA.json')
    assert vstart['locked_EMA_period']==expected and vstart['validation_EMA_periods_computed']==[expected]
    # Source files inspected as text: no importing data/indicator/trace modules.
    development=(F/'run_dev.py').read_text()
    assert "filters=[('date','<=',pd.Timestamp(DEV_END))]" in development
    assert "DEV_END='2023-12-31'" in development
    assert "['sid','anchor_day','anchor_id','status','P0']" in development
    for p in [F/'FREEZE.md', F/'core.py', F/'run_dev.py', F/'run_validation.py', F/'paired_trace.py',
              F/'dev_run_v1/LOCK_EMA.json', F/'dev_run_v1/DEVELOPMENT_FREQUENCY_COUNTS.json',
              F/'dev_run_v1/RUN_RECEIPT.json', F/'validation_run_v1/RUN_START.json',
              *[F/f'dev_run_v1/WORKER_{j}.json' for j in range(3)]]:
        bound[str(p.resolve())]=sha(p)
    result=dict(status='PASS_BOUNDED_DEVELOPMENT_COUNT_LOCK_AND_VALIDATION_STATIC_WITH_LIMITS',
        development_raw_anchors=raw,common_M=M,gate_counts=dict(gates),reports_by_status=dict(statuses),
        maximum_reported_development_price_day=max(maxdays),
        EMA_grid=list(range(4,481)),all_478_arms_worker_counts_and_partition_equal=True,
        KAMA_protection=target,locked_EMA=expected,locked_EMA_protection=chosen['protection'],
        minimum_absolute_count_error=err,all_minimizing_periods=minimizers,error_percentage_points=pp,
        development_lock_bound_before_validation=True,
        static_checks=['Development parquet date filter occurs before feature/indicator calls',
            'All N share anchor_only and common_anchor data-only gates; no early-exit-dependent inclusion',
            'Known close/source precede native I0 competing termination',
            'Native I exact same-day reindex and segment required',
            'Old P tested before max update; new Q never tests current bar',
            'Validation accepted_lock verifies477 counts and computes only locked N',
            'Validation pair-only seed gate plus EMA480 metadata subgroup; no reselecting N'],
        limits=['No independent indicator/protection trajectory recomputation or raw data scan',
            'Worker source cutoff statements checked against code, not independent dataframe execution',
            'Original saved pair JSON is parsed before slimming; only retained entry/P0/status fields enter development. No assertion of never deserializing future saved metadata.',
            'Warm support differs between development all-grid and validation pair-only conditions',
            'Old six-case run did not exercise all unknown branches; current branch review is static',
            'Validation outputs not yet audited; no price-quality or economic approval'],
        remaining_blocks_for_reviewed_development_lock=[],new_model_runs=0,new_accounts=0,
        source_sha256=bound)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','development_raw_anchors','common_M','locked_EMA','all_minimizing_periods','error_percentage_points']}))
    print('AUDIT_SHA256',sha(OUT))

if __name__=='__main__':
    main()
