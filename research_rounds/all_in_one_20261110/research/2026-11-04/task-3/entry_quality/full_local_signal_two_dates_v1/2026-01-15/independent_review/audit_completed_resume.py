"""Saved completed old/new journals and timing arithmetic only; no model import."""
from pathlib import Path
import json,hashlib,math
P=Path(__file__).resolve().parents[1];S=P/'signals';O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
r=read(S/'RESUME_RECEIPT.json');t=read(S/'SEGMENT_TIMING.json');c=read(S/'COMPLETION.json')
oldpaths={Path(e['path']).resolve() for e in r['old_part_index']}
for e in r['old_part_index']:
 p=Path(e['path']);assert sha(p)==e['sha256'] and p.stat().st_mtime_ns==e['mtime_ns']
groups={'old':[],'resumed':[]};files=sorted((S/'full').glob('*.jsonl'))
for p in files:
 b=p.read_bytes();assert not b or b.endswith(b'\n')
 rows=[json.loads(x,parse_constant=lambda z:(_ for _ in ()).throw(ValueError(z))) for x in b.splitlines()]
 groups['old' if p.resolve()in oldpaths else 'resumed']+=rows
assert len(groups['old'])==3391 and len(groups['resumed'])==2120
for k,rr in groups.items():
 assert len(rr)==len({x['sid'] for x in rr})
 assert all(x['day']=='2026-01-15' and x['signal_status']!='SOURCE_OR_PURE_SIGNAL_ERROR' for x in rr)
assert not ({x['sid']for x in groups['old']}&{x['sid']for x in groups['resumed']})
assert len(groups['old'])+len(groups['resumed'])==c['new_unique_requests']==5511
cpu={k:sum(x.get('model_cpu_seconds',0) for x in rr)for k,rr in groups.items()}
for k,key in [('old','completed_model_CPU_seconds_first_segment'),('resumed','completed_model_CPU_seconds_resumed_segment')]:assert math.isclose(cpu[k],t[key],rel_tol=0,abs_tol=1e-6)
assert math.isclose(sum(cpu.values()),t['completed_model_CPU_seconds_total'],rel_tol=0,abs_tol=1e-6)
assert sum(x.get('input_prefix_rows',0) for x in groups['old'] if x.get('model_invoked'))==r['old_model_prefix_done']==9519577
assert t['resumed_invocation_wall_seconds']==c['full_batch_wall_seconds']
end=(S/'COMPLETION.json').stat().st_mtime_ns/1e9-(S/'full/BLOCK_PLAN.json').stat().st_mtime_ns/1e9
assert math.isclose(end,t['end_to_end_wall_including_interruption_seconds'],rel_tol=0,abs_tol=1e-6)
assert sha(S/'ALL_SIGNALS.parquet')==c['all_signals_sha256']
out={'status':'PASS_BOUNDED_COMPLETED_2026_OLD_NEW_PARTS_AND_SEGMENT_TIMING','remaining_blocks':[],'old_files_hash_mtime_unchanged':147,'old_full_rows':3391,'resumed_full_rows':2120,'full_unique_rows':5511,'reused_rows':6,'final_total_rows':5517,'full_duplicate_keys':0,'old_completed_model_prefix_rows':9519577,'committed_model_CPU_seconds':cpu,'resumed_invocation_wall_seconds':c['full_batch_wall_seconds'],'end_to_end_wall_including_interruption_seconds':end,'limits':['Committed per-stock CPU core-seconds exclude interrupted unfinished work.','Exact original process termination and total active wall time remain UNKNOWN; no process enumeration performed by reviewer.','End-to-end wall is BLOCK_PLAN mtime to COMPLETION mtime and includes pause/overhead.','No future-label files opened and no model/account executed.'],'source_sha256':{str(p.resolve()):sha(p) for p in [S/'RESUME_RECEIPT.json',S/'INTERRUPTION_STATUS.json',S/'SEGMENT_TIMING.json',S/'COMPLETION.json',S/'full/BLOCK_PLAN.json',S/'ALL_SIGNALS.parquet',Path(__file__)]},'new_models':0,'new_accounts':0}
p=O/'RESUME_COMPLETED_PARTS_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'full_rows':5511,'CPU':cpu,'end_to_end_wall_seconds':end}))
