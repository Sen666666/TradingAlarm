"""No inputs, Account construction, restore, or financial events."""
from pathlib import Path
import json,sys
OUT=Path(__file__).resolve().parent
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
import native_adapter as A
r=object.__new__(A.Runner)
expected=json.loads((A.O/'runs/2025_26/checkpoint-2025-12-31.provenance.json').read_text())['engine_identity']
with A.IO.atomic_runner_outputs(r,A.L,OUT/'identity_only',canonicalize=A.J.W.canon):actual=A.IO.runner_identity(r)
def diffs(x,y,path=''):
 if isinstance(x,dict) and isinstance(y,dict):
  return sum((diffs(x.get(k),y.get(k),path+'/'+k)for k in sorted(set(x)|set(y))),[])
 return []if x==y else [dict(field=path,expected=x,actual=y)]
record=dict(expected=expected,actual=actual,differences=diffs(expected,actual),inputs_loaded=False,account_constructed=False,restore_attempted=False)
p=OUT/('ENGINE_IDENTITY_PY'+str(sys.version_info.major)+str(sys.version_info.minor)+'.json');p.write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(p,record['differences'])
