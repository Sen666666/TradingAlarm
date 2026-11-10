"""Explicit one-factor parameter provider; old adapter remains byte-identical."""
from pathlib import Path
import gzip,hashlib,json,pickle
import numpy as np
F=Path(__file__).resolve().parent
class VariantProvider:
 def __init__(self,relative,ema,root=None):
  assert (relative,ema) in ((10,20),(40,20),(20,10),(20,40),(20,20))
  self.relative,self.ema=relative,ema;root=Path(root) if root else F/'contexts';p=root/'MANIFEST.json'
  self.data_manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads(p.read_text());q=Path(m['data_file']);assert hashlib.sha256(q.read_bytes()).hexdigest()==m['data_sha256']
  self.manifest_sha256=hashlib.sha256((self.data_manifest_sha256+'|RS'+str(relative)+'|EMA'+str(ema)).encode()).hexdigest()
  with gzip.open(q,'rb') as f:self.data=pickle.load(f)
 def at(self,sid,at):
  day=str(at)[:10];di=int(np.datetime64(day,'D').astype(np.int64));r=self.data.get(sid)
  z=dict(day=day,ready_R=False,ready_P=False,close=None,EMA20=None,RS20=None,sector=None,source_segment=None,anchor_day=None,source_max_day=None,unknown_reason=None,RS_window=self.relative,EMA_span=self.ema,RS_value=None,EMA_value=None,legacy_slot_schema='RS20/EMA20 compatibility slots; use explicit RS_window/EMA_span')
  if r is None:z['unknown_reason']='symbol_missing';return z
  j=int(np.searchsorted(r['days'],di))
  if j==len(r['days']) or int(r['days'][j])!=di:z['unknown_reason']='no_current_original_observation';return z
  nr,ne=str(self.relative),str(self.ema);rs=r['RS'+nr][j];ema=r['EMA'+ne][j];rr=bool(r['ready_R'+nr][j]);pp=bool(r['ready_P'+ne][j])
  z.update(close=float(r['close'][j]),EMA20=float(ema) if np.isfinite(ema) else None,RS20=float(rs) if rr else None,RS_value=float(rs) if rr else None,EMA_value=float(ema) if np.isfinite(ema) else None,ready_R=rr,ready_P=pp,sector=r['sector'],source_segment=float(r['source_segment'][j]),source_max_day=day)
  if rr:z.update(anchor_day=str(np.datetime64(int(r['anchor_days'+nr][j]),'D')),stock_return=float(r['stock_return'+nr][j]),industry_return=float(r['industry_return'+nr][j]),market_return=float(r['market_return'+nr][j]))
  if not(rr and pp):z['unknown_reason']='missing/incomparable exact'+nr+'-market-session endpoint or EMA'+ne+' source warmup/validity'
  return z
