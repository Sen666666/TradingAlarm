"""2024 immutable input extension only. No Runner/Account or execution entrypoint."""
from pathlib import Path
from datetime import datetime,time as dt
import hashlib,json,sys,time
import pandas as pd

O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P=W/'pvr-slot1-native-readiness-20261101'
sys.path.insert(0,str(P))
import native_rank as N
import execution_support as S
J,L,IO=N.J,N.L,N.IO
START,END='2024-01-01','2024-12-31'

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def assert_data():
 g=read(O/'DATA_GATE.json');assert g['passed']and g['account_events']==0
 assert sha(O/'SCORES_MANIFEST.json')==g['score_manifest_sha256']
 assert sha(O/'inputs/MANIFEST.json')==g['canonical_manifest_sha256']
 assert sha(O/'SOURCE_FREEZE.json')==g['source_freeze_sha256']
 for p,h in read(O/'SOURCE_FREEZE.json')['sources'].items():assert sha(p)==h,('input generation source changed',p)
 return g

def inputs():
 begun=time.monotonic();assert_data()
 sm=read(L.U/'STOCK_MANIFEST.json');im=read(L.U/'INDUSTRY_MANIFEST.json')
 fixed=read(L.U/'FREEZE.json')['stocks'];manifest=read(O/'inputs/MANIFEST.json');new={r['sid']:r for r in manifest}
 assert len(sm)==len(fixed)==1709 and len(im)==90 and len(new)==1799
 full={};cp={};receipts={}
 for r in sm:
  sid=r['symbol'];rec=new[sid];assert rec['original_output_sha256']==r['output_sha256']
  for p,h in r['output_sha256'].items():assert sha(p)==h,('numeric cache changed',p)
  assert sha(rec['output_path'])==rec['output_sha256']
  f=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  assert f.index.equals(q.index)and q.index.equals(z.index)
  for k in ['close','segment_id','i_target','i_floor']:pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
  rr=read(rec['output_path']);assert len(rr)==int(z.loc[START:END].receipt.eq(True).sum())
  full[sid]=f;cp[sid]=z;receipts[sid]={x['confirmed_day']:x for x in rr}
 # The unchanged original context loads price/action/H1/execution inputs.
 shared=J.M.context(END,ids=fixed);bundle,market,facts=shared
 assert set(market.lines)==set(fixed)=={x.security_id for x in bundle.lines}
 for sid,f in full.items():
  facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 states={};ir={}
 for r in im:
  sid=r['series'];rec=new[sid]
  for p,h in r['output_sha256'].items():assert sha(p)==h,('industry numeric cache changed',p)
  assert sha(rec['output_path'])==rec['output_sha256']
  z=pd.read_parquet(r['refs']['state']);states[sid]=J.T.norm(z[z.day<=END].to_dict('records'))
  for x in read(rec['output_path']):ir[sid+'|'+x['confirmed_day']]=x
 identity=dict(fixed_ids=fixed,sectors=[r['series']for r in im],window=[START,END],numeric_models_recomputed=0,
  stock_manifest_sha256=sha(L.U/'STOCK_MANIFEST.json'),industry_manifest_sha256=sha(L.U/'INDUSTRY_MANIFEST.json'),
  canonical_manifest_sha256=sha(O/'inputs/MANIFEST.json'),score_manifest_sha256=sha(O/'SCORES_MANIFEST.json'),
  ACT_external_sha256=sha(J.M.O/'recovery.csv'),H1_sha256=sha(J.M.P/'h1.npz'),seconds=time.monotonic()-begun)
 return shared,receipts,cp,states,ir,identity

def scores():
 assert_data()
 return N.FrozenScores(O/'SCORES_MANIFEST.json')

def physical(value,cut):
 shared,receipts,cp,states,ir,identity=value
 shared,receipts,kw=S.physical_inputs(shared,receipts,cp,states,ir,cut)
 return shared,receipts,kw['stock_cp'],kw['industry_states'],kw['industry_receipts'],identity

def next_events(shared,parent='2023-12-29T15:10:00+08:00',through='2024-01-02'):
 _,market,_=shared;after=J.M.N.iso(parent);finish=J.M.N.iso(through+'T15:10:00+08:00')
 closes={x for x in market.cutoffs if after<x<=finish};opens={x for x in market.sessions['A']if after<x<=finish}
 actions={datetime.combine(datetime.fromisoformat(x['effective_date']).date(),dt.min,J.M.N.TZ)
          for rows in market.actions.values()for x in rows}
 actions={x for x in actions if after<x<=finish}
 return [dict(at=str(x),opening=x in opens,close=x in closes,action=x in actions)for x in sorted(closes|opens|actions)]

if __name__=='__main__':raise SystemExit('Input loader only; no financial execution.')
