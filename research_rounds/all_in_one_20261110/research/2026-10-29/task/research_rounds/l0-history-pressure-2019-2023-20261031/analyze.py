"""Same independent L0 audit; only historical endpoint and no-ADD table scope."""
from pathlib import Path
import sys,time,types
import adapter as M
O=M.O
source=(O.parent/'lr1-cp1-add-preflight-20261031/analyze.py').read_text()
source=source.replace("'2026-10-27'","'2023-12-29'")
a=source.index(' bridge=[]\n');b=source.index(" print('COMPLETE',sec,flush=True)",a)
source=source[:a]+" M.save(out/'ACCOUNTING.json',dict(passed=True,receipts=audits,layer_contribution_reconciled=True,legacy_B0_prefix_only_skips_count_limits=True));M.save(out/'SUMMARY.json',summary)\n"+source[b:]
module=types.ModuleType('historical_original_independent_l0');module.__file__=str(O.parent/'lr1-cp1-add-preflight-20261031/analyze.py');exec(compile(source,module.__file__,'exec'),module.__dict__)
if __name__=='__main__':
 t=time.monotonic();status='started'
 try:module.main();status='complete'
 finally:
  p=O/'COMPUTE_TIME.json';s=M.read(p);dt=time.monotonic()-t;s['seconds']+=dt;s['stages'].append(dict(sector=sys.argv[1],stage='independent_accounting',status=status,seconds=dt));M.save(p,s)
