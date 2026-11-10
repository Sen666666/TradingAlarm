"""Frozen signal-only B0/B1 preflight. Imports only pure source definitions; no account consumer."""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,math,time,warnings,resource,signal,traceback
from types import SimpleNamespace
import numpy as np
import pandas as pd
sys.dont_write_bytecode=True
warnings.filterwarnings('ignore',category=FutureWarning)
O=Path(__file__).resolve().parent;R=O.parent
M=Path('/Users/bytedance/Documents/ChatGPT/money')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
OLD=M/'research_rounds/strict-entry-capacity-20261027'
CAN=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
PB=R/'pvr_persistence_breadth_v1'
B=M/'research_rounds/rs-h1-execution-20261025'
EP=R/'m3_stock_birth_during_sector_v1'
CASES=R/'m3_strict_s_fixed_case_map_v1/FIXED_20_CASES.csv'
START=pd.Timestamp('2024-06-01');END=pd.Timestamp('2026-10-22')
INIT=D('24000');RISK=D('3000');SLIP=D('.0005')
POSITIVE_MASK_COLUMNS=('price_eligible','observed_bar','is_observed_bar')
NEGATIVE_MASK_COLUMNS=('source_invalid','synthetic_event_bar')
EVENT_COLUMNS=['confirmation','leg_direction','developing_extreme','confirmed_pivot','event','pivot_age','developing_extreme_price','confirmed_pivot_price','confirmed_pivot_date','developing_extreme_date']
EVENT_DATE_COLUMNS=['confirmed_pivot_date','developing_extreme_date']
UNIT_ROUNDOFF=np.finfo(np.float64).eps/2
ROUNDING_STEPS=4
GAMMA4=ROUNDING_STEPS*UNIT_ROUNDOFF/(1-ROUNDING_STEPS*UNIT_ROUNDOFF)
PURE_SOURCES={
 'arithmetic':(M/'research_rounds/pv-strength-b5-20261025/code/arithmetic.py',['compare','log_ratio']),
 'strict':(OLD/'code/entry_kernel.py',['entry_events']),
 'mu':(CAN/'run.py',['native_mu','state']),
 'breadth':(R/'momentum_persistence_breadth_v1/analyze.py',['breadth']),
 'pvr':(U.parent/'pvr-current-v3-information-capital-20261101/original_score_function.py',['score']),
 'clock':(Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py'),['original_observation_clock']),
 'pvr_state':(PB/'experiment.py',['state']),
 'sizing':(EP/'relative_priority_v1/simulate.py',['finite','true','false','flags','getmeta','fee','size','checkclose','DayFrame'])}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,(pd.Timestamp,Path)):return str(v)
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
def save(name,v): (O/name).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def defs(path,names):
 text=path.read_text();found={}
 for node in ast.parse(text).body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
   source=ast.get_source_segment(text,node);exec(compile(source,str(path)+':pure_definition','exec'),globals())
   found[node.name]=hashlib.sha256(source.encode()).hexdigest()
 assert set(found)==set(names),(path,names,found)
 return found
DEFINITIONS={}
for label,(p,names) in PURE_SOURCES.items():
 DEFINITIONS[label]=defs(p,names)
 if label=='mu':m3_state=state
 if label=='pvr':original_pvr=score
 if label=='pvr_state':pvr_state=state
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
industry={x['series']:x for x in read(U/'INDUSTRY_MANIFEST.json')}
roster=pd.read_csv(PB/'FIXED_MEMBERSHIP.csv').set_index('sid')
members=roster.groupby('sector_id').apply(lambda g:list(g.index),include_groups=False).to_dict()
assert len(manifest)==1709 and len(members)==90 and set(roster.index)==set(manifest)
rules=read(B/'inputs-v2/market-rules.json')
proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
raw={};capacity={};meta={};closecache={}
RUN_START=None
RUN_LIMITS=None
def resource_check(stage):
 if RUN_START is None:return {}
 peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 if sys.platform!='darwin':peak*=1024
 z=dict(stage=stage,elapsed_seconds=time.monotonic()-RUN_START,peak_rss_bytes=int(peak))
 save('RESOURCE_LAST.json',z)
 if z['elapsed_seconds']>RUN_LIMITS['max_seconds_main']:raise RuntimeError('wall-time limit exceeded')
 if peak>RUN_LIMITS['max_rss_bytes']:raise RuntimeError('peak RSS limit exceeded')
 return z
