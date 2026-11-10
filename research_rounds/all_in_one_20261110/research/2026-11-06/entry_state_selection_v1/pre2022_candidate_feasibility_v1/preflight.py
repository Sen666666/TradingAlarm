"""One bounded historical candidate/data-coverage census. No outcome, fitted model or account."""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,time,traceback,warnings,math
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',category=FutureWarning)
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money')
B=M/'research_rounds/rs-h1-execution-20261025'
AS=M/'research_rounds/a-share-selection-e0-20261024'
IX=M/'research_rounds/ix-a-share-entry-20261025/signals'
CP=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
EP=R/'m3_stock_birth_during_sector_v1'
FORMULA=U.parent/'pvr-current-v3-information-capital-20261101/original_score_function.py'
FEATURES=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
SOURCE=EP/'relative_priority_v1/simulate.py'
SMALL_IDS=['000001.SZ','600036.SH','600519.SH']
SMALL_SECTORS=['URFI881155','URFI881273']
CUTS=['2019-06-28','2021-12-31']
HAND_DATES=['2013-01-04','2019-01-04','2020-03-12','2021-06-30','2021-12-31','2022-01-06']
END='2022-12-30'; H=120
NAV=D('1200000'); INIT=D('24000'); RISK=D('3000'); SLIP=D('.0005')
POSITIVE_MASK_COLUMNS=('price_eligible','observed_bar','is_observed_bar')
NEGATIVE_MASK_COLUMNS=('source_invalid','synthetic_event_bar')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,(pd.Timestamp,Path)):return str(v)
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
def save(name,v):(O/name).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv(name,v):v.to_csv(O/name,index=False)
hashes={}
sealed_expected={}
seal_sources=[]
def add_seal(path,container=None,only=None,relative=False):
 data=read(path);data=data[container] if container else data
 seal_sources.append(str(path))
 for key,value in data.items():
  full=str(Path(path).parent/key) if relative and not Path(key).is_absolute() else key
  if only is not None and full not in only:continue
  if full in sealed_expected:assert sealed_expected[full]==value,(full,'conflicting old seals')
  sealed_expected[full]=value
add_seal(R/'pvr_persistence_breadth_v1/INPUT_HASHES.json')
add_seal(R/'pvr_persistence_breadth_v1/OUTPUT_HASHES.json',relative=True)
add_seal(CP/'OUTPUT_HASHES.json',relative=True)
add_seal(R/'momentum_persistence_breadth_v1/SOURCE_HASHES.json',only={str(R/'momentum_persistence_breadth_v1/analyze.py')})
add_seal(EP/'EVENT_SEAL.json',container='source_hashes')
for k,h in read(EP/'EVENT_SEAL.json')['outputs'].items():
 full=str(EP/k)
 if full in sealed_expected:assert sealed_expected[full]==h,(full,'conflicting event seal')
 sealed_expected[full]=h
add_seal(EP/'relative_priority_v1/FREEZE.json',container='hashes')
add_seal(EP/'relative_priority_equity_run_2022_v1/dynamic/OUTPUT_HASHES.json',only={str(EP/'relative_priority_equity_run_2022_v1/dynamic/RANKING_AUDIT.csv')},relative=True)
def track(p,expected=None):
 p=str(p);h=sha(p)
 if expected is not None:assert h==expected,(p,'sealed input drift')
 if p in sealed_expected:assert h==sealed_expected[p],(p,'old registry sealed input drift')
 if p in hashes:assert hashes[p]==h,(p,'input changed during run')
 hashes[p]=h;return p
def definitions(path,names,env):
 track(path);text=Path(path).read_text();found={}
 for node in ast.parse(text).body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
   source=ast.get_source_segment(text,node);exec(compile(source,str(path)+':definition_only','exec'),env);found[node.name]=hashlib.sha256(source.encode()).hexdigest()
 assert set(found)==set(names),(path,names,found)
 return found
