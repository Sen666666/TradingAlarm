"""Saved CPU/provenance and source-date metadata only. No model imports/calls."""
from pathlib import Path
import hashlib,json
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
RUNS={
 '2022-01-24':ENTRY/'full_local_signal_two_dates_v1/2022-01-24/signals',
 '2024-09-24':ENTRY/'full_local_signal_20240924_v1/signals',
 '2026-01-15':ENTRY/'full_local_signal_two_dates_v1/2026-01-15/signals',
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
 assert not(HERE/'SEAL.json').exists()
 source_hash=sha(SOURCE);assert source_hash=='11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b'
 timing=[];bindings=[]
 for day,folder in RUNS.items():
  c=json.loads((folder/'COMPLETION.json').read_text());rows=[]
  for p in sorted((folder/'full').glob('*.jsonl')):
   rows.extend(json.loads(s)for s in p.read_text().splitlines())
  assert len(rows)==len({r['sid']for r in rows})
  models=[r for r in rows if r.get('model_invoked')]
  prefix=sum(r['input_prefix_rows']for r in models)
  cpu=sum(r.get('model_cpu_seconds',0)for r in models)
  wall=sum(r.get('model_seconds',0)for r in models)
  records=dict(day=day,new_full_requests=len(rows),completed_model_calls=len(models),
      missing_requests=sum(r['signal_status']=='MISSING_TARGET_BAR'for r in rows),
      total_model_prefix_rows=prefix,model_CPU_core_seconds=cpu,model_wall_sum_seconds=wall,
      CPU_ms_per_input_row=cpu/prefix*1000,model_CPU_mean_seconds=cpu/len(models),
      model_CPU_p50_seconds=float(pd.Series([r['model_cpu_seconds']for r in models]).median()),
      model_CPU_p90_seconds=float(pd.Series([r['model_cpu_seconds']for r in models]).quantile(.9)),
      recorded_invocation_wall_seconds=c['full_batch_wall_seconds'],
      original_CPU_measurement_scope='Entire stock_signal.calculate only; excludes source reads, per-stock JSONL/fsync, prior reused inputs, controls and lost inflight work',
      component_numeric_CPU_seconds=None,component_B4_CPU_seconds=None,
      component_profiling_not_recorded=True,only_target_row_persisted=True)
  if(folder/'SEGMENT_TIMING.json').exists():
   s=json.loads((folder/'SEGMENT_TIMING.json').read_text())
   records.update(end_to_end_including_interruption_seconds=s['end_to_end_wall_including_interruption_seconds'],
      observed_first_write_span_plus_resume_invocation_seconds=s['first_observed_write_span_seconds']+s['resumed_invocation_wall_seconds'],
      exact_total_active_wall_unknown=True)
  timing.append(records)
  bindings.append(dict(path=str(folder/'COMPLETION.json'),sha256=sha(folder/'COMPLETION.json'),
      raw_signals_path=str(folder/'ALL_SIGNALS.parquet'),raw_signals_sha256=sha(folder/'ALL_SIGNALS.parquet')))
 pd.DataFrame(timing).to_csv(HERE/'SAVED_MODEL_COSTS.csv',index=False);save('SAVED_MODEL_COSTS.json',timing)
 metadata=pq.ParquetFile(SOURCE).metadata
 # Date-only read counts source observations/calendar union; no OHLCV or model execution.
 dates=ds.dataset(SOURCE).to_table(columns=['trade_date'],filter=ds.field('trade_date')>=pd.Timestamp('2022-01-01')).column('trade_date')
 union=sorted(dates.unique().to_pylist());D=len(union);N=metadata.num_rows
 cpu_rates=[r['model_CPU_core_seconds']/r['total_model_prefix_rows']for r in timing]
 estimates=dict(source_path=str(SOURCE),source_sha256=source_hash,source_full_rows=N,source_2022_onward_rows=len(dates),
     source_observed_date_union_count_2022_onward=D,source_observed_date_union_first=str(pd.Timestamp(union[0]).date()),
     source_observed_date_union_last=str(pd.Timestamp(union[-1]).date()),source_union_not_official_calendar=True,
     no_same_source_Jun30_or_full2026_coverage=True,
     sequential_full_stock_signal_CPU_core_seconds_range=[N*min(cpu_rates),N*max(cpu_rates)],
     ideal12worker_compute_wall_minutes_range=[N*min(cpu_rates)/12/60,N*max(cpu_rates)/12/60],
     practical_planning_range_minutes=[35,45],practical_range_not_new_measurement=True,
     estimate_limits='Extrapolates whole-function recorded CPU; numeric-only not separately timed. Assumes unchanged data/parameters/operation order, comparable event density; full-cache output I/O not measured; long-leg fsum worst-case quadratic.',
     rerunning_full_prefix_each_source_date_hours_range=[D*22.587/60,D*34.05/60],
     daily_recompute_range_is_rough_source_date_count_times_three_snapshot_cost=True,
     uncompressed19_slots_times8_bytes_2022_onward=len(dates)*19*8,
     storage_is_raw_slot_estimate_excludes_keys_masks_string_payload_and_encoding=True,
     compressed_cache_bytes_unknown=True)
 save('SOURCE_SCOPE_AND_COST_ESTIMATES.json',estimates)
 pvr_receipt=ENTRY/'local_observable_selection_v1/features/RUN_RECEIPT.json';pvr=json.loads(pvr_receipt.read_text())
 gate=ENTRY/'full_local_signal_20240924_v1/independent_review/SOURCE_PREFIX_GATE.json'
 save('EXISTING_REUSE_EVIDENCE.json',dict(run_bindings=bindings,
     original_PVR_vector_export=dict(path=str(pvr_receipt),sha256=sha(pvr_receipt),elapsed_seconds=pvr['elapsed_seconds'],
       workers=3,source_rows_processed_once=N,output_saved_target_rows=pvr['rows'],dates=pvr['dates'],
       full_prefix_internal_frames_were_not_persisted_as_daily_cache=True),
     bounded_E0_prefix_gate=dict(path=str(gate),sha256=sha(gate),contents=json.loads(gate.read_text())),
     current_caches_not_complete_daily_sequence=True,no_models_run_in_this_review=True))
 stage=ENTRY/'e0_stage_pvr_v1';generation=json.loads((stage/'GENERATION_RECEIPT.json').read_text())
 pilot=json.loads((stage/'PILOT_RECEIPT.json').read_text());stage_binding=json.loads((stage/'SOURCE_BINDING.json').read_text())
 stage_records=[];pilot_records=[]
 for receipt,destination in [(generation,stage_records),(pilot,pilot_records)]:
  for job in receipt['jobs']:
   assert sha(job['file'])==job['sha256']
   destination.extend(json.loads(s)for s in Path(job['file']).read_text().splitlines())
 assert len({(r['sid'],r['day'])for r in stage_records+pilot_records})==3287
 event_eligible=sum(r.get('eligible_rows',0)for r in stage_records)
 assert event_eligible==9470899
 research=stage/'research.py';assert sha(research)==stage_binding['files'][str(research)]
 save('EVENT_STAGE_MEASURED_COST.json',dict(
    generation_receipt_path=str(stage/'GENERATION_RECEIPT.json'),generation_receipt_sha256=sha(stage/'GENERATION_RECEIPT.json'),
    stage_source_binding_sha256=sha(stage/'SOURCE_BINDING.json'),research_current_matches_generation_binding=True,
    research_sha256=sha(research),
    output_total_requests=generation['rows'],output_total_exact=generation['exact_checked'],
    full_new_requests=len(stage_records),full_new_complete=sum(r['status']=='COMPLETE'for r in stage_records),
    full_new_eligible_rows=event_eligible,full_new_wall_seconds=generation['wall_seconds'],workers=10,
    pilot_requests=len(pilot_records),pilot_eligible_rows=sum(r.get('eligible_rows',0)for r in pilot_records),pilot_wall_seconds=pilot['wall_seconds'],
    original_eight_fields_match_count=generation['exact_checked'],
    complete_source_prefix_light_chain_wall_seconds_extrapolated_at10workers=N/event_eligible*generation['wall_seconds'],
    separate_numeric_only_profile_still_not_available=True,
    this_timing_is_numeric_plus_light_E0_stage_replay_not_full_B4_G1_I=True,
    full_daily_frame_persistence_not_measured=True,
    already_saved_three_date_stages_reusable=True,
    lighter_chain_estimate_does_not_replace_full_G1_I_daily_cohort_cost=True,
    new_models_in_this_review=0))
 expected=json.loads((ENTRY/'no_future_cap_selection_v1/target_signal_completion/FREEZE.json').read_text())['original_algorithm_code_sha256']
 inventory=[]
 for p,h in expected.items():
  assert sha(p)==h;inventory.append(dict(path=p,sha256=h,matches_existing_frozen_original=True))
 save('ORIGINAL_SOURCE_IDENTITY.json',inventory)
 excerpts=[]
 specs=[(ENTRY/'selection_qualification_closeout_v1/eligibility_source/stock_signal.py',[(18,55)]),
  (RR/'pv-participation-response-20261020/code/numeric.py',[(15,55),(58,136)]),
  (RR/'pv-participation-response-20261020/code/participation.py',[(17,32),(100,107)]),
  (RR/'pv-strength-b5-20261025/code/evidence.py',[(92,157),(184,199),(227,234)]),
  (RR/'pv-strength-b4-20261025/code/model.py',[(42,44),(85,93),(163,175),(279,290)]),
  (RR/'pv-strength-b5-20261025/code/policy.py',[(43,52),(124,134),(164,171)]),
  (RR/'b5-g1-20261025/code/grade.py',[(13,28),(44,61)]),
  (RR/'b5-g1-20261025/code/policies_g1.py',[(6,34)]),
  (ENTRY/'local_observable_selection_v1/features/derive.py',[(14,31),(44,51),(65,78)])]
 for p,ranges in specs:
  text=p.read_text().splitlines();excerpts.append(str(p)+'\nSHA256 '+sha(p))
  for lo,hi in ranges:excerpts.append('\n'.join(f'{i:5d} {text[i-1]}'for i in range(lo,min(hi,len(text))+1)))
 (HERE/'SOURCE_EXCERPTS.txt').write_text('\n\n'.join(excerpts)+'\n')
 print(json.dumps(dict(timings=timing,estimates=estimates),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