def paths(sid):
 m=manifest[sid]
 return (Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))),
         M/'research_rounds/ix-a-share-entry-20261025/signals'/(sid+'.parquet'),Path(m['refs']['facts']))
def load(sid):
 if sid in raw:return
 p=pd.read_parquet(paths(sid)[0]).loc[:END]
 raw[sid]=DayFrame(p)
 vol=p.raw_volume[p.raw_volume.gt(0)]
 capacity[sid]=(vol.rolling(20,min_periods=20).mean()*.01).reindex(p.index).ffill().to_dict()
def verify():
 f=read(O/'FREEZE.json')
 for p,h in f['input_hashes'].items():assert sha(p)==h,(p,'frozen input drift')
 assert f['definition_hashes']==DEFINITIONS
 return f
def make_calendar():
 days=set()
 for x in industry.values():
  p=next(p for p in x['source_sha256'] if p.endswith('/signal.parquet'))
  days.update(pd.read_parquet(p,columns=[]).index)
 c=pd.DatetimeIndex(sorted(days));c=c[c<=END]
 return c[max(0,c.searchsorted(START)-8):]
def freeze():
 assert not (O/'FREEZE.json').exists()
 src=[Path(__file__),O/'PROTOCOL_DRAFT.txt',CASES,CASES.parent/'PROTOCOL.json',CASES.parent/'SOURCE_HASHES.json',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',PB/'FIXED_MEMBERSHIP.csv',PB/'STOCK_DAILY.parquet',CAN/'COMMON_K_COMPARISON.parquet',CAN/'RIGHT3.parquet',CAN/'KNOWN3.parquet',EP/'SEALED_ALL_BIRTH_EVENTS.csv',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']
 src += [p for p,_ in PURE_SOURCES.values()]+[OLD/'code/prepare.py']
 for sid,x in manifest.items():
  for p in paths(sid):src.append(p)
  old=OLD/'signals'/(sid+'.parquet')
  if old.exists():src.append(old)
 for x in industry.values():src.append(Path(next(p for p in x['source_sha256'] if p.endswith('/signal.parquet'))))
 hashes={str(p):sha(p) for p in sorted(set(src))}
 for x in manifest.values():
  for p,h in x['source_sha256'].items():
   if p in hashes:assert hashes[p]==h,(p,'manifest source mismatch')
  p=x['refs']['facts'];assert hashes[p]==x['output_sha256'][p]
 for x in industry.values():
  for p,h in x['source_sha256'].items():
   if p in hashes:assert hashes[p]==h
 cal=make_calendar()
 oldcal=pd.DatetimeIndex(sorted(pd.read_parquet(CAN/'COMMON_K_COMPARISON.parquet',columns=['day']).day.unique()))
 overlap=oldcal[(oldcal>=cal.min())&(oldcal<=cal.max())]
 assert cal[(cal>=overlap.min())&(cal<=overlap.max())].equals(overlap),'common calendar overlap mismatch'
 save('FREEZE.json',dict(stage='FROZEN_BEFORE_REAL_NEW_SIGNAL_CALC',start=START,end=END,old_history_seen=True,no_economic_run=True,parameter_search=False,input_hashes=hashes,definition_hashes=DEFINITIONS,calendar=[str(d.date()) for d in cal],calendar_overlap_exact=len(overlap),case_count=len(pd.read_csv(CASES)),stock_count=1709,industry_count=90,limits={'max_seconds_main':1800,'max_rss_bytes':6000000000},reporting_context_common_days_each_side=10))
 print('FREEZE',sha(O/'FREEZE.json'),len(hashes),'inputs',len(cal),'calendar',flush=True)
