"""Thin causal indicators from original numeric facts; no trading simulation."""
from pathlib import Path
import hashlib,json,pickle,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
LIMIT=60
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def compute(f):
 c=f.close.astype(float);valid=np.isfinite(c)&c.gt(0)&f.segment_id.notna()
 # Invalid observations are boundaries; do not silently compress over them.
 block=(f.segment_id.ne(f.segment_id.shift())|~valid|~valid.shift(fill_value=False)).cumsum()
 out=pd.DataFrame(index=f.index)
 out['close']=c;out['source_segment']=f.segment_id
 for n in [20,60]:
  out['sma'+str(n)]=c.where(valid).groupby(block,sort=False).transform(lambda s:s.rolling(n,min_periods=n).mean())
  out['ema'+str(n)]=c.where(valid).groupby(block,sort=False).transform(lambda s:s.ewm(span=n,adjust=False,min_periods=n).mean())
 sd=c.where(valid).groupby(block,sort=False).transform(lambda s:s.rolling(20,min_periods=20).std(ddof=0))
 upper=out.sma20+2*sd
 out['bb20_prior_upper']=upper.groupby(block,sort=False).shift()
 previous_c=c.groupby(block,sort=False).shift()
 previous_u=out.bb20_prior_upper.groupby(block,sort=False).shift()
 out['bb20_cross_known']=valid&out.bb20_prior_upper.notna()&previous_c.notna()&previous_u.notna()
 out['bb20_cross']=out.bb20_cross_known&c.gt(out.bb20_prior_upper)&previous_c.le(previous_u)
 out['ema_trend_known']=valid&out.ema20.notna()&out.ema60.notna()
 out['ema_trend']=out.ema_trend_known&c.gt(out.ema20)&out.ema20.gt(out.ema60)
 out['bb_trend_known']=valid&out.sma20.notna()&out.sma60.notna()
 out['bb_trend']=out.bb_trend_known&c.gt(out.sma20)&out.sma20.gt(out.sma60)
 return out

def main():
 start=time.monotonic();records=json.loads(M.read_text());assert len(records)==1709
 sources={str(M):sha(M),str(Path(__file__).resolve()):sha(__file__),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt')}
 features={};counts={};prefix_checks=[]
 # Deterministic samples include all requested diagnostic stocks and full-pool order.
 diagnostics={'002151.SZ','300666.SZ','301611.SZ','603061.SH','688362.SH','605111.SH','300623.SZ','688147.SH','605358.SH','688234.SH','688107.SH','600584.SH','688605.SH','688352.SH','002185.SZ','600206.SH','688233.SH','688469.SH'}
 samples=diagnostics|{r['symbol']for r in records[::100]}
 for r in records:
  assert time.monotonic()-start<LIMIT,'feature budget exhausted, no account executed'
  path=Path(r['refs']['facts']);h=sha(path);assert h==r['output_sha256'][str(path)];sources[str(path)]=h
  f=pd.read_parquet(path,columns=['close','segment_id']);assert f.index.is_unique and f.index.is_monotonic_increasing
  full=compute(f)
  if r['symbol']in samples:
   for cut in ['2023-12-29','2024-09-30','2026-03-31']:
    small=compute(f.loc[:cut]);pd.testing.assert_frame_equal(small,full.loc[small.index],check_exact=True)
    prefix_checks.append(dict(sid=r['symbol'],cut=cut,rows=len(small),passed=True))
  z=full.loc['2022-01-01':'2026-06-30'].copy();features[r['symbol']]=z
  counts[r['symbol']]=dict(rows=len(z),BB_known=int(z.bb20_cross_known.sum()),BB_cross=int(z.bb20_cross.sum()))
 with (O/'PRICE_FEATURES.pkl').open('wb')as h:pickle.dump(features,h,protocol=5)
 (O/'PRICE_FEATURE_MANIFEST.json').write_text(json.dumps(dict(passed=True,stocks=1709,rows=sum(v['rows']for v in counts.values()),
  counts=counts,physical_prefix_checks=prefix_checks,source_sha256=sources,output_sha256=sha(O/'PRICE_FEATURES.pkl'),
  seconds=time.monotonic()-start,limit_seconds=LIMIT,new_accounts=0,recomputed_E0_I_CP1_PVR=False),ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(stocks=1709,rows=sum(v['rows']for v in counts.values()),BB_cross=sum(v['BB_cross']for v in counts.values()),
  physical_prefix_checks=len(prefix_checks),seconds=time.monotonic()-start,new_accounts=0),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
