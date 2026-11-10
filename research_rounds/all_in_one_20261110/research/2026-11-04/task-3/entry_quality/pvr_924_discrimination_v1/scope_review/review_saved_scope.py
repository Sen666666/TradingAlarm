"""Saved denominator/coverage counters and runtime planning only; no models."""
from pathlib import Path
import hashlib,json
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
MAIN=ENTRY/'full_local_signal_20240924_v1/FULL5517_CANDIDATES.parquet'
PILOT=ENTRY/'full_local_signal_20240924_v1/signals/PILOT_SUMMARY.json'
DONE=ENTRY/'full_local_signal_20240924_v1/signals/COMPLETION.json'
RETIRED=ENTRY/'no_future_cap_selection_v1/SEPARATE_RETIRED239_OBSERVED_COVERAGE.csv'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(HERE/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    assert not(HERE/'SCOPE_AND_PLAN.json').exists()
    f=pd.read_parquet(FEATURES,columns=['sid','day','target_row_present','past_source_observation_count','source_observation_count_through_t','current_block_observations_through_t'])
    x=pd.read_parquet(MAIN,columns=['sid','day','score','research_PVR_pool','i_buy_research','rank_ALL_LOCAL_I_BUY','current_close_qfq'])
    selected=x.research_PVR_pool.eq(True)&x.i_buy_research.eq(True);cohort=x.loc[selected].copy()
    assert len(x)==5517 and len(cohort)==2313 and cohort.sid.nunique()==2313
    assert np.isfinite(cohort.score).all()and np.isfinite(cohort.current_close_qfq).all()
    cohort.sort_values('rank_ALL_LOCAL_I_BUY').to_csv(HERE/'ASOF2313_REFERENCE_KEYS.csv',index=False)
    end=f.loc[f.day.eq('2026-05-15')].set_index('sid').source_observation_count_through_t
    pilot=json.loads(PILOT.read_text());done=json.loads(DONE.read_text())
    denominator=int(pilot['remaining_model_prefix_rows']);base_seconds=float(done['full_batch_wall_seconds'])
    plans=[]
    for day in ['2022-01-24','2024-09-24','2026-01-15']:
        g=f.loc[f.day.eq(day)];p=g.loc[g.target_row_present].copy();counts=p.source_observation_count_through_t
        future=p.sid.map(end).to_numpy()-counts.to_numpy();assert(future>=0).all()
        rows=int(counts.sum());plans.append(dict(day=day,mother=5517,exact_target_requests=len(p),missing_target_skip_model=len(g)-len(p),
            all_source_prefix_rows=int(g.source_observation_count_through_t.sum()),model_prefix_rows_cold_exact_only=rows,
            prefix_min=int(counts.min()),prefix_median=float(counts.median()),prefix_p90=float(counts.quantile(.9)),prefix_max=int(counts.max()),
            ratio_to_actual_20240924_remaining_work=rows/denominator,
            estimated_cold_12worker_wall_minutes=base_seconds*rows/denominator/60,
            source_future_rows_to_May15_min=int(future.min()),source_future_rows_to_May15_median=float(np.median(future)),
            exact_targets_with_atleast5_later_source_rows=int((future>=5).sum()),
            exact_targets_with_atleast20_later_source_rows=int((future>=20).sum()),
            exact_targets_with_fewer5_later_source_rows=int((future<5).sum()),
            exact_targets_with_fewer20_later_source_rows=int((future<20).sum())))
    pd.DataFrame(plans).to_csv(HERE/'COLD_SIGNAL_WORKLOAD_PLAN.csv',index=False)
    retired=pd.read_csv(RETIRED);assert retired.mother.eq(239).all()
    retired.to_csv(HERE/'EXISTING_RETIRED239_SEPARATE_COVERAGE.csv',index=False)
    current=f.loc[f.day.eq('2024-09-24')].set_index('sid').source_observation_count_through_t
    post=cohort.sid.map(end).to_numpy()-cohort.sid.map(current).to_numpy()
    result=dict(status='COMPLETE_SAVED_SCOPE_REVIEW_AND_CONDITIONAL_RUNTIME_PLAN_NO_LAUNCH',
        cohort_definition='Saved research_PVR_pool==True AND i_buy_research==True; decision2024-09-24; no future labels involved',
        cohort_N=2313,cohort_with_atleast5_future_source_rows_to_frozen_end=int((post>=5).sum()),
        cohort_with_atleast20_future_source_rows_to_frozen_end=int((post>=20).sum()),
        available_row_count_not_full_forward_path_audit=True,source_end='2026-05-15',
        observed_runtime=dict(workers=12,wall_seconds=base_seconds,new_model_prefix_rows=denominator,
            reused_exact_target_symbols=124,all_exact_target_cold_prefix_rows=plans[1]['model_prefix_rows_cold_exact_only']),
        target_date_cold_plans=[r for r in plans if r['day']!='2024-09-24'],
        two_target_dates_sequential_point_minutes=sum(r['estimated_cold_12worker_wall_minutes']for r in plans if r['day']!='2024-09-24'),
        runtime_is_workload_scaled_estimate_not_guarantee=True,no_simultaneous24worker_speedup_claim=True,
        source_sha256={str(p):sha(p)for p in [FEATURES,MAIN,PILOT,DONE,RETIRED,Path(__file__)]},
        new_model_or_account_calls=0,new_signal_runs_started=0,new_price_forward_labels=0,new_data_refreshes=0)
    save('SCOPE_AND_PLAN.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
