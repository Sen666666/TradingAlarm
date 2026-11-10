from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];R=O.parents[1];BASE=R/'research_rounds/tech-finite-compound-20261026'
sys.path.insert(0,str(BASE/'code'))
import run_v2 as runner
import engine
import analyze_v2 as audit
ORIG=BASE/'prepared-v2'
def setup(version):
 p=ORIG if version=='ON' else O/'prepared'
 runner.PREP=p;engine.PREP=p;audit.PREP=p;audit.HERE=O/version
 root=O/version;root.mkdir(exist_ok=True)
 rules=root/'execution-rules-v2.json'
 if not rules.exists():rules.symlink_to(BASE/'execution-rules-v2.json')
 if version=='OFF':
  h=p/'h1.npz'
  if not h.exists():h.symlink_to(ORIG/'h1.npz')
 return root
if __name__=='__main__':
 stage=sys.argv[1]
 if stage=='economic':
  assert (O/'ON/technical/short-analysis/summary.csv').exists() and (O/'OFF/technical/short-analysis/summary.csv').exists()
  files=[O/'PROTOCOL.md',O/'prepare-audit.csv',*sorted((O/'code').glob('*.py')),*sorted((BASE/'code').glob('*.py'))]
  (O/'freeze.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
 for version in ['ON','OFF']:
  root=setup(version)
  if stage in ['short','economic']:
   out=root/('technical/short-v2' if stage=='short' else 'accounts-v2');assert not out.exists()
   runner.run(out,modes=['E0','I'],end='2024-03-29' if stage=='short' else '2026-10-26',technical=stage=='short')
   audit.main('short' if stage=='short' else 'full')
  elif stage=='prefix':runner.run(root/'technical/prefix',modes=['E0','I'],end='2024-12-31',cutoff='2024-12-31',technical=True)
  else:raise ValueError(stage)
