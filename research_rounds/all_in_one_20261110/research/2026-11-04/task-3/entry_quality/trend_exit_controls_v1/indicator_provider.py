"""Immutable prepared tool reader. This class cannot place orders or change facts."""
from pathlib import Path
import gzip,pickle,json,hashlib
import numpy as np
class IndicatorProvider:
 def __init__(self,root=None):
  root=Path(root) if root is not None else Path(__file__).resolve().parent/'indicators';p=root/'MANIFEST.json';self.manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads(p.read_text());q=Path(m['data_file']);assert hashlib.sha256(q.read_bytes()).hexdigest()==m['data_sha256']
  with gzip.open(q,'rb') as f:self.data=pickle.load(f)
  self.cols={k:i for i,k in enumerate(m['columns'])}
 def at(self,sid,at,indicator):
  assert indicator in ('EMA20','EMA60','BOLL20_MID','BOLL20_LOWER');day=str(at)[:10];di=int(np.datetime64(day,'D').astype(np.int64));r=self.data.get(sid)
  result=dict(status='UNKNOWN',day=day,causal_close=None,line=None,source_segment=None,source_max_day=None,unknown_reason=None)
  if r is None:result['unknown_reason']='symbol_missing';return result
  j=int(np.searchsorted(r['days'],di))
  if j==len(r['days']) or int(r['days'][j])!=di:result['unknown_reason']='no_current_source_observation';return result
  result.update(causal_close=float(r['values'][j,0]),source_segment=float(r['segments'][j]),source_max_day=day)
  if not r['observed_valid'][j]:result['unknown_reason']='source_quote_not_valid_observed_price';return result
  line=float(r['values'][j,self.cols[indicator]])
  if not np.isfinite(line):result['unknown_reason']='insufficient_source_segment_warmup';return result
  result.update(status='READY',line=line);return result