def strict_calc(f,multiplier):
 out=[]
 for seg,g in f.groupby('segment_id',sort=False):
  e,_=entry_events(g,multiplier);active=False;floor=math.nan;rows=[]
  for t,r in g.iterrows():
   exited=False
   if active and compare(float(r.close),floor)<=0:active=False;exited=True
   if e.loc[t,'event']==1:
    pivot=float(e.loc[t,'confirmed_pivot_price'])
    if active:floor=max(floor,pivot)
    elif not exited:active=True;floor=pivot
   row={'day':t,'strict_target':active,'strict_floor':floor if active or exited else math.nan}
   row.update(e.loc[t].to_dict());rows.append(row)
  out.append(pd.DataFrame(rows).set_index('day'))
 if not out:return pd.DataFrame(index=f.index,columns=['strict_target','strict_floor']+EVENT_COLUMNS)
 z=pd.concat(out)
 for c in EVENT_DATE_COLUMNS:z[c]=z[c].astype('string')
 valid=f.observed_bar.eq(True)&f.price_eligible.eq(True)&f.volume_eligible.eq(True)&~f.source_invalid.eq(True)&~f.synthetic_event_bar.eq(True)&f.close.gt(0)&f.volume.gt(0)
 known=valid&np.isfinite(z.leg_direction)&(~z.strict_target|np.isfinite(z.strict_floor))
 z['strict_known']=known
 z['strict_state']=np.where(known,z.strict_target.astype(int),-1).astype('int8')
 return z
def calc_stock(sid,cal,cut=None):
 p,gp,fp=paths(sid);p=pd.read_parquet(p).loc[:END];g=pd.read_parquet(gp).loc[:END];f=pd.read_parquet(fp).loc[:END]
 if cut is not None:p=p.loc[:cut];g=g.loc[:cut];f=f.loc[:cut];cal=cal[cal<=cut]
 assert p.index.is_unique and p.index.is_monotonic_increasing and not p.index.hasnans
 gr=p.reindex(g.index)
 for c in ['close','volume','segment_id']:np.testing.assert_equal(gr[c].to_numpy(),g[c].to_numpy(),err_msg=sid+':'+c)
 x=original_pvr(p);ps=pvr_state(p,x.score,cal);ms=m3_state(g,p,cal)
 s1=strict_calc(p,1.0);s15=strict_calc(p,1.5)
 ix=p.index.intersection(f.index)
 assert np.array_equal(s1.strict_target.reindex(ix).to_numpy(bool),f.e0_target.reindex(ix).to_numpy(bool)),(sid,'multiplier1 target mismatch')
 np.testing.assert_allclose(s1.strict_floor.reindex(ix),f.e0_floor.reindex(ix),equal_nan=True,rtol=1e-12,atol=1e-10,err_msg=sid+':multiplier1 floor')
 oldp=OLD/'signals'/(sid+'.parquet');cache_n=0
 if oldp.exists():
  old=pd.read_parquet(oldp);oi=p.index.intersection(old.index);cache_n=len(oi)
  assert np.array_equal(s15.strict_target.reindex(oi).to_numpy(bool),old.strict_target.reindex(oi).to_numpy(bool)),(sid,'old strict cache target mismatch')
  for c in ['strict_floor','event']:np.testing.assert_allclose(s15[c].reindex(oi),old[c].reindex(oi),equal_nan=True,rtol=1e-12,atol=1e-10,err_msg=sid+':strict cache '+c)
 z=ms.rename(columns={'known':'M3_known','right':'M3_right'})
 z['M3_state']=np.where(z.M3_known,z.M3_right.astype(int),-1).astype('int8')
 z['PVR_score']=ps.score;z['PVR_state']=ps.state;z['PVR_valid']=ps.valid_observation
 for c in ['strict_target','strict_floor','strict_known','strict_state','confirmation','event','leg_direction','developing_extreme_price','developing_extreme_date','confirmed_pivot_price','confirmed_pivot_date','pivot_age']:z['S15_'+c]=s15[c].reindex(cal)
 for c in ['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','close','raw_close','factor','segment_id']:z[c]=f[c].reindex(cal)
 for c in ['source_kind','source_path','adjustment_factor','raw_open','raw_volume','amount','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']:z[c]=p[c].reindex(cal)
 roots=(~f.i_target.eq(True).shift(fill_value=False)&f.i_target.eq(True)).cumsum()
 z['I_root_serial']=roots.where(f.i_target.eq(True)).reindex(cal)
 z['I_qualified']=z.e0_ready.eq(1)&z.g_ready.eq(True)&z.i_target.eq(1)&np.isfinite(z.i_floor)&z.i_floor.gt(0)
 z['PVR_known']=z.PVR_state.ge(0)&np.isfinite(z.PVR_score)&z.PVR_valid.eq(True)
 # Explicit report dtypes prevent a later missing row from changing an earlier prefix schema.
 # Original computations and gate Booleans above are unchanged; missing values stay NaN.
 numeric_facts=['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','close','raw_close','factor','segment_id','I_root_serial']
 numeric_raw=['adjustment_factor','raw_open','raw_volume','amount','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']
 numeric_strict=['S15_'+c for c in ['strict_target','strict_floor','strict_known','strict_state','confirmation','event','leg_direction','developing_extreme_price','confirmed_pivot_price','pivot_age']]
 for c in numeric_facts+numeric_raw+numeric_strict:z[c]=pd.to_numeric(z[c],errors='raise').astype('float64')
 for c in ['source_kind','source_path','S15_developing_extreme_date','S15_confirmed_pivot_date']:z[c]=z[c].astype('string')
 z['sid']=sid;z['day']=z.index
 return z,dict(sid=sid,source_rows=len(p),multiplier1_rows=len(ix),old_strict_cache_rows=cache_n,first_source=str(p.index.min()),last_source=str(p.index.max()))
