"""Read-only fixed relative context, independent from account permissions."""
from pathlib import Path
import json,gzip,pickle,hashlib
import numpy as np
class ContextProvider:
 def __init__(self,root=None):
  root=Path(root) if root else Path(__file__).resolve().parent/'relative_context';p=root/'MANIFEST.json';self.manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads(p.read_text());q=Path(m['data_file']);assert hashlib.sha256(q.read_bytes()).hexdigest()==m['data_sha256']
  with gzip.open(q,'rb') as f:self.data=pickle.load(f)
 def at(self,sid,at):
  day=str(at)[:10];di=int(np.datetime64(day,'D').astype(np.int64));r=self.data.get(sid);z=dict(day=day,ready_R=False,ready_P=False,close=None,EMA20=None,RS20=None,sector=None,source_segment=None,anchor_day=None,source_max_day=None,unknown_reason=None)
  if r is None:z['unknown_reason']='symbol_missing';return z
  j=int(np.searchsorted(r['days'],di))
  if j==len(r['days']) or int(r['days'][j])!=di:z['unknown_reason']='no_current_original_observation';return z
  z.update(close=float(r['close'][j]),EMA20=float(r['EMA20'][j]) if np.isfinite(r['EMA20'][j]) else None,RS20=float(r['RS20'][j]) if r['ready_R'][j] else None,ready_R=bool(r['ready_R'][j]),ready_P=bool(r['ready_P'][j]),sector=r['sector'],source_segment=float(r['source_segment'][j]),source_max_day=day)
  if r['ready_R'][j]:z.update(anchor_day=str(np.datetime64(int(r['anchor_days'][j]),'D')),stock_return20=float(r['stock_return20'][j]),industry_return20=float(r['industry_return20'][j]),market_return20=float(r['market_return20'][j]))
  if not(z['ready_R'] and z['ready_P']):z['unknown_reason']='missing/incomparable exact20-market-session endpoint or EMA source warmup/validity'
  return z
