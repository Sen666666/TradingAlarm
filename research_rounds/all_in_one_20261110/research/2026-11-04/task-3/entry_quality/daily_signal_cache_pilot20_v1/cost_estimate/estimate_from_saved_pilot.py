"""Summarize existing pilot CPU/bytes only. No numerical model imports/calls."""
from pathlib import Path
import json,hashlib
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent;PILOT=HERE.parent;ENTRY=PILOT.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
 assert not(HERE/'SEAL.json').exists()
 receipt=json.loads((PILOT/'RUN_RECEIPT.json').read_text());freeze=json.loads((PILOT/'FREEZE.json').read_text());rs=receipt['records']
 assert receipt['stocks']==len(rs)==20 and receipt['calls_new_full_signal']==60
 source=Path(freeze['source']);stat=source.stat()
 assert stat.st_size==freeze['source_size']and stat.st_mtime_ns==freeze['source_mtime_ns']
 N=pq.ParquetFile(source).metadata.num_rows
 scope_path=ENTRY/'e0_stage_pvr_v1/performance_review/SOURCE_SCOPE_AND_COST_ESTIMATES.json';scope=json.loads(scope_path.read_text())
 assert scope['source_sha256']==freeze['source_sha256']and scope['source_full_rows']==N
 rows=sum(r['baseline_rows']for r in rs);grid=sum(r['daily_grid_rows']for r in rs);observed=sum(r['source_rows_in_output']for r in rs)
 assert rows==64930 and grid==21080 and observed==18881
 components=list(rs[0]['profile']['component_CPU_seconds'])
 profiles=[]
 for k in components:
  cpu=sum(r['profile']['component_CPU_seconds'][k]for r in rs)
  profiles.append(dict(component=k,pilot_baseline_CPU_core_seconds=cpu,CPU_ms_per_input_row=cpu/rows*1000,
      full5517_CPU_core_seconds_row_weighted=cpu*N/rows,
      ideal8worker_minutes=cpu*N/rows/8/60,ideal12worker_minutes=cpu*N/rows/12/60))
 pd.DataFrame(profiles).to_csv(HERE/'BASELINE_CPU_COMPONENTS.csv',index=False)
 files=[]
 prefix_cpu={k:0. for k in components};prefix_rows=0;prefix_calls=0
 for r in rs:
  folder=PILOT/'full'/r['sid']
  for cut in r['physical_prefix_cuts']:
   pr=json.loads((folder/f'PREFIX_{cut}.json').read_text());prefix_calls+=1;prefix_rows+=pr['input_rows']
   for k in components:prefix_cpu[k]+=pr['component_profile']['component_CPU_seconds'][k]
  for name in ['BASELINE_FULL_HISTORY.parquet','DAILY2022_20260515.parquet']:
   p=folder/name;meta=pq.ParquetFile(p).metadata
   assert sha(p)==r['file_sha256'][name]and p.stat().st_size==r['file_bytes'][name]
   assert meta.num_rows==(r['baseline_rows']if name.startswith('BASELINE')else r['daily_grid_rows'])
   files.append(dict(sid=r['sid'],file=name,rows=meta.num_rows,parquet_physical_columns=meta.num_columns,
       bytes=p.stat().st_size,compression=meta.row_group(0).column(0).compression,sha256=sha(p)))
 pd.DataFrame(files).to_csv(HERE/'VERIFIED_PILOT_FILES.csv',index=False)
 fullbytes=sum(r['file_bytes']['BASELINE_FULL_HISTORY.parquet']for r in rs)
 dailybytes=sum(r['file_bytes']['DAILY2022_20260515.parquet']for r in rs)
 D=scope['source_observed_date_union_count_2022_onward'];fullgrid=D*5517
 old_rates=[r['model_CPU_core_seconds']/r['total_model_prefix_rows']for r in json.loads((ENTRY/'e0_stage_pvr_v1/performance_review/SAVED_MODEL_COSTS.json').read_text())]
 other_perrow=sum(p['pilot_baseline_CPU_core_seconds']for p in profiles if p['component']!='original_stock_signal')/rows
 totalcpu=sum(p['full5517_CPU_core_seconds_row_weighted']for p in profiles)
 summary=dict(status='READ_ONLY_COST_ESTIMATE_FROM_COMPLETED20_PILOT_NO_NEW_MODELS',
    receipt_path=str(PILOT/'RUN_RECEIPT.json'),receipt_sha256=sha(PILOT/'RUN_RECEIPT.json'),
    freeze_sha256=sha(PILOT/'FREEZE.json'),source_sha256=freeze['source_sha256'],source_rows=N,
    actual_pilot_workers=freeze['workers'],actual_pilot_total_wall_seconds=receipt['elapsed_seconds'],
    baseline_calls=20,physical_prefix_validation_calls=40,
    prefix_validation_input_rows=prefix_rows,prefix_validation_component_CPU_core_seconds=prefix_cpu,
    prefix_validation_CPU_core_seconds_total=sum(prefix_cpu.values()),
    pilot_total_wall_includes_prefix_validation_roundtrips_and_IO=True,
    baseline_input_rows=rows,baseline_eligible_rows=sum(r['profile']['eligible_rows']for r in rs),
    baseline_daily_grid_rows=grid,baseline_daily_observed_rows=observed,
    baseline_output_dataframe_columns=sorted(set(r['output_columns']for r in rs)),
    baseline_fullhistory_core_columns=sorted(set(r['all_columns']for r in rs)),
    all20_CP_amount_valid_no_first_bad=all(r['profile']['cp_first_bad_date']is None for r in rs),
    old19_exact=sum(x['status']=='EXACT19'for r in rs for x in r['old19_checks']),
    old19_nonexact_statuses=pd.Series([x['status']for r in rs for x in r['old19_checks']if x['status']!='EXACT19']).value_counts().to_dict(),
    old_PVR_target_checks=sum(len(r['oldPVR_dates'])for r in rs),
    CPU_components=profiles,total_row_weighted_CPU_core_seconds=totalcpu,
    ideal_compute_only_minutes=dict(worker8=totalcpu/8/60,worker12=totalcpu/12/60),
    historical_full5517_native_rate_plus_pilot_other_components_compute_minutes={
        str(w):[N*(min(old_rates)+other_perrow)/w/60,N*(max(old_rates)+other_perrow)/w/60]for w in [8,12]},
    planning_minutes_including_large_output_and_audit_not_measured=dict(worker12=[35,50],worker8=[45,65]),
    planning_intervals_are_judgment_not_measured_confidence_bounds=True,
    naive_wall_times_stock_count_minutes_not_valid_production_estimate=receipt['elapsed_seconds']*5517/20/60,
    storage=dict(pilot_baseline_fullhistory_bytes=fullbytes,pilot_daily_bytes=dailybytes,
        full_history_row_weighted_bytes=fullbytes*N/rows,
        all5517_daily_grid_rows=fullgrid,daily_grid_weighted_bytes=dailybytes*fullgrid/grid,
        source_2022_observed_rows=scope['source_2022_onward_rows'],
        daily_observed_weighted_bytes=dailybytes*scope['source_2022_onward_rows']/observed,
        projection_not_file_size_guarantee=True,compression='ZSTD in sampled pilot files; content/schema/partitioning changes compression',
        excludes_source_input_copy_prefix_JSON_logs_and_future_dataset_versions=True),
    historical_source_ends=scope['source_observed_date_union_last'],H1_complete=False,
    original_35_45minute_estimate_excluded_CP=True,
    native_profile_contains_numeric_capture_no_extra_numeric_model_call=True,
    no_all5517_run_performed=True,new_model_calls=0,new_accounts=0)
 save('COST_AND_SIZE_ESTIMATE.json',summary)
 print(json.dumps(dict(components=profiles,compute12=summary['ideal_compute_only_minutes'],
    historical_adjusted=summary['historical_full5517_native_rate_plus_pilot_other_components_compute_minutes'],storage=summary['storage']),ensure_ascii=False))

if __name__=='__main__':main()
