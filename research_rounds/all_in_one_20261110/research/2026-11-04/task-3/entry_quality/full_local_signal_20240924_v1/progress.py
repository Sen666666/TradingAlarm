"""Read-only view of durable per-stock results; does not invoke models."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,time

HERE=Path(__file__).resolve().parent
b=HERE/'signals';allrows={};full={}
for group,paths in [('reuse',[b/'REUSED110.jsonl']),('pilot',list((b/'pilot').glob('block_*_part_*.jsonl'))),('full',list((b/'full').glob('block_*_part_*.jsonl')))]:
    for p in paths:
        for line in p.read_text().splitlines():
            try:r=json.loads(line)
            except json.JSONDecodeError:continue  # a currently-being-written tail is not completed
            allrows[r['sid']]=r
            if group=='full':full[r['sid']]=r
work=sum(r.get('input_prefix_rows',0) for r in full.values() if r.get('model_invoked'))
plan=b/'full/BLOCK_PLAN.json';elapsed=time.time()-plan.stat().st_mtime
total=json.loads((b/'PILOT_SUMMARY.json').read_text())['remaining_model_prefix_rows']
z=dict(at_UTC=datetime.now(timezone.utc).isoformat(),durable_unique=len(allrows),total_requests=5517,
    statuses=dict(Counter(r['signal_status']for r in allrows.values())),new_full_durable=len(full),
    full_model_prefix_observations=work,full_model_prefix_total=total,
    elapsed_full_minutes=round(elapsed/60,2),
    estimated_remaining_minutes_from_prefix_rate=round((total-work)*elapsed/work/60,1)if work else None)
with(HERE/'PROGRESS_SNAPSHOTS.jsonl').open('a')as f:f.write(json.dumps(z)+'\n')
print(json.dumps(z,ensure_ascii=False),flush=True)
