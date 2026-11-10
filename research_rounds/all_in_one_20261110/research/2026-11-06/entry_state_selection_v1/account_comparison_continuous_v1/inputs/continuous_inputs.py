"""Continuous native inputs 2022--2026-05-15; no account state import/run.
Only original missing 2025H1 receipt/PVR export is new. No new I/CP1/stage.
"""
from pathlib import Path
from types import MappingProxyType
import json,hashlib,math,sys,time
import pandas as pd
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
U=W/'universe-cp1-inputs-20261031';P=W/'pvr-slot1-native-readiness-20261101'
START,END='2022-01-01','2026-05-15'
sys.path.insert(0,str(Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')))
import native_adapter as A
N,J,L,IO=A.N,A.J,A.L,A.IO

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class ContinuousScores:
 def __init__(self,check=True):
  self.path=str(O/'H1_MANIFEST.json');hm=read(self.path);h={r['sid']:r for r in hm if not r['industry']}
  dm=read(D/'SCORES_MANIFEST.json');pm=read(P/'SCORES_MANIFEST.json')
  assert dm['fixed_stock_ids']==pm['fixed_stock_ids'] and set(h)==set(dm['fixed_stock_ids'])
  self.source_manifest_sha256={str(p):sha(p)for p in [O/'H1_MANIFEST.json',D/'SCORES_MANIFEST.json',P/'SCORES_MANIFEST.json']}
  self.manifest_sha256=hashlib.sha256(json.dumps(dict(start=START,end=END,sources=self.source_manifest_sha256),sort_keys=True).encode()).hexdigest()
  pmap={r['symbol']:r for r in pm['entries']};values={};self.NA=0;self.cells=0
  for r in dm['entries']:
   sid=r['symbol'];pieces=[]
   for path,digest in [(D/'scores'/f'{sid}.parquet',r['output_sha256']),(Path(h[sid]['score_path']),h[sid]['score_sha256']),(P/'scores'/f'{sid}.parquet',pmap[sid]['output_sha256'])]:
    if check:assert sha(path)==digest,('score changed',path)
    pieces.append(pd.read_parquet(path)['score'])
   old,mid,last=pieces
   overlap=old.index.intersection(last.index);pd.testing.assert_series_equal(old.loc[overlap],last.loc[overlap],check_names=False,check_exact=True,check_freq=False)
   s=pd.concat([old,mid,last.loc['2025-07-01':]]).loc[START:END]
   assert s.index.is_unique and len(mid)==117
   if values:assert tuple(str(t.date())for t in s.index)==dates
   else:dates=tuple(str(t.date())for t in s.index)
   values[sid]=MappingProxyType({str(t.date()):float(v)for t,v in s.items()});self.NA+=int(s.isna().sum());self.cells+=len(s)
  self.values=MappingProxyType(values);self.dates=dates
 def at(self,sid,day):
  v=self.values.get(sid,{}).get(day)
  return v if v is not None and math.isfinite(v) else None

def configure_scores(check=True):
 N.SCORES=ContinuousScores(check=check)
 return N.SCORES

def inputs():
 """Return shared, receipts, cp, states, ir, identity; installs N.SCORES.

 shared=(bundle,market,facts), original native types; no Account or Runner.
 No indicator calculations: all native facts/CP1/state read from frozen files.
 """
 begun=time.monotonic();complete=read(O/'COMPLETION.json');assert complete['status']=='PASS_MISSING_2025H1_EXPORT'
 assert sha(O/'H1_MANIFEST.json')==complete['manifest_sha256']
 for path,h in read(O/'SOURCE_FREEZE.json').items():assert sha(path)==h,('export source changed',path)
 fixed=read(U/'FREEZE.json')['stocks'];sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json')
 assert len(fixed)==len(sm)==1709 and len(im)==90
 receipts={s:{}for s in fixed};ir={};binding={}
 def add(sid,rows):
  for row in rows:
   day=row['confirmed_day']
   if not START<=day<=END:continue
   target=receipts[sid]if sid in receipts else ir;key=day if sid in receipts else sid+'|'+day
   assert key not in target,('duplicate receipt date',sid,day)
   target[key]=row
 for mp in [W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',D/'inputs/MANIFEST.json']:
  binding[str(mp)]=sha(mp)
  for r in read(mp):
   assert sha(r['output_path'])==r['output_sha256'];add(r['sid'],read(r['output_path']))
 for r in read(O/'H1_MANIFEST.json'):
  assert sha(r['receipt_path'])==r['receipt_sha256'];add(r['sid'],read(r['receipt_path']))
 full={};cp={};states={}
 for r in sm+im:
  sid=r.get('symbol',r.get('series'))
  for path,h in r['output_sha256'].items():assert sha(path)==h,('frozen input changed',path)
  add(sid,read(r['refs']['receipts']))
  z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  expected=[str(t.date())for t in z.loc[START:END].index[z.loc[START:END].receipt.eq(True)]]
  actual=sorted(receipts[sid])if sid in receipts else sorted(k.split('|',1)[1]for k in ir if k.startswith(sid+'|'))
  assert actual==expected,('full continuous receipt dates',sid)
  if 'symbol'in r:
   f=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END]
   assert f.index.equals(q.index)and q.index.equals(z.index)
   for k in ['close','segment_id','i_target','i_floor']:pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
   full[sid]=f;cp[sid]=z
  else:
   state=pd.read_parquet(r['refs']['state']);states[sid]=J.T.norm(state[state.day<=END].to_dict('records'))
 J.START,J.END=START,END
 shared=J.M.context(END,ids=fixed);bundle,market,facts=shared
 assert set(market.lines)==set(fixed)=={x.security_id for x in bundle.lines}
 for sid,f in full.items():facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 score=configure_scores()
 identity=dict(window=[START,END],fixed_ids=fixed,sectors=[r['series']for r in im],no_account_state_import=True,numeric_I_CP1_stage_recomputations=0,original_PVR_missing_H1_preexport=True,stock_manifest_sha256=sha(U/'STOCK_MANIFEST.json'),industry_manifest_sha256=sha(U/'INDUSTRY_MANIFEST.json'),receipt_union_sources=binding,H1_manifest_sha256=sha(O/'H1_MANIFEST.json'),stock_canonical_receipts=sum(map(len,receipts.values())),industry_canonical_receipts=len(ir),score_manifest_sha256=score.manifest_sha256,score_dates=len(score.dates),score_cells=score.cells,score_NA=score.NA,ACT_external_sha256=sha(J.M.O/'recovery.csv'),H1_sha256=sha(J.M.P/'h1.npz'),seconds=time.monotonic()-begun)
 return shared,receipts,cp,states,ir,identity
if __name__=='__main__':raise SystemExit('Input adapter only. No account entrypoint.')
