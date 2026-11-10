"""Read durable two-date signal progress only; never invokes models."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,time
HERE=Path(__file__).resolve().parent
rows=[]
for day in ['2022-01-24','2026-01-15']:
    b=HERE/day/'signals';freeze=b/'FREEZE.json'
    if not freeze.exists():rows.append(dict(day=day,status='NOT_STARTED'));continue
    f=json.loads(freeze.read_text());saved={};fresh={}
    paths=[b/'REUSED_TARGETS.jsonl']+list((b/'full').glob('block_*_part_*.jsonl'))
    for p in paths:
        for line in p.read_text().splitlines():
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            saved[r['sid']]=r
            if p.parent.name=='full':fresh[r['sid']]=r
    plan=b/'full/BLOCK_PLAN.json';elapsed=max(0,time.time()-plan.stat().st_mtime)if plan.exists()else 0
    if(b/'COMPLETION.json').exists():elapsed=json.loads((b/'COMPLETION.json').read_text())['full_batch_wall_seconds']
    work=sum(r.get('input_prefix_rows',0)for r in fresh.values()if r.get('model_invoked'))
    total=f['remaining_model_prefix_rows'];estimate=(total-work)*elapsed/work/60 if work else None
    timing_basis='single_invocation_wall';resume_info={}
    rp=b/'RESUME_RECEIPT.json'
    if rp.exists():
        rr=json.loads(rp.read_text());resume_seconds=max(0,time.time()-datetime.fromisoformat(rr['resume_start_UTC']).timestamp())
        delta=work-rr['old_model_prefix_done']
        estimate=(total-work)*resume_seconds/delta/60 if delta>0 else None
        timing_basis='original_plan_wall_includes_interruption'
        elapsed=(b/'COMPLETION.json').stat().st_mtime-plan.stat().st_mtime if(b/'COMPLETION.json').exists()else time.time()-plan.stat().st_mtime
        resume_info={'resumed_elapsed_minutes':round(resume_seconds/60,2),'resumed_model_prefix_done':delta}
    rows.append(dict(day=day,status='COMPLETE'if(b/'COMPLETION.json').exists()else'RUNNING',
        durable_unique=len(saved),total_requests=5517,statuses=dict(Counter(r['signal_status']for r in saved.values())),
        new_full_durable=len(fresh),model_prefix_done=work,model_prefix_total=total,
        elapsed_minutes=round(elapsed/60,2),timing_basis=timing_basis,
        estimated_remaining_minutes=round(estimate,1)if estimate is not None else None,**resume_info))
out=dict(at_UTC=datetime.now(timezone.utc).isoformat(),dates=rows)
with(HERE/'PROGRESS_SNAPSHOTS.jsonl').open('a')as f:f.write(json.dumps(out)+'\n')
print(json.dumps(out,ensure_ascii=False),flush=True)
