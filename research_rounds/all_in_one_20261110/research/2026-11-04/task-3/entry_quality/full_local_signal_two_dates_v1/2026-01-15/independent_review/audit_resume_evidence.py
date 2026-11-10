"""Saved interruption/resume evidence only: no producer/model import or execution."""
from pathlib import Path
import json,csv,hashlib,re,ast
P=Path(__file__).resolve().parents[1]; S=P/'signals'; R=P.parent; O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def rows(p):
 b=Path(p).read_bytes()
 assert not b or b.endswith(b'\n'),('truncated',p)
 return [json.loads(x,parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s))) for x in b.splitlines()]
f=read(S/'FREEZE.json');r=read(S/'RESUME_RECEIPT.json');i=read(S/'INTERRUPTION_STATUS.json')
assert f['day']=='2026-01-15' and f['universe_symbols']==5517
code={str(R/'run_two_dates.py'):f['date_wrapper_sha256'],f['immutable_worker_driver_path']:f['immutable_worker_driver_sha256'],**f['original_algorithm_code_sha256']}
assert len(f['original_algorithm_code_sha256'])==11
for p,h in code.items():assert sha(p)==h,('code changed',p)
source=Path(f['source_path']); stat=source.stat()
assert stat.st_size==f['source_bytes'] and stat.st_mtime_ns==f['source_mtime_ns']
assert sha(S/'REUSED_TARGETS.jsonl')==f['reused_jsonl_sha256']
assert sha(S/'UNIVERSE5517.csv')==f['universe_sha256']
reuse=rows(S/'REUSED_TARGETS.jsonl'); assert len(reuse)==6 and {x['sid'] for x in reuse}==set(f['reused_ids'])
roster=list(csv.DictReader((S/'UNIVERSE5517.csv').open()));assert len(roster)==len({x['sid'] for x in roster})==5517
plan=read(S/'full/BLOCK_PLAN.json');assert plan['day']==f['day'] and plan['stage']=='full'
flat=[s for b in plan['blocks'] for s in b]
assert len(flat)==len(set(flat))==5511 and set(flat)=={x['sid'] for x in roster}-set(f['reused_ids'])
old=[];index=r['old_part_index']; assert len(index)==147
for e in index:
 p=Path(e['path']);assert sha(p)==e['sha256'],('old part changed',p)
 assert p.stat().st_mtime_ns==e['mtime_ns'],('old mtime changed',p)
 rr=rows(p);assert len(rr)==e['rows'] and [x['sid'] for x in rr]==e['symbols']
 bid=int(re.search(r'block_(\d+)_part_',p.name)[1]);assert set(e['symbols'])<=set(plan['blocks'][bid])
 for x in rr:
  assert x['day']==f['day'] and x['source_sha256']==f['source_sha256']
  assert x.get('prefix_end_day') is None or x['prefix_end_day']<=f['day']
  if x['signal_status']=='EXACT_TARGET_STOCK_SIGNAL':assert x['prefix_end_day']==f['day']
  assert x['signal_status']!='SOURCE_OR_PURE_SIGNAL_ERROR'
 old+=rr
assert len(old)==len({x['sid'] for x in old})==r['old_full_durable']==3391
assert not ({x['sid'] for x in old}&set(f['reused_ids']))
assert len(old)+len(reuse)==r['old_unique_durable']==i['durable_unique']==3397
# Inspect stable source text, not import producer or calculate.
w=(R/'run_two_dates.py').read_text();m=Path(f['immutable_worker_driver_path']).read_text();ast.parse(w);ast.parse(m)
assert "if(out/'COMPLETION.json').exists():" in w and "assert resume,'Explicit --resume required for partial date'" in w
assert "existing=sorted(directory.glob(prefix+'*.jsonl'))" in m and "pending=[s for s in symbols if s not in done]" in m
assert "target.open('x')" in m and "os.fsync(stream.fileno())" in m
assert "ds.field('trade_date')<=pd.Timestamp(DAY)" in m
out={'status':'PASS_BOUNDED_2026_RESUME_OLD_PARTS_AND_CODE_IDENTITY','remaining_final_output_audit':'PENDING_COMPLETE_5517_AND_ROOT_OUTPUTS','checks':{'old_part_files_hash_mtime_rows_keys_exact':len(index),'old_full_rows_unique':len(old),'reused_rows':len(reuse),'old_total_durable':3397,'old_duplicate_or_truncated_rows':0,'planned_full_symbols':len(flat),'planned_blocks':len(plan['blocks']),'original_code_files_hash_exact':11,'wrapper_and_immutable_worker_hash_exact':True,'old_prefix_dates_no_future':True,'source_stat_matches_freeze':True},'runtime_semantics':{'resume_skips_persisted_ids_including_errors':True,'new_parts_exclusive_create':True,'stock_completion_flush_fsync':True,'same_day_physical_input_filter':True,'new_session_execution_not_initiated_by_reviewer':True,'original_process_termination_time':'UNKNOWN','process_absence':'Reported by parent controlled read-only ps; reviewer did not enumerate OS processes','timing':'Completion full_batch_wall_seconds is resumed invocation only; final segmented timing remains producer responsibility'},'limits':['No model/Account/Runner imported or run.','Current actively written new parts not scanned; complete all-parts to raw5517 merge audit is pending.','Canonical source full SHA not rehashed here; code SHA, frozen source identity and current size/mtime checked.'],'source_sha256':{str(p):sha(p) for p in [S/'FREEZE.json',S/'RESUME_RECEIPT.json',S/'INTERRUPTION_STATUS.json',S/'full/BLOCK_PLAN.json',S/'UNIVERSE5517.csv',S/'REUSED_TARGETS.jsonl']},'code_sha256':code,'new_models':0,'new_accounts':0}
(O/'RESUME_EVIDENCE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':out['status'],'counts':out['checks'],'audit_sha256':sha(O/'RESUME_EVIDENCE_AUDIT.json')},ensure_ascii=False))
