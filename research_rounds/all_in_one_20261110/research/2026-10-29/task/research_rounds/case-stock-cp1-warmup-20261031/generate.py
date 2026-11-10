"""Frozen case stock inputs and market CP1 only; no account runner."""
from pathlib import Path
import sys,time,json,importlib.util,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');BEGIN='2025-07-01';END='2026-06-30';CUT='2025-12-31'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
N=load('case79_original_native_cache',W/'native-I-cache-interface-20261031/cache.py');M=load('case79_original_CP1',RR/'continuous-protection-lines-20261028/code/model.py');C=load('case79_original_common',RR/'continuous-protection-lines-20261028/code/common.py')
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(n,x):
 x=norm(x);(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(a,b):
 # Parquet stores the same calendar timestamps at s or ms precision. Normalize
 # comparison copies only; never change prices, states or persisted source data.
 aa=a.copy(deep=False);bb=b.copy(deep=False);aa.index=a.index.as_unit('ns');bb.index=b.index.as_unit('ns');pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
def frame(sid,f,cut):
 if f.empty:
  return pd.DataFrame({'close':pd.Series(dtype=float),'segment_id':pd.Series(dtype=int),'i_target':pd.Series(dtype=bool),'i_floor':pd.Series(dtype=float),'amount':pd.Series(dtype=float),'e0_down':pd.Series(dtype=bool),'e0_valid':pd.Series(dtype=bool)},index=f.index)
 rec=N.RECORDS[sid];sig=pd.read_parquet(N.OLD/rec['files']['signal']['path']).loc[:cut];ev=pd.read_parquet(N.OLD/rec['files']['events']['path']).reindex(f.index);out=f[['close','segment_id','i_target','i_floor']].copy();out['amount']=sig.amount.reindex(f.index);out['e0_down']=ev.event.eq(-1);out['e0_valid']=f.i_target.astype(bool)
 if not np.isfinite(out[['close','amount']]).all().all() or not out[['close','amount']].gt(0).all().all():raise ValueError('missing/nonpositive same-source CP1 price or amount; no row removal allowed')
 return out
def main():
 start=time.monotonic();stocks=[r['sid'] for r in N.read(W/'cp1-evidence-trace-20261031/CASE_STOCK_CP1_COVERAGE.json')];assert len(stocks)==79 and len(set(stocks))==79;engineering=['000021.SZ','000034.SZ','000050.SZ'];assert not set(engineering)&set(stocks)
 for d in ['full-facts','CP1-input','CP1','receipts','engineering']:(O/d).mkdir(exist_ok=True)
 sources=[Path(__file__),O/'PROTOCOL.txt',W/'native-I-cache-interface-20261031/cache.py',RR/'continuous-protection-lines-20261028/code/model.py',RR/'continuous-protection-lines-20261028/code/common.py',RR/'pv-strength-b5-20261025/code/policy.py',RR/'b5-g1-20261025/code/policies_g1.py',N.OLD/'manifest.json',N.IX/'signals/manifest.json']
 save('FREEZE',dict(before_run=True,stocks=stocks,engineering_stocks=engineering,full_warm_to=END,audit_window=[BEGIN,END],source_sha256={str(p):sha(p) for p in sources},budget_seconds=90,new_economic_paths=0))
 gates=[]
 for sid in engineering:
  f,r=N.derive(sid,END);q=frame(sid,f,END);gold=C.frame(sid,END);exact(q,gold);z=M.calculate(q);old=pd.read_parquet(C.O/'signals'/f'{sid}.parquet').loc[:END];exact(z,old)
  sf,_=N.derive(sid,CUT);exact(sf,f.loc[:CUT]);sz=M.calculate(frame(sid,sf,CUT));exact(sz,z.loc[:CUT]);z.to_parquet(O/'engineering'/f'{sid}.parquet');gates.append(dict(sid=sid,full_input_exact=True,original_CP1_all_fields_exact=True,physical_I_and_CP1_prefix_exact=True,timestamp_comparison_units_only_normalized=True));print('GATE',sid,round(time.monotonic()-start,3),flush=True)
 save('ENGINEERING_GATE',dict(passed=True,stocks=gates,seconds=time.monotonic()-start));out=[]
 for sid in stocks:
  if time.monotonic()-start>=88:save('PARTIAL',dict(completed=len(out),remaining=stocks[len(out):],seconds=time.monotonic()-start));raise TimeoutError('90-second bounded generation; completed caches retained')
  t=time.monotonic();f,r=N.derive(sid,END);f.to_parquet(O/'full-facts'/f'{sid}.parquet');old=pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[BEGIN:END];exact(f.loc[BEGIN:END],old)
  paths={k:N.OLD/N.RECORDS[sid]['files'][k]['path'] for k in ['signal','events','states']};paths['IX_G1']=N.IX/'signals'/f'{sid}.parquet';source_hashes={str(p):sha(p) for p in paths.values()}
  try:
   q=frame(sid,f,END);z=M.calculate(q);q.to_parquet(O/'CP1-input'/f'{sid}.parquet');z.to_parquet(O/'CP1'/f'{sid}.parquet');status='not_applicable_no_market_observation_by_end' if f.empty else 'complete';unknown=None
  except ValueError as e:
   status='blocked_CP1_input';unknown=str(e);z=None
  row=dict(sid=sid,status=status,source_sha256=source_hashes,warm_from=str(f.index.min().date()) if len(f) else None,warm_observations=len(f),audit_observations=len(f.loc[BEGIN:END]),CP1_receipts=int(z.loc[BEGIN:END,'receipt'].sum()) if z is not None else None,CP1_ready_observations=int(z.loc[BEGIN:END,'ready'].sum()) if z is not None else None,unknown_reason=unknown,I_E0_audit_fields_exact=True,seconds=time.monotonic()-t,output_sha256={str(p.relative_to(O)):sha(p) for p in [O/'full-facts'/f'{sid}.parquet',O/'CP1-input'/f'{sid}.parquet',O/'CP1'/f'{sid}.parquet'] if p.exists()})
  (O/'receipts'/f'{sid}.json').write_text(json.dumps(norm(row),ensure_ascii=False,indent=2)+'\n');out.append(row)
  if len(out)%10==0:print('STOCKS',len(out),round(time.monotonic()-start,3),flush=True)
 save('MANIFEST',out);save('COMPLETION',dict(completed=True,stocks=79,engineering_only=3,status_counts=dict(__import__('collections').Counter(x['status'] for x in out)),CP1_receipts=sum(x['CP1_receipts'] or 0 for x in out),seconds=time.monotonic()-start,new_economic_paths=0,no1709_expansion=True,full_warm_preserved=True));print('DONE',round(time.monotonic()-start,3),dict(__import__('collections').Counter(x['status'] for x in out)),flush=True)
if __name__=='__main__':main()
