"""Read durable journals; no model/account/data-source read."""
from pathlib import Path
import json,time
HERE=Path(__file__).resolve().parent

def main():
 rows=[];active_partial_lines=0
 for p in(HERE/'full').glob('*.jsonl'):
  for line in p.read_text().splitlines():
   try:rows.append(json.loads(line))
   except json.JSONDecodeError:active_partial_lines+=1
 elapsed=time.time()-(HERE/'full/BLOCK_PLAN.json').stat().st_mtime
 done=sum(r['input_prefix_rows']for r in rows if r.get('model_invoked'))
 total=json.loads((HERE/'PILOT_SUMMARY.json').read_text())['remaining_model_prefix_rows']
 result=dict(new_persisted=len(rows),reused_prior_and_pilot=124,full_symbols=5393,
    errors=sum(r['signal_status']=='SOURCE_OR_PURE_SIGNAL_ERROR'for r in rows),
    missing=sum(r['signal_status']=='MISSING_TARGET_BAR'for r in rows),
    model_prefix_done=done,model_prefix_total=total,elapsed_minutes=elapsed/60,
    estimated_remaining_minutes=(total-done)/done*elapsed/60 if done else None,
    incomplete_live_line_not_counted=active_partial_lines,
    complete_table_exists=(HERE/'COMPLETION.json').exists())
 (HERE/'LIVE_PROGRESS.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)

if __name__=='__main__':main()
