"""Read-only union of the original three annual receipt views; native context only."""
from pathlib import Path
import sys,json,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(B/'pvr_pool_feasibility'))
import native_adapter as A
N,J,L,IO=A.N,A.J,A.L,A.IO
sys.path.insert(0,str(B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full'))
import loader_2024 as D
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inputs(window):
 if window=='2022_2024':
  # This loader does not import an old account/checkpoint or annual continuation class.
  value=D.inputs();shared,receipts,cp,states,ir,identity=value
  manifests=[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',D.O/'inputs/MANIFEST.json']
  receipts={sid:{} for sid in receipts};ir={};binding={}
  for mp in manifests:
   binding[str(mp)]=sha(mp)
   for rec in json.loads(mp.read_text()):
    p=Path(rec['output_path']);assert sha(p)==rec['output_sha256'];binding[str(p)]=rec['output_sha256']
    for r in json.loads(p.read_text()):
     sid=rec['sid'];day=r['confirmed_day']
     if sid in receipts:
      assert day not in receipts[sid];receipts[sid][day]=r
     else:
      key=sid+'|'+day;assert key not in ir;ir[key]=r
  for sid,df in cp.items():assert len(receipts[sid])==int(df.loc['2022-01-01':'2024-12-31'].receipt.eq(True).sum())
  J.START='2022-01-01';J.END='2024-12-31';score=D.O/'SCORES_MANIFEST.json'
  identity=dict(identity,window=[J.START,J.END],receipt_union_sources=binding,stock_canonical_receipts=sum(map(len,receipts.values())),industry_canonical_receipts=len(ir),score_manifest_sha256=sha(score),no_account_state_import=True)
 else:
  assert window=='strong';old=A.S.O
  try:A.S.O=O/'input_readiness';shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26')
  finally:A.S.O=old
  J.START='2025-07-01';J.END='2026-06-30';score=W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json'
 N.configure_scores(score)
 return shared,receipts,cp,states,ir,identity
if __name__=='__main__':raise SystemExit('Input loader only')
