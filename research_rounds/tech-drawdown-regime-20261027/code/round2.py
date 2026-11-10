from pathlib import Path
import sys,json,hashlib
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';NR=ROOT/'research_rounds/e0-reclaim-accounts-20261026/prepared';sys.path.insert(0,str(BASE/'code'))
import pandas as pd,numpy as np
import run_v2 as runner
import engine
import analyze_v2 as audit
VERSIONS=['JOINT','JOINT_BLOCK','JOINT_SLOW','G1_JOINT']
if __name__=='__main__':
 stage=sys.argv[1]
 if stage=='prepare':
  gates=pd.read_csv(O/'signals-v1/market-gates.csv',index_col=0,parse_dates=True)
  for v in VERSIONS:
   root=O/v/'prepared';(root/'facts').mkdir(parents=True,exist_ok=False);(root/'h1.npz').symlink_to(BASE/'prepared-v2/h1.npz')
  for path in sorted((NR/'facts').glob('*.parquet')):
   f=pd.read_parquet(path);sid=path.stem;tr=O/'diagnostic-v1/traces'/path.name
   for v in VERSIONS:
    z=f.copy()
    if tr.exists():
     m=pd.read_parquet(tr).m.reindex(f.index);fast=gates.m21.reindex(f.index).fillna(False);slow=gates.m63.reindex(f.index).fillna(False);weak=(~f.g_grade.ge(2)) if v=='G1_JOINT' else (~m.ge(0));exit_now=(~fast)&weak
     z['i_target']=z.i_target&~exit_now;z['i_buy']=z.i_buy&~exit_now
     if v=='JOINT_BLOCK':z['i_buy']=z.i_buy&fast
     if v=='JOINT_SLOW':z['i_buy']=z.i_buy&slow
    z.to_parquet(O/v/'prepared/facts'/path.name)
  # Exact contemporaneous prepared-row rule contract, no account outcomes used.
  n=0
  for path in sorted((O/'JOINT/prepared/facts').glob('*.parquet')):
   tr=O/'diagnostic-v1/traces'/path.name
   if not tr.exists():continue
   f=pd.read_parquet(NR/'facts'/path.name);m=pd.read_parquet(tr).m.reindex(f.index);fast=gates.m21.reindex(f.index).fillna(False);expected=f.i_target & (fast | m.ge(0));z=pd.read_parquet(path);assert z.i_target.equals(expected);n+=len(z)
  (O/'round2-prepared-check.json').write_text(json.dumps({'passed':True,'rows':n,'causal_inputs':'round1 three full-pool physical prefixes plus original frozen G1'},indent=2));print('round2 prepared',n);raise SystemExit
 if stage=='economic':
  for v in VERSIONS:assert json.loads((O/v/'technical/short-analysis/accounting.json').read_text())['passed']
  files=[O/'ROUND2_RULES.md',O/'round2-prepared-check.json',Path(__file__),*sorted((BASE/'code').glob('*.py'))];f=O/'round2-freeze.json';assert not f.exists();f.write_text(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files},indent=2))
 for v in VERSIONS:
  root=O/v;prep=root/'prepared';runner.PREP=prep;engine.PREP=prep;audit.PREP=prep;audit.HERE=root
  rp=root/'execution-rules-v2.json'
  if not rp.exists():rp.symlink_to(BASE/'execution-rules-v2.json')
  if stage in ['short','economic']:
   out=root/('technical/short-v2' if stage=='short' else 'accounts-v2');assert not out.exists();runner.run(out,modes=['I'],end='2024-03-29' if stage=='short' else '2026-10-26',technical=stage=='short');audit.main('short' if stage=='short' else 'full')
  elif stage=='prefix':runner.run(root/'technical/prefix',modes=['I'],end='2025-12-31',cutoff='2025-12-31',technical=True)
  else:raise ValueError(stage)
