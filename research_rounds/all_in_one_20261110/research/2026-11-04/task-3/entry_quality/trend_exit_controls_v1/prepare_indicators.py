"""Frozen causal price tools, using original source segments and observed quotes."""
from pathlib import Path
import gzip, pickle, json, hashlib, time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OUT=O/'indicators';OUT.mkdir(exist_ok=True)
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 start=time.monotonic();mp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';SRC[str(mp)]=sha(mp);ms=json.loads(mp.read_text());out={};counts={};ready={};starts={}
 for j,m in enumerate(ms):
  sid=m['symbol'];p=Path(m['refs']['facts']);assert sha(p)==m['output_sha256'][str(p)];SRC[str(p)]=sha(p)
  rp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(rp)==m['source_sha256'][str(rp)];SRC[str(rp)]=sha(rp)
  f=pd.read_parquet(p,columns=['close','segment_id']);raw=pd.read_parquet(rp,columns=['close','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar']).reindex(f.index)
  f['close']=f.close.astype(float);raw['close']=raw.close.astype(float)
  assert f.index.is_unique and f.index.is_monotonic_increasing
  ok=raw.price_eligible.eq(True)&raw.observed_bar.eq(True)&raw.source_invalid.eq(False)&raw.synthetic_event_bar.eq(False)&np.isfinite(f.close)&f.close.gt(0)&raw.segment_id.eq(f.segment_id)&np.isclose(raw.close,f.close,rtol=1e-10,atol=1e-10)
  vals=np.full((len(f),5),np.nan);vals[:,0]=f.close.to_numpy(float);nobs=np.zeros(len(f),dtype=np.uint32)
  # valid observation count and all rolling state restart only at original source boundary.
  runs=f.segment_id.ne(f.segment_id.shift()).cumsum()
  for _,rr in f.groupby(runs,sort=False):
   ix=f.index.get_indexer(rr.index[ok.loc[rr.index]])
   if not len(ix):continue
   c=f.close.iloc[ix].astype(float)
   vv=np.column_stack([c.ewm(span=20,adjust=False,min_periods=20).mean(),c.ewm(span=60,adjust=False,min_periods=60).mean(),c.rolling(20,min_periods=20).mean(),c.rolling(20,min_periods=20).mean()-2*c.rolling(20,min_periods=20).std(ddof=0)])
   vals[ix,1:]=vv;nobs[ix]=np.arange(1,len(ix)+1)
  keep=(f.index>=pd.Timestamp('2022-01-01'))&(f.index<=pd.Timestamp('2026-06-30'))
  days=f.index.to_numpy('datetime64[D]').astype(np.int32)
  out[sid]=dict(days=days[keep],values=vals[keep],segments=f.segment_id.to_numpy(float)[keep],observed_valid=ok.to_numpy(bool)[keep],valid_observations_in_source=nobs[keep])
  counts[sid]=dict(source_rows=len(f),kept_rows=int(keep.sum()),invalid_kept=int((~ok.to_numpy(bool)[keep]).sum()),source_segments=int(runs.max()) if len(f) else 0)
  ready[sid]={name:int(np.isfinite(vals[keep,col]).sum()) for name,col in [('EMA20',1),('EMA60',2),('BOLL20_MID',3),('BOLL20_LOWER',4)]}
  starts[sid]=str(f.index[0].date()) if len(f) else None
  if (j+1)%300==0:print('INDICATORS_PREPARED',j+1,flush=True)
 p=OUT/'INDICATORS.pkl.gz'
 with gzip.open(p,'xb',compresslevel=3) as z:pickle.dump(out,z,protocol=5)
 manifest=dict(protocol_sha256=sha(O/'PROTOCOL.txt'),script_sha256=sha(Path(__file__)),symbols=len(out),source_files=SRC,source_full_history_start=starts,counts=counts,ready_counts=ready,columns=['causal_close','EMA20','EMA60','BOLL20_MID','BOLL20_LOWER'],data_file=str(p),data_sha256=sha(p),elapsed_seconds=time.monotonic()-start,causality='trailing/recursive within original source segment; current valid close only; invalid quote skip/no synthetic zero; full source warmup precedes kept interval',new_accounts=0)
 with (OUT/'MANIFEST.json').open('x') as z:json.dump(manifest,z,ensure_ascii=False,indent=2);z.write('\n')
 print('INDICATORS_COMPLETE',len(out),sum(x['kept_rows'] for x in counts.values()),round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':main()