def synthetic():
 global entry_events
 dates=pd.bdate_range('2024-01-01',periods=260)
 prices=100*np.exp(np.cumsum(np.r_[np.tile([.003,-.002],50),np.full(40,.012),np.full(40,-.015),np.full(80,.009)]))
 f=pd.DataFrame({'close':prices,'volume':1000.,'segment_id':0,'observed_bar':True,'price_eligible':True,'volume_eligible':True,'source_invalid':False,'synthetic_event_bar':False},index=dates)
 source=(OLD/'code/prepare.py').read_text()
 node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='calc')
 refenv=dict(globals(),fn=entry_events,ev=SimpleNamespace(compare=compare))
 exec(compile(ast.get_source_segment(source,node),str(OLD/'code/prepare.py')+':original_calc','exec'),refenv)
 reference=refenv['calc']
 z=strict_calc(f,1.5);checks=[]
 for n in [65,100,140,180,220]:
  q=strict_calc(f.iloc[:n],1.5);pd.testing.assert_frame_equal(q,z.iloc[:n],check_exact=True)
  bad=f.copy();bad.loc[dates[n]:,'close']*=10.;bad.loc[dates[n]:,'volume']*=100.
  zz=strict_calc(bad,1.5);pd.testing.assert_frame_equal(zz.iloc[:n],z.iloc[:n],check_exact=True)
  checks.append(dict(n=n,prefix=True,future_pollution=True))
 assert z.strict_state.iloc[:64].eq(-1).all()
 changed=f.copy();changed.loc[dates[150]:,'segment_id']=1
 q=strict_calc(changed,1.5);assert q.strict_state.iloc[150:214].eq(-1).all()
 zero=f.copy();zero.loc[dates[160:164],'volume']=0.
 eq=f.copy();eq.loc[dates[140:145],'close']=eq.close.iloc[139]
 for kind,frame in [('smooth',f),('segment',changed),('zero_volume',zero),('equal_prices',eq)]:
  for mult in [1.0,1.5]:
   a=strict_calc(frame,mult);b=reference(frame,mult)
   for c in ['strict_target','strict_floor','event']:
    np.testing.assert_equal(a[c].to_numpy(),b[c].to_numpy(),err_msg=kind+':'+str(mult)+':'+c)
 assert strict_calc(zero,1.5).strict_state.loc[dates[160:164]].eq(-1).all()
 assert bool(z.strict_target.any()) and bool(z.event.eq(-1).any())
 assert compare(1.,1.+GAMMA4/2)==0 and compare(1.+8*GAMMA4,1.)==1
 # Inject explicit pure events to exercise prior-floor exit then positive event on same CLOSE.
 hand=f.iloc[:4].copy();hand['close']=[110.,115.,100.,105.]
 def fixed_events(frame,multiplier=1.5):
  q=pd.DataFrame(np.nan,index=frame.index,columns=[c for c in EVENT_COLUMNS if c not in EVENT_DATE_COLUMNS])
  q['event']=[1.,0.,1.,0.];q['leg_direction']=1.;q['confirmed_pivot_price']=[100.,np.nan,90.,np.nan]
  for c in EVENT_DATE_COLUMNS:q[c]=pd.Series(pd.NA,index=frame.index,dtype='string')
  return q[EVENT_COLUMNS],pd.Series(np.arange(len(frame)),index=frame.index)
 original_events=entry_events
 try:
  entry_events=fixed_events
  h=strict_calc(hand,1.5)
 finally:entry_events=original_events
 assert h.strict_target.tolist()==[True,True,False,False]
 assert h.strict_state.tolist()==[1,1,0,0]
 assert h.strict_floor.iloc[2]==100 and pd.isna(h.strict_floor.iloc[3])
 return dict(passed=True,checks=checks,source_calc_comparisons=8,segment_reset_known_test=True,zero_volume_unknown=True,numeric_tie=True,exit_then_positive_no_reentry=True,inactive_missing_floor_stays_known_false=True,no_labels=True)
