"""Full raw-signal recomputation audit, physically truncated at each clock cut."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,json,time,hashlib,ast,inspect
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;M=Path('/Users/bytedance/Documents/ChatGPT/money');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');P=Path(json.load(open(M/'TradingAlarm/runtime/market/current.json'))['path'])
sys.path.insert(0,str(M));from TradingAlarm.desk.refresh import prepare_facts
# Compile the exact existing prepare_facts body, only returning B5 evidence too.
# This changes no market algorithm, state, or source file.
source=inspect.getsource(prepare_facts);tree=ast.parse(source);fn=tree.body[0];assert isinstance(fn.body[-1],ast.Return);fn.body[-1].value=ast.Tuple(elts=[ast.Name(id='keep',ctx=ast.Load()),ast.Subscript(value=ast.Name(id='z',ctx=ast.Load()),slice=ast.Constant(value='evidence'),ctx=ast.Load())],ctx=ast.Load());ast.fix_missing_locations(tree);env=prepare_facts.__globals__.copy();exec(compile(tree,'<exact_prepare_facts_with_evidence>','exec'),env);rebuild=env['prepare_facts']
sm={x['symbol']:x for x in json.load(open(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
sector=next(x for x in json.load(open(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')) if x['series']=='URFI881121')
def exact(a,b):
 a=a.copy(deep=False);b=b.copy(deep=False);a.index=a.index.as_unit('ns');b.index=b.index.as_unit('ns');pd.testing.assert_frame_equal(a,b,check_exact=True,check_dtype=False,check_freq=False)
def one(sid):
 t=time.monotonic();signal=pd.read_parquet(P/'signals'/(sid+'.parquet'));orig=pd.read_parquet(P/'facts'/(sid+'.parquet'));q=pd.read_parquet(sector['refs']['CP1_input'] if sid.startswith('URFI') else sm[sid]['refs']['CP1_input']);checks=[]
 for cut in ['2025-12-31','2026-05-15','2026-06-30']:
  s=signal.loc[:cut]
  if s.empty:continue
  f,e=rebuild(s);exact(f,orig.loc[:cut]);qq=q.loc[:cut]
  exact(e[['event']].reindex(qq.index).eq(-1).rename(columns={'event':'e0_down'}),qq[['e0_down']])
  if sid.startswith('URFI'):
   np.testing.assert_equal(f.e0_target.astype(bool).to_numpy(),qq.e0_valid.to_numpy())
   np.testing.assert_allclose(f.e0_floor,qq.i_floor,rtol=0,atol=0,equal_nan=True)
  else:
   exact(f,pd.read_parquet(sm[sid]['refs']['facts']).loc[:cut])
   np.testing.assert_equal(f.i_target.astype(bool).to_numpy(),qq.e0_valid.to_numpy())
  checks.append(cut)
 return dict(sid=sid,status='PASS',physical_raw_OHLC_cuts=checks,native_down_exact=True,E0_I_all_fields_exact=True,seconds=time.monotonic()-t)
if __name__=='__main__':
 start=time.monotonic();ids=pd.read_csv(O/'COVERAGE.csv').query('H1_rows > 0').sid.tolist()+['URFI881121'];assert len(ids)==121
 (O/'RAW_AUDIT_FREEZE.json').write_text(json.dumps(dict(ids=ids,cuts=['2025-12-31','2026-05-15','2026-06-30'],workers=4,expected_wall_seconds=180,budget_wall_seconds=360,code_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),method='Exact production prepare_facts body recomputed from physically truncated signal OHLC, with evidence returned to verify native-down event. No source changes. Causal signal factors already independently exact.'),indent=2))
 out=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for r in pool.map(one,ids):
   out.append(r)
   if len(out)%20==0:print('RAW',len(out),round(time.monotonic()-start,1),flush=True)
   if time.monotonic()-start>360:raise TimeoutError('raw audit bounded at 360 seconds')
 pd.DataFrame(out).to_csv(O/'RAW_CLOCK_EXACT_AUDITS.csv',index=False)
 (O/'RAW_AUDIT_RESULT.json').write_text(json.dumps(dict(status='PASS',stocks=120,sectors=1,clock_cuts=['2025-12-31','2026-05-15','2026-06-30'],seconds=time.monotonic()-start,exact_source_hash=hashlib.sha256(inspect.getsource(prepare_facts).encode()).hexdigest(),code_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),all_checks=out),indent=2));print('RAW COMPLETE',len(out),time.monotonic()-start,flush=True)
