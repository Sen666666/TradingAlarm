from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];R=O.parents[1];BASE=R/'research_rounds/tech-finite-compound-20261026'
sys.path.insert(0,str(BASE/'code'))
import run_v2 as runner
import engine
import analyze_v2 as audit
if __name__=='__main__':
 name,stage=sys.argv[1:3]
 if stage=='economic':
  assert (O/name/'GRAPH_REVIEW.md').exists()
  for p in ['H','C']:assert json.loads((O/name/p/'technical/short-analysis/accounting.json').read_text())['passed']
  files=[O/'DESIGN.md',O/name/'GRAPH_REVIEW.md',O/name/'input-audit.csv',*sorted((O/'code').glob('*.py')),*sorted((BASE/'code').glob('*.py'))]
  (O/name/'freeze.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
 for pol in ['H','C']:
  root=O/name/pol;prep=root/'prepared';runner.PREP=prep;engine.PREP=prep;audit.PREP=prep;audit.HERE=root
  rp=root/'execution-rules-v2.json'
  if not rp.exists():rp.symlink_to(BASE/'execution-rules-v2.json')
  if stage in ['short','economic']:
   out=root/('technical/short-v2' if stage=='short' else 'accounts-v2');assert not out.exists()
   runner.run(out,modes=['I'],end='2024-03-29' if stage=='short' else '2026-10-26',technical=stage=='short');audit.main('short' if stage=='short' else 'full')
  elif stage=='prefix':runner.run(root/'technical/prefix',modes=['I'],end='2024-12-31',cutoff='2024-12-31',technical=True)
  else:raise ValueError(stage)