def small():
 verify();assert not (O/'SMALL_COMPLETE.json').exists()
 save('SMALL_STARTED.json',dict(at=pd.Timestamp.now(tz='UTC')))
 cal=pd.DatetimeIndex(read(O/'FREEZE.json')['calendar']);cases=pd.read_csv(CASES)
 dest=O/'small';dest.mkdir(exist_ok=False);qa=[];views=[]
 for sid in sorted(cases.symbol.unique()):
  resource_check('small_before_'+sid)
  z,q=calc_stock(sid,cal);z.to_parquet(dest/(sid+'.parquet'),index=False)
  for cut in [pd.Timestamp('2024-09-26'),pd.Timestamp('2026-07-22')]:
   zz,_=calc_stock(sid,cal,cut);pd.testing.assert_frame_equal(zz,z.loc[:cut],check_exact=True)
  q['physical_dataframe_prefix_cuts']=2;qa.append(q);resource_check('small_after_'+sid)
  for row in cases[cases.symbol.eq(sid)].itertuples():
   d=pd.Timestamp(row.signal_close_date);a=z.loc[d].to_dict();a.update(case_id=row.case_id,case_reason=row.reason);views.append(a)
  print('SMALL',sid,'multiplier1',q['multiplier1_rows'],'old_S_cache',q['old_strict_cache_rows'],flush=True)
 pd.DataFrame(views).to_csv(O/'SMALL_FIXED20_STOCK_ONLY.csv',index=False)
 save('SMALL_COMPLETE.json',dict(qa=qa,synthetic=synthetic(),full_sector_not_computed=True,no_economics=True))
 print('SMALL COMPLETE',len(qa),flush=True)
def feature_main():
 f=verify();assert (O/'SMALL_COMPLETE.json').exists();assert not (O/'FEATURES_STARTED.json').exists()
 save('FEATURES_STARTED.json',dict(at=pd.Timestamp.now(tz='UTC'),protocol_hash=sha(O/'PROTOCOL_DRAFT.txt')))
 cal=pd.DatetimeIndex(f['calendar']);dest=O/'features';dest.mkdir(exist_ok=False);qa=[];start=time.monotonic()
 caseids=set(pd.read_csv(CASES).symbol)
 ids=sorted(manifest,key=lambda s:(s not in caseids,s))
 old=pd.read_parquet(PB/'STOCK_DAILY.parquet',columns=['day','sid','score','state','valid_observation']).set_index(['sid','day'])
 mk=pd.read_parquet(CAN/'KNOWN3.parquet');mr=pd.read_parquet(CAN/'RIGHT3.parquet')
 for j,sid in enumerate(ids,1):
  resource_check('features_before_'+sid)
  z,q=calc_stock(sid,cal)
  if sid in old.index.get_level_values(0):
   o=old.loc[sid];ix=z.index.intersection(o.index)
   np.testing.assert_allclose(z.loc[ix,'PVR_score'],o.loc[ix,'score'],rtol=0,atol=1e-10,equal_nan=True,err_msg=sid+':PVR old')
   assert z.loc[ix,'PVR_state'].equals(o.loc[ix,'state'].astype('int8'))
   assert z.loc[ix,'PVR_valid'].equals(o.loc[ix,'valid_observation'])
   q['pvr_old_overlap']=len(ix)
   q['pvr_old_max_abs_error']=float((z.loc[ix,'PVR_score']-o.loc[ix,'score']).abs().max())
   z.loc[ix,'PVR_score']=o.loc[ix,'score'] # exact old score authority
  ix=z.index.intersection(mk.index)
  assert z.loc[ix,'M3_known'].equals(mk.loc[ix,sid])
  assert z.loc[ix,'M3_right'].equals(mr.loc[ix,sid])
  q['m3_old_overlap']=len(ix);z.to_parquet(dest/(sid+'.parquet'),index=False);qa.append(q);resource_check('features_after_'+sid)
  if j%50==0 or j==len(ids):
   save('FEATURE_PROGRESS.json',dict(done=j,total=len(ids),seconds=time.monotonic()-start,last_sid=sid))
   print('FEATURES',j,'/',len(ids),'seconds',round(time.monotonic()-start,2),flush=True)
  assert time.monotonic()-start<f['limits']['max_seconds_main'],'runtime budget reached'
 pd.DataFrame(qa).to_csv(O/'FEATURE_SOURCE_QA.csv',index=False)
 save('FEATURES_COMPLETE.json',dict(stocks=len(qa),seconds=time.monotonic()-start,outputs={p.name:sha(p) for p in sorted(dest.glob('*.parquet'))}))
 print('FEATURES COMPLETE',len(qa),flush=True)
