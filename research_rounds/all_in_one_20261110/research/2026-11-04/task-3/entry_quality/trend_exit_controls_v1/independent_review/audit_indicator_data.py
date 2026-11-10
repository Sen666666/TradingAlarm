"""All-symbol artifact audit with independent EMA and rolling-window formulas."""
from pathlib import Path
from collections import Counter
import json,gzip,pickle,hashlib,math,time
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;I=P/'indicators';C=Counter();maxerr=np.zeros(5);start=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=json.loads((I/'MANIFEST.json').read_text());assert m['protocol_sha256']==sha(P/'PROTOCOL.txt') and m['script_sha256']==sha(P/'prepare_indicators.py');assert sha(m['data_file'])==m['data_sha256']
prefix=json.loads((O/'INDICATOR_PREFIX_AUDIT.json').read_text());assert prefix['source_sha256']['prepare_indicators.py']==m['script_sha256'] and prefix['source_sha256']['indicator_provider.py']==sha(P/'indicator_provider.py')
for p,h in m['source_files'].items():assert sha(p)==h,p;C['all_source_SHA']+=1
mp=next(p for p in m['source_files'] if p.endswith('/STOCK_MANIFEST.json'));sm=json.loads(Path(mp).read_text());assert len(sm)==m['symbols']
with gzip.open(m['data_file'],'rb') as z:data=pickle.load(z)
assert set(data)=={x['symbol'] for x in sm}
empty=[];sample_rows=[]
for item in sm:
 sid=item['symbol'];fpath=item['refs']['facts'];rpath=next(p for p in item['source_sha256'] if p.endswith('/signal.parquet'));assert m['source_files'][fpath]==item['output_sha256'][fpath] and m['source_files'][rpath]==item['source_sha256'][rpath]
 f=pd.read_parquet(fpath,columns=['close','segment_id']);raw=pd.read_parquet(rpath,columns=['close','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar']).reindex(f.index);a=data[sid]
 assert f.index.is_unique and f.index.is_monotonic_increasing
 c=f.close.to_numpy(float);seg=f.segment_id.to_numpy(float);rc=raw.close.to_numpy(float);rseg=raw.segment_id.to_numpy(float)
 valid=(raw.price_eligible.to_numpy()==True)&(raw.observed_bar.to_numpy()==True)&(raw.source_invalid.to_numpy()==False)&(raw.synthetic_event_bar.to_numpy()==False)&np.isfinite(c)&(c>0)&(seg==rseg)&np.isclose(rc,c,rtol=1e-10,atol=1e-10)
 days=f.index.to_numpy('datetime64[D]').astype(np.int32);keep=(days>=int(np.datetime64('2022-01-01','D').astype(int)))&(days<=int(np.datetime64('2026-06-30','D').astype(int)))
 assert np.array_equal(a['days'],days[keep]) and np.array_equal(a['segments'],seg[keep],equal_nan=True) and np.array_equal(a['observed_valid'],valid[keep]);C['all_symbol_domains']+=1
 expected=np.full((len(f),5),np.nan);expected[:,0]=c;count=np.zeros(len(f),dtype=np.uint32)
 bounds=np.r_[0,np.flatnonzero(seg[1:]!=seg[:-1])+1,len(f)] if len(f) else np.array([0])
 for lo,hi in zip(bounds[:-1],bounds[1:]):
  ix=np.flatnonzero(valid[lo:hi])+lo
  if not len(ix):continue
  v=c[ix];count[ix]=np.arange(1,len(ix)+1);e20=e60=float(v[0])
  for j,p in enumerate(v):
   if j:e20=(2/21)*p+(19/21)*e20;e60=(2/61)*p+(59/61)*e60
   if j>=19:expected[ix[j],1]=e20
   if j>=59:expected[ix[j],2]=e60
  if len(v)>=20:
   windows=np.lib.stride_tricks.sliding_window_view(v,20);means=np.mean(windows,axis=1);std=np.std(windows,axis=1,ddof=0);expected[ix[19:],3]=means;expected[ix[19:],4]=means-2*std
 out=expected[keep];got=a['values'];assert got.shape==out.shape and np.array_equal(np.isnan(got),np.isnan(out)),sid
 assert np.array_equal(count[keep],a['valid_observations_in_source']),sid
 err=np.abs(got-out);finite=np.isfinite(err)
 if len(out):
  # pandas' incremental rolling variance and independent fresh windows differ at rounding scale.
  assert np.allclose(got,out,equal_nan=True,rtol=1e-9,atol=1e-9),(sid,np.nanmax(err));maxerr=np.maximum(maxerr,np.max(np.where(finite,err,0),axis=0))
 C['all_output_rows']+=len(out);C['all_full_source_rows']+=len(f);C['all_indicator_cells']+=int(np.isfinite(out[:,1:]).sum());C['source_segment_runs']+=len(bounds)-1
 counts=m['counts'][sid];assert counts==dict(source_rows=len(f),kept_rows=int(keep.sum()),invalid_kept=int((~valid[keep]).sum()),source_segments=len(bounds)-1)
 assert m['source_full_history_start'][sid]==(str(f.index[0].date()) if len(f) else None)
 for col,name in enumerate(['EMA20','EMA60','BOLL20_MID','BOLL20_LOWER'],1):assert m['ready_counts'][sid][name]==int(np.isfinite(out[:,col]).sum());C['all_READY_counts']+=1
 if len(f)==0:empty.append(sid)
 for col,name in [(1,'EMA20'),(2,'EMA60')]:
  kk=np.flatnonzero(np.isfinite(out[:,col]))
  if len(kk) and len(sample_rows)<12:
   k=int(kk[0]);sample_rows.append(dict(sid=sid,indicator=name,day=str(np.datetime64(int(a['days'][k]),'D')),value=float(got[k,col]),observations=int(a['valid_observations_in_source'][k])))
 if C['all_symbol_domains']%300==0:print('AUDITED_SYMBOLS',C['all_symbol_domains'],flush=True)
out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(C),symbols=len(data),empty_source_symbols=empty,max_absolute_difference_by_column=dict(zip(m['columns'],maxerr.tolist())),first_READY_examples=sample_rows,source_manifest_sha256=sha(I/'MANIFEST.json'),data_sha256=m['data_sha256'],preparer_sha256=m['script_sha256'],provider_sha256=sha(P/'indicator_provider.py'),protocol_sha256=m['protocol_sha256'],source_files_sha256=m['source_files'],elapsed_seconds=time.monotonic()-start,method='Full3419 immutable source hashes; full1709 symbols/4081068 original facts observations. Original full warmup independently recomputed by explicit EMA recursion plus fresh20-value window mean/population std; all1731880 kept date/domain/validity/state counts and finite outputs compared. No pandas ewm or rolling used in oracle.',limits=['Price validity requires original observed eligible non-synthetic source and matching original source segment; invalid current rows remain UNKNOWN.','Same-segment future valid observations resume previous valid-observation state after invalid/no-trade rows.','Float comparison tolerance1e-9 relative/absolute only covers independent variance rounding; maximum differences reported.','Only indicators/source domains audited. No adapter state machine, trade execution or candidate account performance has passed this receipt.'],new_accounts=0)
(O/'INDICATOR_DATA_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='source_files_sha256'},ensure_ascii=False,indent=2))
