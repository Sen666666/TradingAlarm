"""Fixed14 source-only loader. No economic paths at import or load."""
from pathlib import Path
import copy,gzip,hashlib,json,sys
import pandas as pd
from decimal import Decimal as D
O=Path(__file__).resolve().parent; M=O.parent; R=M.parent; AROOT=R/'act_only_ablation_continuous_v1'; CROOT=R/'account_comparison_continuous_v1'
sys.path.insert(0,str(CROOT/'inputs')); import continuous_inputs as C
sys.path.insert(0,str(AROOT/'code')); from continuous_execution import attach
sys.path.insert(0,str(CROOT/'factors')); from continuous_factors import OpenFactorTimeline,FactorSource
J,A=C.J,C.A
IDS=[27,17,28,1527,1542,2891,2893,343,361,1942,1952,2898,2905,2897]; END='2026-05-15'; START='2022-01-01'
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def track(p,h=None):
 p=Path(p); got=sha(p)
 if h:assert got==h,('source drift',str(p),got,h)
 SOURCES[str(p)]=got;return p
def read(p,h=None):return json.loads(track(p,h).read_text())
def para(p,h=None):return pd.read_parquet(track(p,h))
def canon(x):return J.W.canon(x)
def save(name,x):
 p=O/name;assert not p.exists(),('no overwrite',p)
 p.write_text(json.dumps(canon(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load():
 track(M/'CANDIDATE_CONTRACT_v2.md','d750c7b3dae6353b8eb021630d78e1ca88a21be5895bbf8bb0b71020e2326ef3')
 finals=read(M/'case_trace/FINAL_OUTPUT_HASHES.json');cases=pd.read_csv(track(M/'case_trace/CASE_SUMMARY.csv',finals['CASE_SUMMARY.csv']));cases=cases.set_index('round_id').loc[IDS].reset_index().to_dict('records');sids={r['sid']for r in cases}
 hashes=read(AROOT/'run/OUTPUT_HASHES.json');p=track(AROOT/'run/pair/NOACT.json.gz',hashes['pair/NOACT.json.gz'])
 with gzip.open(p,'rt')as f:old=json.load(f)
 trades=[t for t in old['trades'] if t['security_id']in sids];del old
 p=track(AROOT/'run/pair/daily.jsonl.gz',hashes['pair/daily.jsonl.gz']);nav={};cal=[]
 with gzip.open(p,'rt')as f:
  for line in f:
   r=json.loads(line)
   if r['account']=='NOACT':day=r['at'][:10];nav[day]=r['nav'];cal.append(day)
 assert cal[-1]==END
 p=track(AROOT/'run/pair/opportunities.jsonl.gz',hashes['pair/opportunities.jsonl.gz']);seedkeys={(r['sid'],r['signal_day'])for r in cases};seedopp={}
 with gzip.open(p,'rt')as f:
  for line in f:
   z=json.loads(line)
   if z['account']=='NOACT'and (z['sid'],z['day'])in seedkeys:seedopp[(z['sid'],z['day'])]=z
 for r in cases:
  initial=next(t for t in trades if t['side']=='buy'and t['layer']==r['first_layer_id']);assert initial['kind']=='add'
  prior=[t for t in trades if t['side']=='buy'and t['security_id']==r['sid']and t['kind']=='core'and t['at'][:10]<=r['signal_day']]
  r.update(original_seed_opportunity=seedopp[(r['sid'],r['signal_day'])],seed_nav=nav[r['signal_day']],original_initial_trade=initial,seed_core_epoch=prior[-1]['epoch']if prior else None,seed_core_trade=prior[-1]if prior else None)
 sm={x['symbol']:x for x in read(C.U/'STOCK_MANIFEST.json')};im={x['series']:x for x in read(C.U/'INDUSTRY_MANIFEST.json')}
 J.START=START;J.END=END
 shared=J.M.context(END,ids=sorted(sids));b,m,f=shared
 for item in b.series.values():
  rr=item.record
  track(rr['raw']['path'],rr['raw']['sha256'])
  ar=rr.get('adjustment',{}).get('actions')
  if ar:track(ar['path'],ar['sha256'])
 for p in [J.M.P/'manifest.json',J.M.P/'h1.npz',J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',J.M.BP.C.OLD/'inputs-v2/economic-protocol.json',J.M.BP.C.OLD/'inputs-v2/input-manifest.json',J.M.F]:track(p)
 for sid in b.series:
  p=(J.M.O/'industry-facts'if sid.startswith('URFI')else J.M.IC/'facts')/(sid+'.parquet')
  track(p)
 sectors={l.sector_id for l in b.lines};wanted=sids|sectors
 receipts={s:{}for s in sids};ir={};cp={};states={}
 def add(sid,rows):
  if sid not in wanted:return
  for r in rows:
   day=r['confirmed_day']
   if not START<=day<=END:continue
   key=day if sid in sids else sid+'|'+day;dest=receipts[sid]if sid in sids else ir
   assert key not in dest,('duplicate receipt',sid,day);dest[key]=r
 for mp in [C.W/'2022-normal-reference-20261031/inputs/MANIFEST.json',C.W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',C.D/'inputs/MANIFEST.json']:
  for r in read(mp):
   if r['sid']in wanted:add(r['sid'],read(r['output_path'],r['output_sha256']))
 for r in read(C.O/'H1_MANIFEST.json'):
  if r['sid']in wanted:add(r['sid'],read(r['receipt_path'],r['receipt_sha256']))
 for sid in sorted(wanted):
  r=sm[sid]if sid in sids else im[sid]
  add(sid,read(r['refs']['receipts'],r['output_sha256'][r['refs']['receipts']]))
  z=para(r['refs']['CP1'],r['output_sha256'][r['refs']['CP1']]).loc[:END]
  expected={str(d.date())for d in z.loc[START:END].index[z.loc[START:END].receipt.eq(True)]}
  actual=set(receipts[sid])if sid in sids else {k.split('|')[1]for k in ir if k.startswith(sid+'|')};assert actual==expected
  if sid in sids:
   ff=para(r['refs']['facts'],r['output_sha256'][r['refs']['facts']]).loc[:END];f.f[sid]=ff;cp[sid]=z;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
  else:
   st=para(r['refs']['state'],r['output_sha256'][r['refs']['state']]);states[sid]=J.T.norm(st[st.day<=END].to_dict('records'))
 factors=FactorSource({sid:OpenFactorTimeline(raw,m.actions.get(sid,[]),method=b.series[sid].record['adjustment']['method'],end=END)for sid,raw in m.raw.items()})
 # Verify all local code loaded against the original NOACT runtime when available.
 runtime=read(AROOT/'run/RUNTIME_DEPENDENCY_FREEZE.json')
 for mod in list(sys.modules.values()):
  p=getattr(mod,'__file__',None)
  if p and str(p).startswith('/Users/bytedance/Documents/')and str(p).endswith('.py'):track(p,runtime.get(str(Path(p).resolve())))
 return dict(cases=cases,shared=shared,receipts=receipts,cp=cp,states=states,ir=ir,factors=factors,calendar=cal,trades=trades)
def single(data,sid):
 b,m,f=data['shared'];sector=m.lines[sid].sector_id;want={sid,sector}
 bb=copy.copy(b);bb.lines=tuple(l for l in b.lines if l.security_id==sid);bb.series={k:v for k,v in b.series.items()if k in want};bb.sector_series={k:v for k,v in b.sector_series.items()if k==sector}
 mm=copy.copy(m);mm.bundle=bb;mm.lines={sid:m.lines[sid]};mm.raw={sid:m.raw[sid]};mm.arr={sid:m.arr[sid]};mm.actions={sid:m.actions.get(sid,[])};mm.cache_at=None;mm.mark_verified=set();mm.window_verified=set();mm.notices=[];mm._notice_keys={}
 ff=J.M.E.Facts.__new__(J.M.E.Facts);ff.b=bb;ff.market=mm;ff.f={k:v for k,v in f.f.items()if k in want};ff.cache={};ff.day=None;ff.structure_lookup={}
 cm,cf=attach(mm,ff,data['factors'],J.C.L)
 return (bb,cm,cf),{sid:data['receipts'][sid]},{sid:data['cp'][sid]},{sector:data['states'][sector]},{k:v for k,v in data['ir'].items()if k.startswith(sector+'|')}