def panel_from(features):
 cal=next(iter(features.values())).index
 known=pd.DataFrame({s:z.M3_known for s,z in features.items()},index=cal).fillna(False).astype(bool)
 right=pd.DataFrame({s:z.M3_right for s,z in features.items()},index=cal).fillna(False).astype(bool)
 pv=pd.DataFrame({s:z.PVR_state for s,z in features.items()},index=cal)
 both=known&pv.ge(0);parts=[]
 for sec,ids in members.items():
  b=breadth(sec,ids,both,right&both);n,N,U,J,d=b.n,b.N,b.U,b.common3_K,b.entered3-b.left3
  lo=(n>=3)&(((3*n>=N)&J.gt(0)&d.gt(0))|(2*n>=N))
  hi=(n+U>=3)&(((3*(n+U)>=N)&(d.gt(0)|J.eq(0)))|(2*(n+U)>=N))
  b['M3_candidate']=np.where(lo,1,np.where(~hi,0,-1)).astype('int8');b['previous_sector_state']=b.M3_candidate.shift()
  b['day']=cal;b['industry']=roster.loc[ids[0],'industry'];parts.append(b)
 return pd.concat(parts,ignore_index=True)
def aggregate():
 verify();assert (O/'FEATURES_COMPLETE.json').exists();assert not (O/'SIGNAL_SEAL.json').exists()
 fc=read(O/'FEATURES_COMPLETE.json')
 features={}
 for j,sid in enumerate(sorted(manifest),1):
  if j%50==1:resource_check('aggregate_load_'+str(j))
  p=O/'features'/(sid+'.parquet');assert sha(p)==fc['outputs'][p.name]
  z=pd.read_parquet(p);z.index=pd.DatetimeIndex(z.day);features[sid]=z
 resource_check('aggregate_before_panel')
 panel=panel_from(features);resource_check('aggregate_after_panel');old=pd.read_parquet(CAN/'COMMON_K_COMPARISON.parquet')
 chk=panel.merge(old,on=['day','sector'],suffixes=('_new','_old'))
 for a,b in [('N','N'),('K','K'),('n','M3_n'),('U','U'),('common3_K','common3_K'),('entered3','M3_entered3'),('left3','M3_left3'),('M3_candidate','M3_candidate')]:
  x=a+'_new' if a in old.columns else a;y=b+'_old' if b in panel.columns else b
  # first warm rows lack previous three-day paired history by design; compare research dates only.
  use=chk.day.ge(START)
  assert np.array_equal(chk.loc[use,x].to_numpy(),chk.loc[use,y].to_numpy()),('panel mismatch',a,b)
 panel.to_parquet(O/'RESEARCH_SECTOR_DAILY.parquet',index=False)
 rows=[]
 for sec,g in panel.groupby('sector'):
  resource_check('aggregate_events_'+sec)
  for r in g[g.day.ge(START)&g.M3_candidate.eq(1)].itertuples():
   for sid in members[sec]:
    z=features[sid];d=r.day;q=z.loc[d]
    if q.M3_state!=1:continue
    prev=z.M3_state.shift().loc[d]
    if r.previous_sector_state==0:kind='A_SECTOR_BIRTH'
    elif r.previous_sector_state==1 and prev==0:kind='B_STOCK_BIRTH_DURING_SECTOR'
    elif r.previous_sector_state==1 and prev==1:continue
    else:kind='OTHER_UNKNOWN_OR_LEFT'
    a=q.to_dict();a.update(event_id=f'{d.date()}|{sec}|{sid}|{kind}',event_type=kind,sector=sec,industry=r.industry,previous_stock_state=prev,previous_sector_state=r.previous_sector_state,sector_N=r.N,sector_K=r.K,sector_n=r.n,sector_J=r.common3_K,sector_d=r.entered3-r.left3)
    rows.append(a)
 e=pd.DataFrame(rows);assert not e.duplicated(['day','sid']).any()
 # Raw A/B market identities, not holdings, must match saved 2024/2026 signal regions.
 oe=pd.read_csv(EP/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'],dtype={'window':str})
 oe=oe[oe.window.isin(['2024_924','2026H1_SEMI'])]
 oldset=set(map(tuple,oe[['day','sid','event_type']].to_numpy()))
 ne=e[((e.day.between('2024-09-01','2024-12-31')))|((e.day.between('2026-01-01','2026-06-30'))&e.sector.eq('URFI881121'))]
 newset=set(map(tuple,ne[['day','sid','event_type']].to_numpy()))
 assert oldset==newset,('old market event identities',len(oldset-newset),len(newset-oldset))
 e['birth_AB']=e.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])
 e['base_signal_legal']=e.birth_AB&e.I_qualified&e.PVR_known
 e['close_check']='NOT_BASE_SIGNAL_LEGAL'
 extra=[]
 for n,(idx,r) in enumerate(e[e.base_signal_legal].iterrows()):
  if n%500==0:resource_check('aggregate_close_'+str(n))
  a=checkclose(r.to_dict());a['row']=idx;extra.append(a)
 x=pd.DataFrame(extra).set_index('row')
 for col in x:e.loc[x.index,col]=x[col]
 e['B0_feasible']=e.base_signal_legal&e.close_check.eq('PASS')
 e['B1_feasible']=e.B0_feasible&e.S15_strict_state.eq(1)
 e['B1_gate']=np.where(e.S15_strict_state.eq(1),'PASS',np.where(e.S15_strict_state.eq(0),'REJECT','UNKNOWN'))
 e['B0_rank']=np.nan;e['B1_rank']=np.nan
 for arm in ['B0','B1']:
  z=e[e[arm+'_feasible']].sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True],kind='stable')
  e.loc[z.index,arm+'_rank']=z.groupby(['day','sector'],sort=False).cumcount()+1
  e[arm+'_top2']=e[arm+'_rank'].le(2)
 assert not (e.B1_feasible&~e.B0_feasible).any()
 e['queue_change']=np.select([e.B0_top2&e.B1_top2,e.B0_top2&~e.B1_top2,~e.B0_top2&e.B1_top2],['RETAINED','LOST_B0_SLOT','REPLACEMENT_FROM_ORIGINAL_BIRTHS'],default='NEITHER_TOP2')
 e.to_parquet(O/'ALL_MARKET_EVENTS.parquet',index=False)
 e[e.queue_change.ne('NEITHER_TOP2')].to_csv(O/'ALL_TOP2_CHANGES.csv',index=False)
 # All dates by fixed quarter and industry. No outcome sorting.
 e['quarter']=e.day.dt.to_period('Q').astype(str)
 group=[]
 for keys in [[],['quarter'],['sector','industry'],['quarter','sector','industry'],['event_type']]:
  iterator=[((),e)] if not keys else e.groupby(keys,dropna=False)
  for key,g in iterator:
   key=(key,) if not isinstance(key,tuple) else key
   a=dict(zip(keys,key));a['grouping']='|'.join(keys) or 'ALL';a.update(events=len(g),stocks=g.sid.nunique(),dates=g.day.nunique(),sector_dates=len(g[['day','sector']].drop_duplicates()),AB=int(g.birth_AB.sum()),I_PVR_legal=int(g.base_signal_legal.sum()),B0_feasible=int(g.B0_feasible.sum()),B1_feasible=int(g.B1_feasible.sum()),gate_reject=int((g.B0_feasible&g.B1_gate.eq('REJECT')).sum()),gate_unknown=int((g.B0_feasible&g.B1_gate.eq('UNKNOWN')).sum()),B0_top2=int(g.B0_top2.sum()),B1_top2=int(g.B1_top2.sum()),retained=int(g.queue_change.eq('RETAINED').sum()),lost=int(g.queue_change.eq('LOST_B0_SLOT').sum()),replacement=int(g.queue_change.eq('REPLACEMENT_FROM_ORIGINAL_BIRTHS').sum()))
   group.append(a)
 pd.DataFrame(group).to_csv(O/'COVERAGE_GROUPS.csv',index=False)
 # Identity-frozen case snapshots and fixed ±10 common-session context, even when no original ticket.
 cv=[];contexts=[];pi=panel.set_index(['sector','day']);ei=e.set_index(['sid','day'])
 for c in pd.read_csv(CASES).itertuples():
  d=pd.Timestamp(c.signal_close_date);z=features[c.symbol];base=z.loc[d].to_dict();ps=pi.loc[(c.sector,d)].to_dict()
  base.update(case_id=c.case_id,case_reason=c.reason,sector=c.sector,sector_N=ps['N'],sector_K=ps['K'],sector_n=ps['n'],sector_d=ps['entered3']-ps['left3'],sector_state=ps['M3_candidate'],previous_sector_state=ps['previous_sector_state'])
  if (c.symbol,d) in ei.index:
   er=ei.loc[(c.symbol,d)];base.update({k:er[k] for k in ['event_type','I_qualified','PVR_known','close_check','B0_top2','B1_top2','B1_gate','queue_change']})
  else:base.update(event_type='NO_ORIGINAL_BIRTH_TICKET',B0_top2=False,B1_top2=False)
  cv.append(base)
  n=z.index.get_loc(d);zz=z.iloc[max(0,n-10):min(len(z),n+11)].copy();zz=zz[zz.day.ge(START)];zz['case_id']=c.case_id;contexts.append(zz)
 pd.DataFrame(cv).to_csv(O/'FIXED20_SIGNAL_SNAPSHOTS.csv',index=False)
 pd.concat(contexts).to_parquet(O/'FIXED20_CONTEXT.parquet',index=False)
 outputs=['ALL_MARKET_EVENTS.parquet','ALL_TOP2_CHANGES.csv','COVERAGE_GROUPS.csv','FIXED20_SIGNAL_SNAPSHOTS.csv','FIXED20_CONTEXT.parquet','RESEARCH_SECTOR_DAILY.parquet']
 save('SIGNAL_SEAL.json',dict(at=pd.Timestamp.now(tz='UTC'),outputs={n:sha(O/n) for n in outputs},all_market_identities_exact=True,old_event_rows=len(oldset),panel_overlap_rows=int(use.sum()),no_forward_labels_read=True,no_accounts=True))
 print(pd.DataFrame(group).query("grouping=='ALL' or grouping=='quarter'").to_string(index=False),flush=True)
 print('SIGNAL SEALED',sha(O/'SIGNAL_SEAL.json'),flush=True)
if __name__=='__main__':
 mode=sys.argv[1]
 if mode in ['small','features','aggregate']:
  RUN_START=time.monotonic();RUN_LIMITS=read(O/'FREEZE.json')['limits']
  def timeout_handler(signum,frame):raise RuntimeError('hard wall-time alarm reached')
  signal.signal(signal.SIGALRM,timeout_handler);signal.alarm(int(RUN_LIMITS['max_seconds_main']))
  ok=False
  try:
   {'small':small,'features':feature_main,'aggregate':aggregate}[mode]()
   resource_check(mode+'_final');ok=True
  except Exception as ex:
   save('FAILURE_'+mode+'.json',dict(error=repr(ex),traceback=traceback.format_exc(),no_economics=True))
   raise
  finally:
   signal.alarm(0)
   peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
   if sys.platform!='darwin':peak*=1024
   save('RESOURCE_'+mode+'_FINAL.json',dict(completed=ok,elapsed_seconds=time.monotonic()-RUN_START,peak_rss_bytes=int(peak),limits=RUN_LIMITS,peak_checked_at_boundaries=True,wall_alarm=True))
 elif mode=='freeze':freeze()
 elif mode=='synthetic':print(json.dumps(synthetic()))
 else:raise ValueError(mode)
