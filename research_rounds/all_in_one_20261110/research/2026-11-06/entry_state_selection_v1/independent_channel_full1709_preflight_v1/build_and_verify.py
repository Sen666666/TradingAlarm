"""Mechanical performance translation; no market logic or parameters changed."""
from pathlib import Path
import ast,hashlib,json,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent/'independent_channel_probe_preflight_v1'
sys.path.insert(0,str(O))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 s=(P/'core.py').read_text();n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='simulate');s=ast.get_source_segment(s,n)
 changes=[(' rows=[];root=None;last_failure=None;segment_start=None;lastid=None',' close=q.close.to_numpy(float);high=q.high.to_numpy(float);low=q.low.to_numpy(float);amount=q.amount.to_numpy(float);av=q.amount_valid.to_numpy(bool)\n rows=[];root=None;last_failure=None;segment_start=None;lastid=None'),(' for j,(d,r) in enumerate(q.iterrows()):',' for j,r in enumerate(q.itertuples()):\n  d=r.Index'),('q.close.iloc[astart:j].to_numpy(float)','close[astart:j]'),('q.high.iloc[j-20:j].max()','np.max(high[j-20:j])'),('q.close.iloc[a]','close[a]'),('q.amount.iloc[a-21:a].median()','np.median(amount[a-21:a])'),('q.amount_valid.iloc[a-21:a].all()','av[a-21:a].all()'),('q.close.iloc[k]','close[k]'),('q.amount_valid.iloc[k]','av[k]'),('q.amount.iloc[k]','amount[k]'),('q.low.iloc[a:j+1].min()','np.min(low[a:j+1])')]
 for before,after in changes:
  assert s.count(before)==1,(before,s.count(before));s=s.replace(before,after)
 s='"""Mechanically translated frozen core; only access/iteration optimized."""\nimport numpy as np\nimport pandas as pd\n\n'+s+'\n'
 (O/'fast_core.py').write_text(s)
 (O/'TRANSLATION.json').write_text(json.dumps(dict(original_sha256=sha(P/'core.py'),optimized_sha256=sha(O/'fast_core.py'),exact_replacements=changes),indent=2))
def main():
 build()
 import engine
 from fast_core import simulate as fast
 core={};exec((P/'core.py').read_text(),core);original=core['simulate']
 checks=[];t=time.monotonic()
 for sid in ['300085.SZ','002583.SZ','300666.SZ','600096.SH','300529.SZ']:
  q=engine.data(sid);a=original(q);b=fast(q);pd.testing.assert_frame_equal(a,b,check_exact=True)
  checks.append(dict(sid=sid,full_warm_rows=len(q),all_columns_exact=True,births=int(a.born.sum()),receipts=int(a.receipt.sum())))
  print('EXACT_FULL_WARM',checks[-1],flush=True)
 # Execute existing synthetic checks after replacing only simulate binding with parity wrapper.
 syn=(P/'independent_synthetic_audit.py').read_text();needle='simulate=ns["simulate"];perm=ns["execution_permission"]'
 assert needle in syn
 counts={'calls':0,'rows':0}
 def parity(q):
  a=original(q);b=fast(q);pd.testing.assert_frame_equal(a,b,check_exact=True);counts['calls']+=1;counts['rows']+=len(q);return b
 syn=syn.replace(needle,'simulate=parity;perm=ns["execution_permission"]')
 ns={'parity':parity,'__name__':'__verification__'};exec(compile(syn,str(P/'independent_synthetic_audit.py')+':parity','exec'),ns)
 # True raw-input prefix truncations at fixed window boundaries, original and optimized exact.
 prefix=[]
 for sid in ['300085.SZ','002583.SZ','300666.SZ','600096.SH','300529.SZ']:
  full=fast(engine.data(sid))
  for cut in ['2022-01-01','2022-12-31','2024-09-01','2024-12-31','2026-01-01','2026-06-30']:
   qq=engine.data(sid,pd.Timestamp(cut));bb=fast(qq);pd.testing.assert_frame_equal(full.loc[bb.index],bb,check_exact=True,check_dtype=False)
   prefix.append(dict(sid=sid,cut=cut,rows=len(bb),exact=True))
 result=dict(status='PASS',five_full_warm=checks,synthetic_checks=len(ns['checks']),synthetic_optimized_parity=counts,true_input_prefix=prefix,seconds=time.monotonic()-t,core_sha256=sha(P/'core.py'),optimized_sha256=sha(O/'fast_core.py'),engine_sha256=sha(O/'engine.py'))
 (O/'PRE_RUN_EQUIVALENCE.json').write_text(json.dumps(result,indent=2));print('VERIFIED',result['seconds'],flush=True)
if __name__=='__main__':main()
