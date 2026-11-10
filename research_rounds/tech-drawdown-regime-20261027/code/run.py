from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';sys.path.insert(0,str(BASE/'code'))
import run_v2 as runner
import engine
import analyze_v2 as audit
VERSIONS=['CONTROL','FAST','SECTOR','MARKET_NEW','MARKET_ALL','MARKET_SLOW','MARKET_PRICE']
if __name__=='__main__':
 stage=sys.argv[1];versions=sys.argv[2:] or VERSIONS
 if stage=='economic':
  assert json.loads((O/'signal-validation.json').read_text())['passed']
  for v in versions:assert json.loads((O/v/'technical/short-analysis/accounting.json').read_text())['passed']
  files=[O/'PROTOCOL.md',O/'RULES.md',O/'GRAPH_REVIEW.md',O/'signal-validation.json',*sorted((O/'code').glob('*.py')),*sorted((BASE/'code').glob('*.py')),*sorted((O/'signals-v1').glob('*.csv'))]
  freeze=O/'economic-freeze.json';assert not freeze.exists();freeze.write_text(json.dumps({str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},indent=2))
 for v in versions:
  root=O/v;prep=root/'prepared';runner.PREP=prep;engine.PREP=prep;audit.PREP=prep;audit.HERE=root
  rp=root/'execution-rules-v2.json'
  if not rp.exists():rp.symlink_to(BASE/'execution-rules-v2.json')
  if stage in ['short','economic']:
   out=root/('technical/short-v2' if stage=='short' else 'accounts-v2');assert not out.exists();runner.run(out,modes=['I'],end='2024-03-29' if stage=='short' else '2026-10-26',technical=stage=='short');audit.main('short' if stage=='short' else 'full')
  elif stage=='prefix':runner.run(root/'technical/prefix',modes=['I'],end='2025-12-31',cutoff='2025-12-31',technical=True)
  else:raise ValueError(stage)