for seal_path in seal_sources:track(seal_path)
DEFINITION_HASHES={}
DEFINITION_HASHES['pvr']=definitions(FORMULA,['score'],globals())
original_pvr=score
DEFINITION_HASHES['clock']=definitions(FEATURES,['original_observation_clock'],globals())
DEFINITION_HASHES['pvr_state']=definitions(R/'pvr_persistence_breadth_v1/experiment.py',['state'],globals())
pvr_state=state
DEFINITION_HASHES['m3']=definitions(CP/'run.py',['native_mu','state'],globals())
m3_state=state
DEFINITION_HASHES['breadth']=definitions(R/'momentum_persistence_breadth_v1/analyze.py',['breadth'],globals())
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
for p in [B/'code/market_rules.py',B/'code/sector_account.py']:track(p)
DEFINITION_HASHES['close_feasibility']=definitions(SOURCE,['finite','true','false','flags','getmeta','fee','size','checkclose','DayFrame'],globals())
sm={x['symbol']:x for x in read(track(U/'STOCK_MANIFEST.json'))}
im={x['series']:x for x in read(track(U/'INDUSTRY_MANIFEST.json'))}
roster=pd.read_csv(track(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')).set_index('sid')
members=roster.groupby('sector_id').apply(lambda g:list(g.index),include_groups=False).to_dict()
assert len(roster)==1709 and roster.index.is_unique and set(roster.index)==set(sm)
assert len(members)==90 and set(members)==set(im)
rules=read(track(B/'inputs-v2/market-rules.json'));proxies=read(track(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
dates=[]
for x in im.values():
 p=x['refs']['CP1_input'];track(p,x['output_sha256'][p]);dates.extend(pd.read_parquet(p,columns=[]).index.tolist())
cal=pd.DatetimeIndex(sorted(set(dates)));cal=cal[cal<=END]
# Six common dates before 2019 are enough for 3-day known-state and paired delta plus previous sector edge.
start_i=cal.searchsorted(pd.Timestamp('2019-01-01')); viewcal=cal[max(0,start_i-6):]
raw={};capacity={};meta={};closecache={}
def source_paths(sid):
 m=sm[sid];return next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),str(IX/(sid+'.parquet')),m['refs']['facts']
def get_source(sid):
 rp,gp,fp=source_paths(sid);m=sm[sid]
 track(rp,m['source_sha256'][rp]);track(gp,m['source_sha256'][gp]);track(fp,m['output_sha256'][fp])
 p=pd.read_parquet(rp).loc[:END]
 g=pd.read_parquet(gp,columns=['close','volume','segment_id','valid_strength_observation','z5']).loc[:END]
 return p,g
def get_facts(sid):
 p=source_paths(sid)[2];return pd.read_parquet(p).loc[:END]
def load(sid):
 if sid in raw:return
 p,_=get_source(sid)
 raw[sid]=DayFrame(p[['raw_open','raw_close','adjustment_factor','source_kind','source_path','segment_id','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']])
 vol=p.raw_volume[p.raw_volume.gt(0)]
 capacity[sid]=(vol.rolling(20,min_periods=20).mean()*.01).reindex(p.index).ffill().to_dict()
def panels(K,M3,P):
 both=K&P.ge(0);parts=[]
 for sec,ids in members.items():
  b=breadth(sec,ids,both,M3&both)
  n,N,U,J,delta=b.n,b.N,b.U,b.common3_K,b.entered3-b.left3
  lo=(n>=3)&(((3*n>=N)&J.gt(0)&delta.gt(0))|(2*n>=N))
  hi=(n+U>=3)&(((3*(n+U)>=N)&(delta.gt(0)|J.eq(0)))|(2*(n+U)>=N))
  b['M3_candidate']=np.where(lo,1,np.where(~hi,0,-1))
  b['day']=b.index;parts.append(b.reset_index(drop=True))
 return pd.concat(parts,ignore_index=True)
def stock_calc(sid,calendar=cal,cut=None):
 p,g=get_source(sid)
 if cut is not None:p=p.loc[:cut];g=g.loc[:cut]
 x=original_pvr(p);ps=pvr_state(p,x.score,calendar)
 ms=m3_state(g,p,calendar)
 return p,g,x,ps,ms
def manual_pvr(p,day):
 """Scalar calculation of the 21 effective observations and all lagged windows."""
 valid,blocks=original_observation_clock(p)
 if day not in p.index or not valid.loc[day]:return np.nan
 block=blocks.loc[day];g=p.loc[valid&blocks.eq(block)].loc[:day]
 if len(g)<85:return np.nan
 closes=g.close.to_numpy();amount=g.amount.to_numpy();logs=np.log(closes)
 rs=np.r_[np.nan,np.array([logs[j]-logs[j-1] for j in range(1,len(logs))])]
 weights=np.array([.9**j for j in range(20,-1,-1)]);weights/=sum(weights)
 es=[]
 for j in range(len(g)-21,len(g)):
  scale=max(float(np.median(np.abs(rs[j-63:j])))*1.4826,1e-8)
  ar=float(np.median(amount[j-21:j]));u=float(np.tanh(rs[j]/scale));b=float(np.tanh(np.log(amount[j]/ar)))
  es.append(u*(1+.5*abs(u)*b))
 return 50+50*np.tanh(2*float(np.dot(weights,np.array(es))))
def manual_mu(g,day):
 if day not in g.index or not bool(g.loc[day,'valid_strength_observation']):return np.nan
 segment=g.loc[day,'segment_id'];q=g[(g.segment_id==segment)&g.valid_strength_observation].loc[:day]
 if len(q)<65:return np.nan
 anchor=float(q.close.iloc[0]);last=0.;m=np.nan
 for j,c in enumerate(q.close.iloc[1:],start=1):
  x=float(np.log(c/anchor));r=x-last;last=x;m=r if j==1 else r/3+2*m/3
 return m
def run_small():
 stage=O/'SMALL_CHECKS.json';assert not stage.exists()
 ids=sorted(set(sum([members[s] for s in SMALL_SECTORS],[])))
 ks={};rs={};pss={};hand=[];pref=[]
 for sid in ids:
  p,g,x,ps,ms=stock_calc(sid)
  ks[sid]=ms.known;rs[sid]=ms.right;pss[sid]=ps.state
  for cut in CUTS:
   cc=cal[cal<=cut];xx=original_pvr(p.loc[:cut]);pp=pvr_state(p.loc[:cut],xx.score,cc);mm=m3_state(g.loc[:cut],p.loc[:cut],cc)
   pd.testing.assert_frame_equal(xx,x.loc[:cut],check_exact=True)
   pd.testing.assert_frame_equal(pp,ps.loc[:cut],check_exact=True)
   pd.testing.assert_frame_equal(mm,ms.loc[:cut],check_exact=True)
   pref.append(dict(sid=sid,cut=cut,dataframe_prefix_recomputation_exact=True))
  if sid in SMALL_IDS:
   for dt in HAND_DATES:
    d=pd.Timestamp(dt);a=manual_pvr(p,d);b=float(x.loc[d,'score']);mu=manual_mu(g,d);cached=float(ms.loc[d,'mu5'])
    assert (np.isnan(a) and np.isnan(b)) or abs(a-b)<1e-10,(sid,d,'scalar pvr',a,b)
    assert (np.isnan(mu) and np.isnan(cached)) or (abs(mu-cached)<1e-14 and np.sign(mu)==np.sign(cached)),(sid,d,'scalar mu',mu,cached)
    if np.isfinite(mu) and np.isfinite(g.loc[d,'z5']):assert np.sign(mu)==np.sign(g.loc[d,'z5'])
    ix=cal.get_loc(d);window=cal[ix-2:ix+1]
    identities=[tuple(str(p.loc[t,c]) for c in ['segment_id','source_kind','source_path']) if t in p.index else None for t in window]
    km=all(t in g.index and bool(g.loc[t,'valid_strength_observation']) and t in p.index and all(true(p.loc[t,c]) for c in ['observed_bar','price_eligible','volume_eligible']) and false(p.loc[t,'source_invalid']) and p.loc[t,'close']>0 and p.loc[t,'volume']>0 and finite(manual_mu(g,t)) for t in window) and len(set(identities))==1
    rm=km and all(manual_mu(g,t)>0 for t in window)
    assert km==bool(ms.loc[d,'known']) and rm==bool(ms.loc[d,'right'])
    clock_valid,_=original_observation_clock(p)
    kp=all(t in p.index and bool(clock_valid.loc[t]) and finite(manual_pvr(p,t)) and p.loc[t,'raw_volume']>0 for t in window) and len(set(identities))==1
    scalar_ps=(1 if all(manual_pvr(p,t)>=60 for t in window) else 0) if kp else -1
    assert scalar_ps==int(ps.loc[d,'state']),(sid,d,'manual PVR state')
    hand.append(dict(sid=sid,day=d,scalar_pvr=a,canonical_pvr=b,scalar_mu=mu,canonical_mu=cached,M3_known=km,M3_right=rm,PVR_state=int(ps.loc[d,'state'])))
 K=pd.DataFrame(ks);Q=pd.DataFrame(rs);P=pd.DataFrame(pss);industry=[]
 small_members=members.copy()
 # Main production aggregation restricted to the two complete small industries.
 for sec in list(members):
  if sec not in SMALL_SECTORS:members.pop(sec)
 reference_panel=panels(K,Q,P).set_index(['day','sector'])
 members.clear();members.update(small_members)
 for sec in SMALL_SECTORS:
  ids=members[sec];both=K[ids]&P[ids].ge(0);b=breadth(sec,ids,both,Q[ids]&both)
  for dt in HAND_DATES:
   d=pd.Timestamp(dt);j=cal.get_loc(d);prev=cal[j-3];known=[s for s in ids if K.at[d,s] and P.at[d,s]>=0]
   right=[s for s in known if Q.at[d,s]];pair=[s for s in known if K.at[prev,s] and P.at[prev,s]>=0]
   entered=sum(Q.at[d,s] and not Q.at[prev,s] for s in pair);left=sum(not Q.at[d,s] and Q.at[prev,s] for s in pair)
   expected=dict(N=len(ids),K=len(known),n=len(right),U=len(ids)-len(known),common3_K=len(pair),entered3=entered,left3=left)
   for k,v in expected.items():assert v==b.loc[d,k],(sec,d,k)
   n=expected['n'];N=len(ids);u=N-len(known);J=len(pair);delta=entered-left
   low=n>=3 and ((3*n>=N and J>0 and delta>0) or 2*n>=N)
   high=n+u>=3 and ((3*(n+u)>=N and (delta>0 or J==0)) or 2*(n+u)>=N)
   scalar_gate=1 if low else 0 if not high else -1
   assert scalar_gate==reference_panel.loc[(d,sec),'M3_candidate'],(sec,d,'manual industry gate')
   industry.append(dict(sector=sec,day=d,**expected,scalar_gate=scalar_gate))
  for cut in CUTS:
   pd.testing.assert_frame_equal(breadth(sec,ids,both.loc[:cut],(Q[ids]&both).loc[:cut]),b.loc[:cut],check_exact=True)
 assert len(hand)==len(SMALL_IDS)*len(HAND_DATES) and len(industry)==len(SMALL_SECTORS)*len(HAND_DATES)
 assert any(not r['M3_known'] for r in hand) and any(r['M3_known'] for r in hand)
 # In-memory source-identity poison verifies the declared three-session UNKNOWN reset.
 reset_tests=[]
 for sid in SMALL_IDS:
  p,g,x,ps,ms=stock_calc(sid)
  d=pd.Timestamp('2021-12-31');poison=p.loc[:d].copy();poison.loc[d,'source_path']=str(poison.loc[d,'source_path'])+'|SYNTHETIC_TEST_ONLY'
  cc=cal[cal<=d];pp=pvr_state(poison,original_pvr(poison).score,cc);mm=m3_state(g.loc[:d],poison,cc)
  assert pp.loc[d,'state']==-1 and not bool(mm.loc[d,'known'])
  reset_tests.append(dict(sid=sid,day=d,source_change_PVR_UNKNOWN=True,source_change_M3_UNKNOWN=True))
 save('SMALL_RESET_TESTS.json',reset_tests)
 csv('SMALL_STOCK_HAND_CALCULATIONS.csv',pd.DataFrame(hand))
 csv('SMALL_SECTOR_HAND_CALCULATIONS.csv',pd.DataFrame(industry));csv('SMALL_SOURCE_PREFIX_CHECKS.csv',pd.DataFrame(pref))
 save('SMALL_CHECKS.json',dict(status='PASS',three_named_stocks=SMALL_IDS,two_industries=SMALL_SECTORS,industry_member_stocks=len(set(sum([members[s] for s in SMALL_SECTORS],[]))),dataframe_prefix_checks=len(pref),prefix_scope='In-memory raw input frames truncated before recomputation; not isolated on-disk input files',stock_hand_rows=len(hand),industry_hand_rows=len(industry),no_outcomes=True))
 print('SMALL_PASS',len(pref),flush=True)
def emit_events(panel,K,M3,P,S,V,lo,hi,original_left_boundary=False):
 rows=[];prevM=M3.astype('int8').where(K,-1).shift();curM=M3.astype('int8').where(K,-1)
 for sec,gg in panel.groupby('sector',sort=True):
  gg=gg.sort_values('day').copy();gg['previous_sector_state']=gg.M3_candidate.shift()
  if original_left_boundary:gg.loc[gg.day.eq(pd.Timestamp(lo)),'previous_sector_state']=np.nan
  use=gg[gg.day.between(lo,hi)&gg.M3_candidate.eq(1)]
  for z in use.itertuples():
   for sid in members[sec]:
    if curM.at[z.day,sid]!=1:continue
    prev=prevM.at[z.day,sid]
    if z.previous_sector_state==0:typ='A_SECTOR_BIRTH'
    elif z.previous_sector_state==1 and prev==0:typ='B_STOCK_BIRTH_DURING_SECTOR'
    elif z.previous_sector_state==1 and prev==1:continue
    else:typ='OTHER_UNKNOWN_OR_LEFT'
    score=S.at[z.day,sid];pstate=int(P.at[z.day,sid])
    rows.append(dict(day=z.day,sid=sid,sector=sec,event_type=typ,previous_sector_state=z.previous_sector_state,previous_stock_state=prev,PVR_score=score,PVR_state=pstate,PVR_known=bool(np.isfinite(score) and pstate>=0 and V.at[z.day,sid]),sector_N=z.N,sector_K=z.K,sector_M3_n=z.n,sector_delta3=z.delta3))
 out=pd.DataFrame(rows)
 assert not out.duplicated(['day','sid']).any()
 for sid,g in out.groupby('sid'):
  f=get_facts(sid).reindex(pd.DatetimeIndex(g.day))
  for c in ['e0_ready','g_ready','i_target','i_floor','i_buy','g_grade','factor','raw_close']:out.loc[g.index,c]=f[c].to_numpy()
 out['I_qualified']=out.e0_ready.eq(1)&out.g_ready.eq(True)&out.i_target.eq(1)&np.isfinite(out.i_floor)&out.i_floor.gt(0)
 out['I_and_PVR_known']=out.I_qualified&out.PVR_known
 return out
def add_feasibility(events):
 rows=[]
 for sid,g in events.groupby('sid',sort=True):
  for r in g.to_dict('records'):
   if not true(r['I_qualified']):status='I_INELIGIBLE';q={}
   elif not true(r['PVR_known']) or not finite(r['PVR_score']):status='PVR_UNKNOWN';q={}
   else:q=checkclose(r);status=q['close_check']
   rows.append(dict(**r,close_feasibility=status,**{k:v for k,v in q.items() if k!='close_check'}))
  raw.pop(sid,None);capacity.pop(sid,None)
 return pd.DataFrame(rows)
def run_all():
 assert read(O/'SMALL_CHECKS.json')['status']=='PASS'
 assert not (O/'COMPLETE.json').exists()
 started=time.monotonic();ks={};rs={};pss={};scores={};valids={};presence={};observed={};sourceinfo=[]
 for j,sid in enumerate(sorted(sm)):
  p,g,x,ps,ms=stock_calc(sid)
  ks[sid]=ms.known.reindex(viewcal);rs[sid]=ms.right.reindex(viewcal);pss[sid]=ps.state.reindex(viewcal);scores[sid]=ps.score.reindex(viewcal);valids[sid]=ps.valid_observation.reindex(viewcal)
  first=p.index[p.observed_bar.eq(True)].min();presence[sid]=pd.Series(viewcal>=first,index=viewcal)
  observed[sid]=p.observed_bar.reindex(viewcal).eq(True)
  sourceinfo.append(dict(sid=sid,first_observed_source_day=first,last_observed_source_day=p.index[p.observed_bar.eq(True)].max(),sector=roster.loc[sid,'sector_id'],first_source_observation_before_2019=first<pd.Timestamp('2019-01-01'),first_source_observation_before_2020=first<pd.Timestamp('2020-01-01'),first_source_observation_before_2021=first<pd.Timestamp('2021-01-01')))
  if (j+1)%300==0:print('SIGNAL_PREP',j+1,round(time.monotonic()-started,1),flush=True)
 K=pd.DataFrame(ks);Q=pd.DataFrame(rs);P=pd.DataFrame(pss);S=pd.DataFrame(scores);V=pd.DataFrame(valids);Presence=pd.DataFrame(presence);Observed=pd.DataFrame(observed)
 panel=panels(K,Q,P);oldpanel=pd.read_parquet(track(CP/'COMMON_K_COMPARISON.parquet'));oldpanel=oldpanel[oldpanel.day.between('2022-01-01',END)]
 newpanel=panel[panel.day.between('2022-01-01',END)]
 cols=['N','K','U','common3_K','M3_candidate'];ren={'n':'M3_n','entered3':'M3_entered3','left3':'M3_left3','delta3':'M3_delta3'}
 comp=newpanel.rename(columns=ren).set_index(['day','sector']).sort_index()
 old=oldpanel.set_index(['day','sector']).sort_index()
 assert comp.index.is_unique and old.index.is_unique and comp.index.equals(old.index)
 assert newpanel.sector.nunique()==90 and len(newpanel)==90*newpanel.day.nunique()
 for c in cols+list(ren.values()):np.testing.assert_equal(comp[c].to_numpy(),old[c].to_numpy(),err_msg=c)
 oldstock=pd.read_parquet(track(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'),columns=['day','sid','score','state','valid_observation'])
 oldstock=oldstock[oldstock.day.between('2022-01-01',END)]
 for name,data in [('score',S),('state',P),('valid_observation',V)]:
  pivot=oldstock.pivot(index='day',columns='sid',values=name).sort_index(axis=1)
  new=data.reindex(index=pivot.index,columns=pivot.columns)
  if name=='score':np.testing.assert_allclose(new.to_numpy(),pivot.to_numpy(),rtol=0,atol=1e-10,equal_nan=True)
  else:np.testing.assert_equal(new.to_numpy(),pivot.to_numpy())
 for name,data in [('KNOWN3.parquet',K),('RIGHT3.parquet',Q)]:
  old=pd.read_parquet(track(CP/name)).loc['2022-01-01':END];np.testing.assert_equal(data.reindex(index=old.index,columns=old.columns).to_numpy(),old.to_numpy())
 ev22=emit_events(panel,K,Q,P,S,V,'2022-01-04',END,original_left_boundary=True)
 oldev=pd.read_csv(track(EP/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False);oldev=oldev[oldev.window.eq('2022')]
 keys=['day','sid'];a=ev22.set_index(keys).sort_index();b=oldev.set_index(keys).sort_index()
 assert a.index.equals(b.index),(len(a),len(b),'2022 event identity')
 for c in ['event_type','PVR_state','PVR_known','I_qualified','I_and_PVR_known']:np.testing.assert_equal(a[c].to_numpy(),b[c].to_numpy(),err_msg=c)
 for c in ['PVR_score','sector_delta3','i_floor']:np.testing.assert_allclose(a[c],b[c],rtol=0,atol=1e-10,equal_nan=True,err_msg=c)
 ab22=add_feasibility(ev22[ev22.event_type.ne('OTHER_UNKNOWN_OR_LEFT')].copy())
 rankpath=EP/'relative_priority_equity_run_2022_v1/dynamic/RANKING_AUDIT.csv'
 ra=pd.read_csv(track(rankpath),usecols=['day','sid','arm','stock_state_before','ranking_feasibility','original_feasible_rank'],parse_dates=['day'])
 ra=ra[ra.arm.eq('A_UNION_B')&ra.stock_state_before.eq('FLAT')]
 mm=ra.merge(ab22,on=['day','sid'],validate='one_to_one')
 assert len(mm)==len(ra);assert mm.ranking_feasibility.eq(mm.close_feasibility).all(),mm[mm.ranking_feasibility.ne(mm.close_feasibility)][['day','sid','ranking_feasibility','close_feasibility']].head().to_dict('records')
 # Restore native baseline rank on only its original FLAT/PASS subset, without using lifecycle profit or actions.
 passed=mm[mm.close_feasibility.eq('PASS')].sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True])
 computed=passed.groupby(['day','sector']).cumcount()+1
 assert np.array_equal(computed.to_numpy(),passed.original_feasible_rank.to_numpy())
 save('REGRESSION_2022.json',dict(status='PASS',sector_days=len(newpanel),stock_days=len(oldstock),all_original_events=len(ev22),AB_events=len(ab22),original_FLAT_checks=len(mm),original_PASS_ranks=len(passed),pvr_absolute_tolerance=1e-10,states_and_events_exact=True,original_left_boundary_preserved=True,full_new_prefix_boundary_separately_reported=True,no_profit_action_or_round_file_loaded=True))
 print('REGRESSION_PASS',len(ab22),len(mm),flush=True)
 # No new historical candidate output or coverage decision is made before both gates pass.
 hist=emit_events(panel,K,Q,P,S,V,'2019-01-01','2021-12-31')
 other=hist[hist.event_type.eq('OTHER_UNKNOWN_OR_LEFT')].copy()
 ev=add_feasibility(hist[hist.event_type.ne('OTHER_UNKNOWN_OR_LEFT')].copy())
 ev=ev.sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True],na_position='last')
 ev['event_id']=['PRE2022|'+r.event_type+'|'+str(r.day.date())+'|'+r.sector+'|'+r.sid for r in ev.itertuples()]
 ev['year']=ev.day.dt.year;ev['month']=ev.day.dt.strftime('%Y-%m')
 feasible=ev.close_feasibility.eq('PASS')
 ev['potential_flat_PVR_rank']=np.nan;ev.loc[feasible,'potential_flat_PVR_rank']=ev[feasible].groupby(['day','sector']).cumcount()+1
 counts=ev[feasible].groupby(['day','sector']).size()
 ev['feasible_competitors']=[int(counts.get((d,s),0)) for d,s in zip(ev.day,ev.sector)]
 ev['same_K']=[min(2,n) for n in ev.feasible_competitors]
 ev['potential_flat_selected']=feasible&ev.potential_flat_PVR_rank.le(ev.same_K)
 ev['queue_scope']='INDEPENDENT_FLAT_OPPORTUNITY_NOT_DYNAMIC_ADMISSION'
 csv('ALL_AB_CANDIDATES.csv',ev);csv('OTHER_UNKNOWN_OR_LEFT.csv',other);csv('STOCK_SOURCE_PRESENCE.csv',pd.DataFrame(sourceinfo))
 sec=panel[panel.day.between('2019-01-01','2021-12-31')].copy();csv('INDUSTRY_DAILY_CAUSAL.csv',sec)
 perday=pd.DataFrame(dict(day=viewcal,first_source_observation_reached=Presence.sum(axis=1),observed_today=Observed.sum(axis=1),M3_known=K.sum(axis=1),PVR_known=P.ge(0).sum(axis=1),common_known=(K&P.ge(0)).sum(axis=1)))
 perday=perday[perday.day.between('2019-01-01','2021-12-31')];perday['month']=perday.day.dt.strftime('%Y-%m');perday['year']=perday.day.dt.year
 csv('DAILY_SOURCE_COVERAGE.csv',perday)
 for period in ['year','month']:
  s=ev.groupby([period,'event_type']).agg(raw_events=('sid','size'),stocks=('sid','nunique'),signal_dates=('day','nunique'),industries=('sector','nunique'),I_qualified=('I_qualified','sum'),I_and_PVR_known=('I_and_PVR_known','sum'),feasible=('close_feasibility',lambda x:x.eq('PASS').sum()),potential_flat_selected=('potential_flat_selected','sum')).reset_index()
  csv('CANDIDATE_COUNTS_'+period.upper()+'.csv',s)
  csv('FEASIBILITY_REASONS_'+period.upper()+'.csv',ev.groupby([period,'close_feasibility']).size().rename('rows').reset_index())
  csv('SOURCE_COVERAGE_'+period.upper()+'.csv',perday.groupby(period).agg(days=('day','size'),mean_observed=('observed_today','mean'),min_observed=('observed_today','min'),mean_M3_known=('M3_known','mean'),mean_PVR_known=('PVR_known','mean'),mean_common_known=('common_known','mean'),source_presence_start=('first_source_observation_reached','first'),source_presence_end=('first_source_observation_reached','last')).reset_index())
 groups=ev.groupby(['day','sector']).agg(raw_AB=('sid','size'),feasible=('close_feasibility',lambda x:x.eq('PASS').sum()),potential_flat_selected=('potential_flat_selected','sum')).reset_index();groups['competition_gt_K']=groups.feasible.gt(2);groups['year']=groups.day.dt.year;groups['month']=groups.day.dt.strftime('%Y-%m')
 csv('COMPETITION_GROUPS.csv',groups)
 for period in ['year','month']:csv('COMPETITION_'+period.upper()+'.csv',groups.groupby(period).agg(all_groups=('day','size'),feasible_groups=('feasible',lambda x:x.gt(0).sum()),competitive_groups=('competition_gt_K','sum'),total_feasible=('feasible','sum'),total_sameK=('potential_flat_selected','sum'),max_competitors=('feasible','max')).reset_index())
 # Full-warm versus original 2022 display-left boundary is transparent, not silently merged into the old baseline.
 warm22=emit_events(panel,K,Q,P,S,V,'2022-01-04','2022-01-04',original_left_boundary=False)
 csv('ORIGINAL_2022_LEFT_BOUNDARY_COMPARISON.csv',ev22[ev22.day.eq('2022-01-04')][['day','sid','event_type']].merge(warm22[['day','sid','event_type']],on=['day','sid'],how='outer',suffixes=('_original','_full_warm')))
 coverage(ev[feasible].copy())
 save('SOURCE_HASHES.json',hashes)
 assert all(sha(p)==h for p,h in hashes.items()),'source changed'
 summary=dict(status='COMPLETE_CANDIDATE_AND_DATA_COVERAGE_ONLY',AB_events=len(ev),feasible_candidates=int(feasible.sum()),potential_flat_selected=int(ev.potential_flat_selected.sum()),other_unknown_or_left=len(other),signal_days=ev.day.nunique(),sectors=ev.sector.nunique(),stocks=ev.sid.nunique(),competition_groups=int(groups.competition_gt_K.sum()),source_files=len(hashes),source_hashes_unchanged=True,seconds=time.monotonic()-started,model_fits=0,outcome_or_return_computations=0,account_runs=0,actual_lifecycle_labels_computed=0,PIT=False,meaning='New historical selection/data census, not strategy improvement or a completed training set')
 save('COMPLETE.json',summary);print('COMPLETE',json.dumps(clean(summary),ensure_ascii=False),flush=True)
def coverage(ev):
 """Inventory candidate potential follow-up requirements without calculating returns or positions."""
 fullcal=cal;idx={d:i for i,d in enumerate(fullcal)};eventrows=[];pathrows=[];action_index={};public={}
 root=EP/'cash_dividend_source_feasibility_v1/raw'
 for p in root.glob('*.json'):
  x=read(track(p));sid=x['sid']
  for e in x.get('raw',{}).get('records',[]):
   d=e.get('F023D')
   if d:public.setdefault((sid,d),[]).append(e)
 for sid,g in ev.groupby('sid',sort=True):
  p,gg=get_source(sid);f=get_facts(sid);ap=AS/'inputs-v1/actions'/(sid+'.json')
  a=read(track(ap));terms=a.get('events',[]);cover=a.get('coverage_evidence',[])
  for c in cover:track(c['path'],c['sha256'])
  rp=p.reindex(fullcal);valid=rp.observed_bar.eq(True)&rp.price_eligible.eq(True)&rp.volume_eligible.eq(True)&rp.source_invalid.eq(False)&rp.synthetic_event_bar.eq(False)&rp.raw_open.gt(0)&rp.raw_close.gt(0)&np.isfinite(rp.raw_open)&np.isfinite(rp.raw_close)
  identity=rp.source_kind.astype('string')+'|'+rp.source_path.astype('string')+'|'+rp.segment_id.astype('string')
  ff=f.reindex(fullcal);native=ff.e0_ready.eq(1)&ff.g_ready.eq(True)&ff.i_target.notna()
  for r in g.itertuples():
   di=idx[r.day];ei=di+1;hi=ei+H-1;entry=fullcal[ei] if ei<len(fullcal) else pd.NaT;horizon=fullcal[hi] if hi<len(fullcal) else pd.NaT
   mature=pd.notna(horizon) and horizon<=pd.Timestamp('2021-12-31')
   lo=ei;end=min(hi,len(fullcal)-1);inds=fullcal[lo:end+1]
   # Only the requested 2019-2021 information cutoff is inspected for new history.
   knowninds=inds[inds<=pd.Timestamp('2021-12-31')]
   support=len(knowninds)==H
   good=bool(support and valid.reindex(knowninds).all())
   one=bool(support and identity.reindex(fullcal[di:end+1]).notna().all() and identity.reindex(fullcal[di:end+1]).nunique()==1)
   factor=rp.adjustment_factor.reindex(fullcal[di:min(end,idx[pd.Timestamp('2021-12-31')])+1])
   stable=bool(support and np.isfinite(factor).all() and np.isclose(factor.to_numpy(),factor.iloc[0],rtol=1e-11).all())
   ns=bool(support and native.reindex(knowninds).all())
   actual_terms=[(j,e) for j,e in enumerate(terms) if str(entry.date())<=e.get('effective_date','')<=str(min(horizon,pd.Timestamp('2021-12-31')).date())] if pd.notna(entry) and pd.notna(horizon) else []
   # Ex-date at entry may require coordinate handling even with no record-date position.
   ids=[];minimal_public=0
   for j,e in actual_terms:
    eid=sid+'|LOCAL_DISTRIBUTION_'+str(j+1).zfill(3);ids.append(eid);pub=public.get((sid,e['effective_date']),[])
    unique=len(pub)==1;prec=pub[0] if unique else {}
    cash=float(e.get('cash_per_old_share',0));split=float(e.get('split_ratio',1));pure=split==1
    dates_ok=bool(unique and prec.get('F006D') and prec.get('F018D') and (cash==0 or prec.get('F020D')))
    minimal_public+=dates_ok
    if eid not in action_index:
     action_index[eid]=dict(action_id=eid,sid=sid,effective_date=e['effective_date'],cash_per_old_share=e.get('cash_per_old_share'),split_ratio=e.get('split_ratio'),pure_cash=pure,old_paid_at=e.get('paid_at'),old_new_shares_sellable_at=e.get('new_shares_sellable_at'),current_public_matches=len(pub),public_announcement=prec.get('F006D'),public_record=prec.get('F018D'),public_pay=prec.get('F020D'),public_shares_arrival=prec.get('F025D'),public_minimum_dates_present=dates_ok,public_new_shares_tradable_date_certified=False,admitted_2019_2021_economic_fact=False,source_only_not_actual_claim=True)
    eventrows.append(dict(event_id=r.event_id,action_id=eid,sid=sid,signal_day=r.day,entry_proxy_day=entry,horizon_day=horizon,potential_flat_selected=r.potential_flat_selected,relation='POTENTIAL_120_DAY_INTERVAL_OVERLAP_NOT_HELD_CLAIM'))
   source_nonempty=not bool(a.get('raw_response_empty',False))
   proxy_no_action=good and one and stable and ns and not actual_terms and source_nonempty and not a.get('unresolved')
   pathrows.append(dict(event_id=r.event_id,sid=sid,day=r.day,year=r.year,month=r.month,potential_flat_selected=r.potential_flat_selected,entry_proxy_day=entry,horizon_day=horizon,mature_by_20211231=mature,full120_observed_price_open_valid=good,full120_one_source_segment=one,full120_factor_stable=stable,full120_original_core_fields_ready=ns,potential_interval_source_events=len(ids),public_minimum_dates_events=minimal_public,old_actions_source_nonempty=source_nonempty,old_actions_source_unresolved=len(a.get('unresolved',[])),zero_action_conditional_proxy_data_available=proxy_no_action,full_economic_label_certified=False,actual_holdings_or_returns_computed=False))
  print('COVERAGE_STOCK',sid,len(g),flush=True) if len(g)>100 else None
 paths=pd.DataFrame(pathrows);csv('ALL_FEASIBLE_120D_DATA_COVERAGE.csv',paths);csv('POTENTIAL_ACTION_REQUIREMENTS.csv',pd.DataFrame(action_index.values()));csv('CANDIDATE_ACTION_OVERLAP.csv',pd.DataFrame(eventrows))
 for period in ['year','month']:
  for selected,label in [(None,'ALL'),(True,'PVR_TOPK'),(False,'UNSELECTED')]:
   v=paths if selected is None else paths[paths.potential_flat_selected.eq(selected)]
   q=v.groupby(period).agg(candidates=('event_id','size'),mature=('mature_by_20211231','sum'),price_path=('full120_observed_price_open_valid','sum'),same_source=('full120_one_source_segment','sum'),factor_stable=('full120_factor_stable','sum'),original_core_fields_ready=('full120_original_core_fields_ready','sum'),zero_action_conditional_proxy=('zero_action_conditional_proxy_data_available','sum'),with_actions=('potential_interval_source_events',lambda x:x.gt(0).sum()),event_overlaps=('potential_interval_source_events','sum')).reset_index()
   for c in ['mature','price_path','same_source','factor_stable','original_core_fields_ready','zero_action_conditional_proxy']:q[c+'_fraction_all']=q[c]/q.candidates
   csv('POTENTIAL_120D_SOURCE_COVERAGE_'+period.upper()+'_'+label+'.csv',q)
 save('COVERAGE_BOUNDARIES.json',dict(calendar_last=cal.max(),fixed_label_information_cutoff='2021-12-31',H=120,first_entry_day_counts_as_day1=True,all_feasible_candidates=len(paths),mature=int(paths.mature_by_20211231.sum()),unique_potential_actions=len(action_index),candidate_action_overlaps=len(eventrows),public_cash_source_files=len(list(root.glob('*.json'))),certified_full_economic_labels=0,zero_label_certification_does_not_mean_zero_possible_conditional_paths=True,no_action_proxy='Full120 price/source/partial original-core-field/factor support and nonempty legacy no-event evidence. Only a conservative source-support screen, not a simulated outcome, CP lifecycle readiness, complete issuer certification, proven tradability or total-return label.',action_scope='Historical source events intersecting potential next-open through120-common-session intervals. Not actual held entitlement requirements; actual I exit and CP profit/position paths not simulated. Requirements may include events after actual early exits. Payers/record dates outside ex-date interval can require further checks.',mature_scope='Administrative maturity alone, not proof of full lifecycle closure, W/L or total-return label availability.',NON_PIT=True))
def main():
 track(Path(__file__))
 assert not (O/'FREEZE.json').exists(),'One bounded run only; preserve failed results'
 save('FREEZE.json',dict(name='pre2022_candidate_feasibility_v1',frozen_before_new_candidate_outputs=True,scope='Reconstruct frozen original signals and A+B candidate domain for2019-2021. Do not fit, calculate outcomes/returns, simulate holdings or run accounts.',small_stocks=SMALL_IDS,small_industries=SMALL_SECTORS,cuts=CUTS,hand_dates=HAND_DATES,gate_order=['three-stock/two-industry independent scalar and truncated-dataframe prefix checks','whole2022 same-definition state/event/flat feasibility/rank regression','2019-2021 candidate and120day source-coverage census'],population='Same fixed future1709/90 NON-PIT. Stock presence means first observed source record, not PIT issuer master. No future-company deletion or roster changes.',sameK='Each industry/date K=min(2,all t-close-feasible independent FLAT candidates), PVR desc then sid. Not the dynamic consumer or available-capital admission.',economic_contract='Original24k nominal/3k planned risk at1200k NAV,5bp slippage,dated fee/lot,20 strictly-positive raw-volume observations including current close-day observation, no additional validity mask as in original implementation. No modifications.',original_boundary='2022 regression reproduces original first panel day prevS UNKNOWN; full-warm first-day alternative reported separately. New2019 census uses sufficient actual warm prefix.',label_data='120 common days inclusive next-open entry; all information for a hypothetical pre2022 fit must end2021-12-31. No W/L/U or total PnL labels produced.',coverage='Only existing local actions and existing426 public raw responses; no external fetches. Potential interval events not actual held claims. Full economic certification remains unavailable.',small_definition_hashes=DEFINITION_HASHES,initial_source_hashes=hashes,code_sha256=sha(__file__),no_parameter_search=True,no_strategy_improvement_claim=True))
 run_small();run_all()
 save('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
if __name__=='__main__':
 try:main()
 except Exception as e:
  save('FAILED.json',dict(error=repr(e),traceback=traceback.format_exc(),stage='See completed gate files; no pass inferred for subsequent stages'))
  raise
