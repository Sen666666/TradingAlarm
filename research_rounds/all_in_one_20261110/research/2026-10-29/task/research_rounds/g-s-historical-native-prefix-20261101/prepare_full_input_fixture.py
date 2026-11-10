"""Read original saved next-session data ONLY for physical-prefix verification.
The financial calendar stays exactly the authorized two sessions.
"""
from historical_binding import *
import shutil,time,numpy as np
import pyarrow.parquet as pq

def main():
 out=O/'full-input-fixtures';out.mkdir(exist_ok=False);start=time.monotonic()
 inventory={r['symbol']:r for r in LD.read(LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')}
 sources=LD.read(INPUT/'SOURCE_BINDINGS.json');hp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');assert sha(hp)==sources[str(hp)]
 h=np.load(hp,allow_pickle=False);dates=pd.DatetimeIndex(h['dates']);cols={str(s):i for i,s in enumerate(h['symbols'])};scores=h['score']
 def one(path,day,key):
  path=Path(path);assert sha(path)==sources[str(path)]
  f=pq.read_table(path,filters=[(key,'==',pd.Timestamp(day).to_pydatetime())]).to_pandas()
  if 'trade_date' in f.columns:f=f.set_index('trade_date')
  return f
 for k,day in [('2022','2022-01-06'),('2025_26','2025-07-03')]:
  root=out/k;shutil.copytree(INPUT/k,root);m=LD.read(root/'MANIFEST.json');adds={n:[] for n in ('facts','cp','pvr','raw')}
  for n,sid in enumerate(m['fixed_ids']):
   ref=inventory[sid]['refs']
   for key,source,idx in [('facts','facts','date'),('cp','CP1','date'),('pvr','PVR','day'),('raw','raw_bars','trade_date')]:
    f=one(ref[source],day,idx)
    if not f.empty:
     f=f.copy();f['sid']=sid;f['day']=day;adds[key].append(f.reset_index(drop=True))
   if (n+1)%600==0:print('FULL_INPUT_ONLY',k,n+1,round(time.monotonic()-start,2),flush=True)
  for name,rows in adds.items():
   p=root/(name+'.parquet');f=pd.read_parquet(p)
   if rows:f=pd.concat([f]+rows,ignore_index=True)
   f.to_parquet(p,index=False);m['files'][name]['sha256']=sha(p)
  p=root/'h1.parquet';f=pd.read_parquet(p);i=dates.get_indexer([pd.Timestamp(day)])[0]
  rows=[dict(sid=s,day=day,score=float(scores[i,cols[s]])) for s in m['fixed_ids']+m['sectors']]
  f=pd.concat([f,pd.DataFrame(rows)],ignore_index=True);f.to_parquet(p,index=False);m['files']['h1']['sha256']=sha(p)
  m['technical_future_input_fixture']=dict(extra_input_date=day,financial_days_unchanged=m['days'],no_extra_financial_authorization=True,original_prefix_manifest_sha256=sha(INPUT/k/'MANIFEST.json'))
  LD.write(root/'MANIFEST.json',m)
 LD.write(out/'MANIFEST.json',dict(purpose='same-policy physical input truncation test only',source_binding_sha256=sha(INPUT/'SOURCE_BINDINGS.json'),financial_dates_unchanged=True,seconds=time.monotonic()-start))
 print('FULL_INPUT_FIXTURES_READY',round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':main()
