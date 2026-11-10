from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';NR=ROOT/'research_rounds/e0-reclaim-accounts-20261026/prepared'
sys.path.insert(0,str(BASE/'code'));sys.path.insert(0,str(O/'code'))
import engine
import run_v2 as runner
import analyze_v2 as audit
VERSIONS=['CONTROL','ACT20_WARN']
if __name__=='__main__':
 stage=sys.argv[1];versions=sys.argv[2:] or VERSIONS
 if stage=='economic':
  for v in versions:assert json.loads((O/v/'technical/short-analysis/accounting.json').read_text())['passed']
  for p in ['synthetic-tests.json','recovery-validation.json','control-short.json']:assert json.loads((O/p).read_text())['passed']
  assert (O/'GRAPH_REVIEW.md').exists()
  fs=[O/'PROTOCOL.md',O/'GRAPH_REVIEW.md',O/'recovery.csv',*sorted((O/'code').glob('*.py')),*sorted((BASE/'code').glob('*.py'))];f=O/'freeze.json';assert not f.exists();f.write_text(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in fs},indent=2))
 for v in versions:
  root=O/v;root.mkdir(exist_ok=True);runner.PREP=NR;engine.PREP=NR;engine.RISK_MODE=v;audit.PREP=NR;audit.HERE=root
  rp=root/'execution-rules-v2.json'
  if not rp.exists():rp.symlink_to(BASE/'execution-rules-v2.json')
  if stage in ['short','economic']:
   out=root/('technical/short-v2' if stage=='short' else 'accounts-v2');assert not out.exists();runner.run(out,modes=['I'],end='2024-03-29' if stage=='short' else '2026-10-26',technical=stage=='short');audit.main('short' if stage=='short' else 'full')
  elif stage=='prefix':runner.run(root/'technical/prefix',modes=['I'],end='2026-08-31',cutoff='2026-08-31',technical=True)
  else:raise ValueError(stage)
