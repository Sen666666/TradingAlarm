"""Import-safe frozen-input loader. Original runner bodies are never executed."""
from pathlib import Path
import ast,hashlib,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;P=R/'independent_channel_probe_preflight_v1';A=R/'independent_channel_amount_preflight_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
ROSTER=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-compound-design-20261026/proposed-pool.csv')
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected,(str(p),h,expected)
 S[str(p)]=h;return p
manifest={m['symbol']:m for m in json.loads(src(U/'STOCK_MANIFEST.json').read_text())}
with np.load(src(H),allow_pickle=False) as f:full_cal=pd.DatetimeIndex(f['dates'])
cal=full_cal[full_cal<='2026-06-30']
for path,name in [(A/'preflight.py','inputs'),(P/'run_preflight.py','data')]:
 t=ast.parse(src(path).read_text());n=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[n],type_ignores=[]),str(path)+':'+name+'_only','exec'),globals())
WINDOWS=[('2022','2022-01-01','2022-12-31'),('2024_924','2024-09-01','2024-12-31'),('2026H1','2026-01-01','2026-06-30')]

def output_frame(sid,q,x):
 z=x.copy();z['receipt_id']=z.receipt_id.astype('string');z['receipt_id']=sid+'|'+z.receipt_id
 z['sid']=sid
 for c in ['open','high','low','close','raw_open','raw_high','raw_low','raw_close','amount','raw_volume','adjustment_factor','e0_ready','e0_floor','g_ready','coordinate_valid','identity','source_kind','source_path','segment_id','observed_bar','is_observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar','quality_status']:
  z[c]=q[c]
 for c in ['identity','source_kind','source_path','quality_status']:z[c]=z[c].astype('string')
 for c in ['observed_bar','is_observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']:z[c]=z[c].astype('boolean')
 z['segment_id']=pd.to_numeric(z.segment_id,errors='coerce').astype(float)
 return z

def replay(sid,cut=None):
 """Independent review interface. cut truncates raw/facts/CP before reindex/compute."""
 from fast_core import simulate
 q=data(sid,pd.Timestamp(cut) if cut is not None else None)
 return q,simulate(q)
