"""Frozen fixed-25, market-only diagnostic. Never reads economic labels."""
from pathlib import Path
import ast,hashlib,json,math,datetime,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds'); U=W/'universe-cp1-inputs-20261031'
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
SOURCES={}; QA=[]; START=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,(str(p),'hash mismatch')
 SOURCES[str(p)]=h;return p
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,obj):(O/name).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def readj(p):return json.loads(source(p).read_text())
freeze=readj(O/'SPECIFICATION_FREEZE.json')
for p,h in freeze['sha256'].items():source(O/p,h)
cases=pd.read_csv(O/'FIXED_CASES.csv');cases.day=pd.to_datetime(cases.day);assert len(cases)==25
END=cases.day.max()
SM={x['symbol']:x for x in readj(U/'STOCK_MANIFEST.json')};IM={x['series']:x for x in readj(U/'INDUSTRY_MANIFEST.json')}
meta=pd.read_csv(source(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')).set_index('sid')
assert len(meta)==1709 and set(meta.index)==set(SM)
# Verify persisted fixed mapping against its original metadata authority.
MP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
native_meta=readj(MP)['security_metadata']
assert all(meta.loc[s,'sector_id']==native_meta[s]['sector_id'] for s in meta.index)
cases=cases.join(meta[['industry','sector_id','name']],on='sid').rename(columns={'sector_id':'sector'})
env=dict(np=np,pd=pd);exec(compile(source(FORMULA).read_text(),str(FORMULA),'exec'),env);score=env['score']
source(H)
with np.load(H,allow_pickle=False) as hh:
 cal=pd.DatetimeIndex(hh['dates']); hsy={str(s):i for i,s in enumerate(hh['symbols'])};hc=hh['close'].copy()
hdi={d:i for i,d in enumerate(cal)};cal=cal[cal<=END];di={d:i for i,d in enumerate(cal)}
assert cal.is_unique and cal.is_monotonic_increasing
def loadref(rec,key):return pd.read_parquet(source(rec['refs'][key],rec['output_sha256'][rec['refs'][key]]))
def loadsrc(rec,suffix):
 p=next(p for p in rec['source_sha256'] if p.endswith(suffix));return pd.read_parquet(source(p,rec['source_sha256'][p]))
def pricevalid(p):
 v=p.close.gt(0)&np.isfinite(p.close)
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in p:v &=p[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in p:v &=~p[k].fillna(True).astype(bool)
 if 'raw_volume' in p:v &=p.raw_volume.gt(0)
 return v
def ident(p):
 a=p.segment_id.astype('string')
 for c in ['source_kind','source_path']:a=a+'|'+p[c].astype('string')
 return a
def contiguous(p,dates):
 q=p.reindex(dates);valid=pricevalid(q)
 same=ident(q).notna().all() and ident(q).nunique(dropna=False)==1
 return bool(valid.all() and same)
def root(sector,t):
 rec=IM[sector];raw=loadsrc(rec,'/signal.parquet').loc[:t]
 fpath=next(p for p in rec['source_sha256'] if '/industry-facts/' in p);facts=pd.read_parquet(source(fpath,rec['source_sha256'][fpath])).loc[:t]
 cp=loadref(rec,'CP1_input').loc[:t];st=loadref(rec,'state');st.index=pd.to_datetime(st.day);st=st.loc[:t]
 pd.testing.assert_series_equal(facts.e0_target.astype(bool),cp.e0_valid,check_names=False,check_dtype=False)
 q=raw.reindex(cal[cal<=t]);f=facts.reindex(q.index)
 valid=pricevalid(q)&f.e0_ready.eq(1)&f.e0_target.isin([0,1])&q.segment_id.eq(f.segment_id)
 target=f.e0_target
 z=dict(sector_E0=target.loc[t],sector_E0_root_status=None,sector_E0_birth=None,sector_E0_age=None)
 for c in ['E0_episode','stage','stage_name','action','reason','receipt','attempt_id','authorization_usable']:
  z['sector_'+c]=st.loc[t,c] if t in st.index else None
 if not valid.loc[t]:z['sector_E0_root_status']='CURRENT_E0_UNKNOWN';return z
 if target.loc[t]==0:z['sector_E0_root_status']='E0_OFF';return z
 k=len(q)-1; line=ident(q); a=k
 while a>0 and target.iloc[a-1]==1:
  if not valid.iloc[a-1] or line.iloc[a-1]!=line.iloc[a]:z['sector_E0_root_status']='ROOT_UNKNOWN_MISSING_OR_CHANGED_SOURCE';return z
  a-=1
 if a==0 or not valid.iloc[a-1] or target.iloc[a-1]!=0 or line.iloc[a-1]!=line.iloc[a]:
  z['sector_E0_root_status']='ROOT_UNKNOWN_NO_COMPLETE_0_TO_1';return z
 z.update(sector_E0_root_status='KNOWN',sector_E0_birth=q.index[a],sector_E0_age=k-a)
 # Original state prices and original signal adjusted-price coordinate.
 np.testing.assert_allclose(st.loc[q.index[a]:t,'close'],raw.loc[q.index[a]:t,'close'],rtol=0,atol=1e-10)
 return z
roots=[]
for c in cases.to_dict('records'):roots.append(dict(c,**root(c['sector'],c['day'])))
cases=pd.DataFrame(roots);cases.to_csv(O/'ANCHOR_STATUS_PRELABEL.csv',index=False)
print('ANCHORS',cases[['case_id','sid','day','sector_E0_root_status','sector_E0_birth','sector_E0_age']].to_string(index=False),flush=True)
# Verify reused caches against hash receipts, without any candidate/label files.
cache_hash=readj(R/'pvr_persistence_breadth_v1/OUTPUT_HASHES.json')
def verified_cache(name):
 p=R/'pvr_persistence_breadth_v1'/name
 expected=cache_hash.get(name,cache_hash.get(str(p)))
 if expected is None:
  for ledger in ['FINAL_OUTPUT_HASHES.json','SUPPLEMENT_OUTPUT_HASHES.json']:
   d=readj(R/'pvr_persistence_breadth_v1'/ledger);expected=d.get(name,d.get(str(p)))
   if expected is not None:break
 assert expected is not None,('missing cache identity',name)
 return pd.read_parquet(source(p,expected))
pv=verified_cache('STOCK_DAILY.parquet');pv.day=pd.to_datetime(pv.day);pv=pv.set_index(['sid','day'])
CM=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';cmhash=readj(CM/'OUTPUT_HASHES.json');m3=pd.read_parquet(source(CM/'COMMON_K_COMPARISON.parquet',cmhash['COMMON_K_COMPARISON.parquet']));m3.day=pd.to_datetime(m3.day);m3=m3.set_index(['sector','day'])
RAW={};Z={};members=[];memberpaths=[];targetrows=[];prefix=[]
sids=sorted(meta[meta.sector_id.isin(cases.sector)].index)
for n,sid in enumerate(sids):
 raw=loadsrc(SM[sid],'/signal.parquet').loc[:END];z=score(raw);RAW[sid]=raw;Z[sid]=z
 # Native adjusted-price identity at exact common observations.
 dates=raw.index.intersection(cal);hidx=[hdi[d] for d in dates];hv=hc[hidx,hsy[sid]]
 both=np.isfinite(hv)&np.isfinite(raw.loc[dates,'close'].to_numpy())
 np.testing.assert_allclose(raw.loc[dates,'close'].to_numpy()[both],hv[both],rtol=0,atol=1e-10)
 for c in cases[cases.sector.eq(meta.loc[sid,'sector_id'])&cases.sector_E0_root_status.eq('KNOWN')].to_dict('records'):
  a=pd.Timestamp(c['sector_E0_birth']);t=c['day'];ap=cal[di[a]-1];dates=cal[di[a]-1:di[t]+1]
  ar=z.reindex([a]).iloc[0];cur=z.reindex([t]).iloc[0];known=bool(np.isfinite(ar.e) and contiguous(raw,[ap,a]))
  member=dict(case_id=c['case_id'],sid=sid,target_sid=c['sid'],sector=c['sector'],day=t,anchor=a,previous_common_day=ap,is_target=sid==c['sid'],anchor_e_known=known,anchor_e_reason='KNOWN' if known else 'UNKNOWN_E_OR_IMMEDIATE_SOURCE',anchor_close=raw.close.get(a,np.nan),origin_close=raw.close.get(ap,np.nan),current_close=raw.close.get(t,np.nan))
  for k in ['r','scale','amount_ref','u','b','e']:member['anchor_'+k]=ar[k];member['current_'+k]=cur[k]
  member['anchor_amount']=raw.amount.get(a,np.nan)
  pos=known and ar.e>0;pk=known and contiguous(raw,dates)
  member.update(positive_cohort=pos,weight=float(ar.e) if pos else 0. if known else np.nan,path_known=pk,path_reason='KNOWN' if pk else 'UNKNOWN_MISSING_INVALID_OR_CHANGED_SOURCE',h=np.nan,weighted_h=np.nan,min_day=None,min_log_advance=np.nan,cumulative_log_advance=np.nan,cumulative_log_advance_over_frozen_scale=np.nan)
  if pk:
   lr=np.log(raw.loc[dates[1:],'close']/raw.loc[ap,'close']);member['min_day']=lr.idxmin();member['min_log_advance']=lr.min();member['cumulative_log_advance']=lr.iloc[-1];member['cumulative_log_advance_over_frozen_scale']=lr.iloc[-1]/ar.scale
   if pos:
    assert ar.r>0
    hs=(lr/ar.r).cummin().clip(0,1);member['h']=float(hs.iloc[-1]);member['weighted_h']=float(ar.e*hs.iloc[-1])
    assert np.all(np.diff(hs.to_numpy())<=1e-12)
    for d,lv,hv2 in zip(lr.index,lr,hs):memberpaths.append(dict(case_id=c['case_id'],sid=sid,day=d,close=raw.loc[d,'close'],origin_close=raw.loc[ap,'close'],anchor_r=ar.r,anchor_e=ar.e,log_advance=lv,h=hv2,source_identity=ident(raw.loc[[d]]).iloc[0]))
  members.append(member)
 # One physical prefix for each fixed year, predetermined case, with full-warm data physically truncated.
 for target,cut in [('000728.SZ','2022-04-01'),('300085.SZ','2024-09-12'),('300623.SZ','2026-01-05')]:
  if sid==target:
   cut=pd.Timestamp(cut);pp=O/('PREFIX_'+sid+'_'+str(cut.date())+'.parquet');raw.loc[:cut].to_parquet(pp);small=pd.read_parquet(pp);zz=score(small);pd.testing.assert_frame_equal(zz,z.loc[:cut],check_exact=True,check_freq=False)
   prefix.append(dict(sid=sid,cut=cut,physical_rows=len(small),physical_sha256=sha(pp),pvr_all_fields_exact=True))
 if sid in set(cases.sid):
  facts=loadref(SM[sid],'facts').loc[:END];g=loadsrc(SM[sid],'/signals/'+sid+'.parquet').loc[:END]
  for c in cases[cases.sid.eq(sid)].to_dict('records'):
   t=c['day'];fr=facts.loc[t];gr=g.loc[t];pr=z.loc[t]
   assert fr.g_grade==gr.grade and bool(fr.g_fresh_up)==bool(gr.fresh_up)
   np.testing.assert_allclose(fr.close,raw.loc[t,'close'],rtol=0,atol=1e-10)
   cr=dict(case_id=c['case_id'])
   for k in ['e0_target','e0_ready','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_ready']:cr['stock_'+k]=fr[k]
   for k in ['up_reasons','phase','z5','z21','e0_entered','e0_exited']:cr['stock_'+k]=gr[k]
   for k in ['r','scale','amount_ref','u','b','e','E','score']:cr['PVR_'+k]=pr[k]
   cr['PVR_current_weight']=1/sum(.9**np.arange(21));cr['PVR_current_weighted_e']=pr.e*cr['PVR_current_weight'];cr['PVR_r_over_scale']=pr.r/pr.scale
   cr['amount']=raw.loc[t,'amount'];cr['amount_over_median21']=cr['amount']/pr.amount_ref
   cache=pv.loc[(sid,t)];np.testing.assert_allclose(pr.score,cache.score,rtol=0,atol=1e-10,equal_nan=True)
   cr['PVR_original_cached_score']=cache.score;cr['PVR3_stock_state']=cache.state;cr['PVR_original_known']=bool(np.isfinite(cache.score) and cache.state>=0 and cache.valid_observation)
   for h in [3,21]:
    ds=cal[di[t]-h:di[t]+1];ok=contiguous(raw,ds)
    cr[f'log_advance_{h}_known']=ok;cr[f'log_advance_{h}']=float(np.log(raw.loc[t,'close']/raw.loc[ds[0],'close'])) if ok else np.nan
    cr[f'log_advance_{h}_over_scale']=cr[f'log_advance_{h}']/pr.scale
   # Independent scalar formula at t, fixed exactly original windows.
   ix=raw.index.get_loc(t);segment=raw.segment_id.iloc[ix]
   block=raw.iloc[max(0,ix-84):ix+1]
   if len(block)==85 and block.segment_id.eq(segment).all() and (pricevalid(block)&block.amount.gt(0)).all():
    rv=[math.log(float(block.close.iloc[k]))-math.log(float(block.close.iloc[k-1])) for k in range(1,len(block))]
    scalar_s=max(1.4826*float(np.median(np.abs(rv[-64:-1]))),1e-8); scalar_ref=float(np.median(block.amount.iloc[-22:-1]));scalar_r=math.log(float(block.close.iloc[-1]))-math.log(float(block.close.iloc[-2]));u=math.tanh(scalar_r/scalar_s);b=math.tanh(math.log(float(block.amount.iloc[-1])/scalar_ref));e=u*(1+.5*abs(u)*b)
    np.testing.assert_allclose([scalar_r,scalar_s,scalar_ref,u,b,e],pr[['r','scale','amount_ref','u','b','e']].to_numpy(dtype=float),rtol=1e-12,atol=1e-12)
    QA.append(dict(case_id=c['case_id'],scalar_original_PVR_checked=True))
   targetrows.append(cr)
 if (n+1)%100==0:print('MEMBERS',n+1,len(sids),round(time.monotonic()-START,1),flush=True)
mem=pd.DataFrame(members);mem.to_csv(O/'ALL_MEMBER_CONTRIBUTIONS_PRELABEL.csv',index=False)
pd.DataFrame(memberpaths).to_parquet(O/'ALL_POSITIVE_MEMBER_PATHS_PRELABEL.parquet',index=False)
pd.DataFrame(memberpaths).to_csv(O/'ALL_POSITIVE_MEMBER_PATHS_PRELABEL.csv',index=False)
out=cases.merge(pd.DataFrame(targetrows),on='case_id',validate='one_to_one');summ=[]
for c in cases.to_dict('records'):
 row=dict(case_id=c['case_id']);md=m3.loc[(c['sector'],c['day'])]
 for k in ['N','K','U']:row['M3_'+k]=md[k]
 for k in ['M3_n','M3_right_known','M3_right_fixed_lower','M3_right_fixed_upper','M3_candidate','M3_observed_candidate','PVR3_n','PVR3_right_known','PVR3_right_fixed_lower','PVR3_right_fixed_upper']:row[k]=md[k]
 row['fixed_industry_N']=int((meta.sector_id==c['sector']).sum());row['fixed_LOO_N']=row['fixed_industry_N']-1
 row['zero_age_no_retention_information']=bool(c['sector_E0_age']==0)
 if c['sector_E0_root_status']=='KNOWN':
  gg=mem[mem.case_id.eq(c['case_id'])]
  target=gg[gg.is_target].iloc[0]
  for k in ['anchor_e_known','positive_cohort','weight','h','path_known','anchor_u','anchor_e','min_day','min_log_advance']:row['target_'+k]=target[k]
  for scope,df in [('LOO',gg[~gg.is_target]),('INCLUSIVE',gg)]:
   N=len(df);K=int(df.anchor_e_known.sum());M=N-K;pos=df[df.positive_cohort];kp=pos[pos.path_known];W=pos.weight.sum();Uw=pos.loc[~pos.path_known,'weight'].sum();S=kp.weighted_h.sum();den=W+1.5*M;kw=kp.weight.sum()
   vals=dict(N=N,K=K,M=M,positive_count=len(pos),positive_weight=W,path_known_count=len(kp),path_known_weight=kw,path_unknown_weight=Uw,S=S,R_known=S/kw if kw>0 else np.nan,R_lower=S/den if den>0 else np.nan,R_upper=(S+Uw+1.5*M)/den if den>0 else np.nan,R_equal_known=kp.h.mean(),R_u_known=(kp.anchor_u*kp.h).sum()/kp.anchor_u.sum() if kp.anchor_u.sum()>0 else np.nan,status='NO_POSITIVE_COHORT' if W==0 and M==0 else 'COHORT_OR_PATH_UNKNOWN' if M>0 or Uw>0 else 'KNOWN')
   for cohort,gd in [('participating',pos),('nonparticipating',df[df.anchor_e_known&~df.positive_cohort])]:
    kk=gd[gd.path_known];vals[cohort+'_N']=len(gd);vals[cohort+'_path_known_N']=len(kk);vals[cohort+'_mean_log_advance_over_frozen_scale']=kk.cumulative_log_advance_over_frozen_scale.mean()
   row.update({scope+'_'+k:v for k,v in vals.items()})
 summ.append(row)
out=out.merge(pd.DataFrame(summ),on='case_id',validate='one_to_one');out.to_csv(O/'FIXED_CASE_FEATURES_PRELABEL.csv',index=False)
# Scalar h check independent of vector cummin for all positive known members.
maxerr=0.
for rr in mem[mem.positive_cohort&mem.path_known].to_dict('records'):
 p=RAW[rr['sid']];dates=cal[di[rr['anchor']]:di[rr['day']]+1];v=min(math.log(float(p.loc[d,'close'])/float(rr['origin_close']))/float(rr['anchor_r']) for d in dates);h=max(0.,min(1.,v));maxerr=max(maxerr,abs(h-rr['h']))
assert maxerr<1e-10
source(__file__);save('FEATURE_SOURCE_HASHES.json',SOURCES)
save('FEATURE_QA.json',dict(passed=True,feature_cases=25,sectors=cases.sector.nunique(),members_loaded=len(sids),source_files=len(SOURCES),all_source_hashes_verified=True,raw_and_H1_adjusted_price_exact_tolerance=1e-10,scalar_h_max_abs_error=maxerr,scalar_PVR_checks=QA,physical_prefix_checks=prefix,full_market_context_not_computed=True,no_accounts=True,no_lifecycle=True,no_ranking=True,no_threshold=True,no_label_file_opened=True,publication_PIT=False))
files=['FIXED_CASE_FEATURES_PRELABEL.csv','ALL_MEMBER_CONTRIBUTIONS_PRELABEL.csv','ALL_POSITIVE_MEMBER_PATHS_PRELABEL.parquet','FEATURE_QA.json','FEATURE_SOURCE_HASHES.json']
save('FEATURE_SEAL.json',dict(sealed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),specification_sha256=sha(O/'FIXED_COHORT_SPEC.md'),labels_opened=False,prior_labels_seen_development_diagnostic=True,sha256={f:sha(O/f) for f in files}))
print('DONE',out[['case_id','sid','day','sector_E0_root_status','sector_E0_age','LOO_R_known','LOO_R_lower','LOO_R_upper','LOO_positive_count','LOO_status']].to_string(index=False),flush=True)
