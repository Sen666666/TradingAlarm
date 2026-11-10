from pathlib import Path
import json,hashlib,ast
import pandas as pd
from priority import reorder
O=Path(__file__).resolve().parent;E=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def row(i,p,k,e):return dict(event_id=str(i),sid=str(i),PVR_score=p,relative_known=k,relative_event=e)
r=[row(0,9,True,0),row(1,8,False,1),row(2,7,True,1),row(3,6,True,0)]
f={x['event_id'] for x in r}
assert [x['event_id'] for x in reorder(r,f,True)]==['2','1','0','3']
assert [x['event_id'] for x in reorder(r,f,False)]==['0','1','2','3']
assert [x['event_id'] for x in reorder(r,{'0','1','3'},True)]==['0','1','2','3']
for known in [True,False]:
 rr=[row(0,9,known,0),row(1,8,known,0)]
 assert [x['event_id'] for x in reorder(rr,{'0','1'},True)]==['0','1']
rr=[row(0,9,True,0),row(1,8,True,0),row(2,7,True,1)]
assert len(reorder(rr,{'0','1','2'},True))==3
# Original execution and state-management functions are byte-for-byte AST identical.
a=ast.parse((E/'lifecycle_v1/simulate.py').read_text());b=ast.parse((O/'simulate.py').read_text())
fa={n.name:ast.dump(n) for n in a.body if isinstance(n,ast.FunctionDef)};fb={n.name:ast.dump(n) for n in b.body if isinstance(n,ast.FunctionDef)}
for name in fa:
 if name!='run_window':assert fa[name]==fb[name],name
coverage=E/'relative_m3_cache_v1/coverage_upper_bound_v1/EVENT_COVERAGE.csv'
c=pd.read_csv(coverage,usecols=['event_id','relative_known','relative_event'])
e=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',usecols=['event_id','event_type']);e=e[e.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
assert len(c)==20445 and set(c.event_id)==set(e.event_id) and not c.event_id.duplicated().any()
# Frozen original input manifest includes per-stock OHLC/facts/CP data.
hashes=json.loads((E/'lifecycle_v1/SOURCE_HASHES.json').read_text())
for p,h in hashes.items():assert sha(p)==h,('original drift',p)
extra=[coverage,E/'relative_m3_cache_v1/clock_model.py',E/'relative_m3_cache_v1/coverage_upper_bound_v1/run_coverage_clock.py',E/'entry_quality_2022_v1/decompose_core.py']+list(O.glob('*.py'))+[O/'PROTOCOL.json',O/'ORIGINAL_DIFF.patch']
hashes.update({str(p):sha(p) for p in extra})
(O/'SYNTHETIC_QA.json').write_text(json.dumps(dict(passed=True,tests=['unknown_exact_slot','baseline_identity','infeasible_not_promoted','all_non_up_retained','all_unknown_identity','no_filtering','management_AST_identical','causal_join_20445'],unchanged_functions=sorted(set(fa)-{'run_window'})),indent=2)+'\n')
assert not (O/'FREEZE.json').exists()
(O/'FREEZE.json').write_text(json.dumps(dict(created_utc=str(pd.Timestamp.now(tz='UTC')),no_new_economic_results=True,hashes=hashes),indent=2)+'\n')
print('PREPARED',len(hashes),'frozen inputs/code files')
