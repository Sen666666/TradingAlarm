"""Only causal signal fields may enter queue ordering."""
import numpy as np
import pandas as pd
CAUSAL_COLUMNS=['event_id','relative_known','relative_event']
def istrue(x):return pd.notna(x) and x in (True,1)
def reorder(rows, feasible, relative=False):
    # rows are original PVR/sid sorted; feasible IDs already reflect live state.
    base=[r for r in rows if r['event_id'] in feasible]
    known=[r for r in base if istrue(r.get('relative_known'))]
    promoted=sorted(known,key=lambda r:(-int(r.get('relative_event')==1),-r['PVR_score'],r['sid'])) if relative else known
    it=iter(promoted)
    ordered=[next(it) if istrue(r.get('relative_known')) else r for r in base]
    old={r['event_id']:i+1 for i,r in enumerate(base)};new={r['event_id']:i+1 for i,r in enumerate(ordered)}
    for r in rows:
        eid=r['event_id'];r.update(feasible_at_ranking=eid in feasible,original_feasible_rank=old.get(eid,np.nan),new_feasible_rank=new.get(eid,np.nan),relative_unknown=not istrue(r.get('relative_known')))
    # Keep infeasible positions unchanged too; only feasible slots permute.
    it=iter(ordered)
    return [next(it) if r['event_id'] in feasible else r for r in rows]
