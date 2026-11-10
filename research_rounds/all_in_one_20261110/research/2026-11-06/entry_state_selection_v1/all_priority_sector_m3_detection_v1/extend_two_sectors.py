"""Original M3 two-sector extension and descriptive sector timeline. No B1 or account."""
from pathlib import Path
import sys,json,hashlib,time,resource,signal,traceback,importlib.util
import numpy as np,pandas as pd
sys.dont_write_bytecode=True
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent
P=R/'m3_strict_s_admission_preflight_v1'
C=R/'major_trends_2025_2026_review_v1/industry_specific_cycles'
SECTORS=sorted(pd.read_csv(O/'FIXED_PRIORITY_66.csv').sector.unique())
START=pd.Timestamp('2024-06-01'); END=pd.Timestamp('2026-10-22')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def module():
 sp=importlib.util.spec_from_file_location('frozen_signal_definitions',P/'preflight.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def freeze():
 assert not (O/'FREEZE.json').exists()
 m=module();f=m.read(P/'FREEZE.json');ids=sorted(s for sec in SECTORS for s in m.members[sec]);assert len(ids)==len(set(ids)) and len(SECTORS)==66
 src={str(O/'FIXED_PRIORITY_66.csv'):sha(O/'FIXED_PRIORITY_66.csv'),str(R/'industry_panorama_2019_2026_v1/full90_final_integration_v1/FINAL_CANONICAL_CYCLES_90.csv'):sha(R/'industry_panorama_2019_2026_v1/full90_final_integration_v1/FINAL_CANONICAL_CYCLES_90.csv'),str(P/'preflight.py'):sha(P/'preflight.py'),str(P/'FREEZE.json'):sha(P/'FREEZE.json'),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(Path(__file__)):sha(__file__)}
 uses=[m.PB/'FIXED_MEMBERSHIP.csv',m.U/'STOCK_MANIFEST.json',m.CAN/'KNOWN3.parquet',m.CAN/'RIGHT3.parquet',m.CAN/'COMMON_K_COMPARISON.parquet',m.PB/'STOCK_DAILY.parquet']
 uses += [p for p,_ in m.PURE_SOURCES.values()]
 for sid in ids:uses.extend(m.paths(sid)[:2])
 # Existing calendar already verified exact old 90-sector overlap; copied unchanged.
 for p in set(uses):
  h=sha(p); assert h==f['input_hashes'][str(p)],str(p);src[str(p)]=h
 save('FREEZE.json',dict(stage='FROZEN_BEFORE_FIXED_66_PRIORITY_EXTENSION',sectors=SECTORS,ids=ids,start=str(START.date()),end=str(END.date()),calendar=f['calendar'],sources=src,definitions=f['definition_hashes'],max_seconds=600,max_peak_rss_bytes=3000000000,no_B1=True,no_economics=True,parameter_search=False))
def run():
 f=json.loads((O/'FREEZE.json').read_text());assert not (O/'RUN_STARTED.json').exists()
 for p,h in f['sources'].items():assert sha(p)==h,p
 m=module();assert m.DEFINITIONS==f['definitions'];cal=pd.DatetimeIndex(f['calendar']);start=time.monotonic()
 save('RUN_STARTED.json',dict(at=pd.Timestamp.now(tz='UTC')))
 def guard(*args):
  peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  assert time.monotonic()-start<=f['max_seconds']
  assert peak<=f['max_peak_rss_bytes']
  return peak
 def alarm(*args):raise TimeoutError('600 second limit')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(f['max_seconds'])
 good=False
 try:
  old=pd.read_parquet(m.PB/'STOCK_DAILY.parquet',columns=['day','sid','score','state','valid_observation']).set_index(['sid','day'])
  mk=pd.read_parquet(m.CAN/'KNOWN3.parquet');mr=pd.read_parquet(m.CAN/'RIGHT3.parquet')
  features={};qa=[]
  for j,sid in enumerate(f['ids'],1):
   guard();pp,gp,_=m.paths(sid);raw=pd.read_parquet(pp).loc[:END];g=pd.read_parquet(gp).loc[:END]
   re=raw.reindex(g.index)
   for col in ['close','volume','segment_id']:np.testing.assert_equal(re[col].to_numpy(),g[col].to_numpy())
   score=m.original_pvr(raw);pv=m.pvr_state(raw,score.score,cal);mu=m.m3_state(g,raw,cal)
   z=mu.rename(columns={'known':'M3_known','right':'M3_right'});z['PVR_score']=pv.score;z['PVR_state']=pv.state;z['PVR_valid']=pv.valid_observation
   oo=old.loc[sid];ix=cal.intersection(oo.index);ix=ix[ix>=START]
   np.testing.assert_allclose(z.loc[ix,'PVR_score'],oo.loc[ix,'score'],rtol=0,atol=1e-10,equal_nan=True)
   np.testing.assert_array_equal(z.loc[ix,'PVR_state'],oo.loc[ix,'state'])
   np.testing.assert_array_equal(z.loc[ix,'PVR_valid'],oo.loc[ix,'valid_observation'])
   mi=cal.intersection(mk.index);mi=mi[mi>=START]
   np.testing.assert_array_equal(z.loc[mi,'M3_known'],mk.loc[mi,sid]);np.testing.assert_array_equal(z.loc[mi,'M3_right'],mr.loc[mi,sid])
   # Fixed first member per sector, all real source physically cut at two dates; no future fill.
   prefix=0
   if sid in [sorted(m.members[s])[0] for s in SECTORS]:
    for cut in [pd.Timestamp('2024-09-26'),pd.Timestamp('2026-07-22')]:
     cc=cal[cal<=cut];r2=raw.loc[:cut];g2=g.loc[:cut];mu2=m.m3_state(g2,r2,cc);p2=m.pvr_state(r2,m.original_pvr(r2).score,cc)
     pd.testing.assert_frame_equal(mu2,mu.loc[:cut],check_exact=True);pd.testing.assert_frame_equal(p2,pv.loc[:cut],check_exact=True);prefix+=1
   features[sid]=z
   qa.append(dict(sid=sid,source_rows=len(raw),overlap_pvr=len(ix),overlap_m3=len(mi),pvr_max_abs_error=float((z.loc[ix,'PVR_score']-oo.loc[ix,'score']).abs().max()),research_present=int(cal[cal>=START].isin(raw.index).sum()),research_required=int((cal>=START).sum()),prefix_cuts=prefix))
   if j%20==0:print('SECTOR_MEMBERS',j,'/',len(f['ids']),round(time.monotonic()-start,2),flush=True)
  known=pd.DataFrame({s:z.M3_known for s,z in features.items()},index=cal).fillna(False).astype(bool)
  right=pd.DataFrame({s:z.M3_right for s,z in features.items()},index=cal).fillna(False).astype(bool)
  pv=pd.DataFrame({s:z.PVR_state for s,z in features.items()},index=cal);both=known&pv.ge(0);parts=[]
  for sec in SECTORS:
   b=m.breadth(sec,m.members[sec],both,right&both);n,N,U,J,d=b.n,b.N,b.U,b.common3_K,b.entered3-b.left3
   lo=(n>=3)&(((3*n>=N)&J.gt(0)&d.gt(0))|(2*n>=N))
   hi=(n+U>=3)&(((3*(n+U)>=N)&(d.gt(0)|J.eq(0)))|(2*(n+U)>=N))
   b['M3_candidate']=np.where(lo,1,np.where(~hi,0,-1)).astype('int8');b['day']=cal;parts.append(b)
  panel=pd.concat(parts,ignore_index=True);panel=panel[panel.day.ge(START)].copy()
  oldpanel=pd.read_parquet(m.CAN/'COMMON_K_COMPARISON.parquet');chk=panel.merge(oldpanel,on=['day','sector'],suffixes=('_new','_old'))
  for a,b in [('N','N'),('K','K'),('n','M3_n'),('U','U'),('common3_K','common3_K'),('entered3','M3_entered3'),('left3','M3_left3'),('M3_candidate','M3_candidate')]:
   ac=a+'_new' if a in oldpanel.columns else a;bc=b+'_old' if b in panel.columns else b;np.testing.assert_array_equal(chk[ac],chk[bc],err_msg=a)
  panel.to_parquet(O/'SECTOR_DAILY.parquet',index=False);pd.DataFrame(qa).to_csv(O/'MEMBER_SOURCE_QA.csv',index=False)
  # Per-member state, no price labels or trading candidates.
  mem=[]
  for sid,z in features.items():
   zz=z[z.index>=START].copy();zz['sid']=sid;zz['day']=zz.index;mem.append(zz)
  pd.concat(mem,ignore_index=True).to_parquet(O/'MEMBER_DAILY.parquet',index=False)
  save('SIGNAL_SEAL.json',dict(outputs={n:sha(O/n) for n in ['SECTOR_DAILY.parquet','MEMBER_SOURCE_QA.csv','MEMBER_DAILY.parquet']},old_panel_overlap_rows=len(chk),stocks=len(features),rows=len(panel),seconds=time.monotonic()-start,peak_rss_bytes=guard(),parameters_changed=False,no_economics=True))
  good=True;print('SECTOR_EXTENSION_COMPLETE',len(panel),round(time.monotonic()-start,2),flush=True)
 except Exception as e:
  save('FAILURE.json',dict(type=type(e).__name__,error=str(e),traceback=traceback.format_exc()));raise
 finally:
  signal.alarm(0);save('RESOURCE_FINAL.json',dict(completed=good,seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)))
if __name__=='__main__':
 {'freeze':freeze,'run':run}[sys.argv[1]]()
