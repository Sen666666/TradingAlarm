"""Bounded selection diagnostic after strict unknown-score stop; no quote reads."""
from pathlib import Path
import ast,gzip,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
old=O/'freeze_true_pvr_samples.py'
s=old.read_text()
s=s[:s.index('samples=[];full=[]')]
exec(compile(s,str(old),'exec'))
results=[]
for d,group in rows.items():
    known=[dict(r,PVR_score=scores[r['sid'],d])for r in group if(r['sid'],d)in scores]
    unknown=[r for r in group if(r['sid'],d)not in scores]
    ordered=sorted(known,key=lambda r:(-r['PVR_score'],r['sid']))
    results.append(dict(day=d,next_OPEN=days[d],retained_fresh_mobile=len(group),PVR_known=len(known),PVR_unknown=len(unknown),
        unknown_rows=unknown,provisional_highest_defined_PVR=ordered[0],strict_all_known_selection_pass=not unknown))
out=dict(status='UNKNOWN_SELECTION_STRICT_STOP',before_sample_price_read=True,
    reason='Strict v1 prerequisite all retained PVR known failed. Preserve first H1 mislabeled freeze; no replacing unknown score with zero and no execution-price probing.',
    results=results,sources=sources,strict_failed_source_sha256=sha(old),this_source_sha256=sha(__file__),
    original_score_missing_behavior='Native priority_plan preserves missing-score original H1 slots. Highest defined score is not automatically first native priority.',
    new_accounts=0,indicators_recomputed=0,sample_execution_prices_read=0)
(O/'PVR_SELECTION_UNKNOWN_STOP.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':out['status'],'byday':[{k:v for k,v in r.items()if k!='unknown_rows'}for r in results]},ensure_ascii=False,indent=2))
