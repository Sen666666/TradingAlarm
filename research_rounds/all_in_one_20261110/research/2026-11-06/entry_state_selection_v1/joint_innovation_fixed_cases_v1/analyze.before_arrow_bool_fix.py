"""Frozen J event diagnostic. No accounts, orders, new ranking, optimization, or economic simulation."""
from pathlib import Path
import json, hashlib, math, datetime, itertools, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent; P=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
SN=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot')
CM=P/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
END=pd.Timestamp('2026-06-30'); SOURCES={}; QA={}; START=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 p=Path(p);s=sha(p)
 if expected is not None:assert s==expected,('SOURCE_HASH_MISMATCH',str(p),s,expected)
 SOURCES[str(p)]=s;return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def readj(p):return json.loads(source(p).read_text())
protocol=readj(O/'PROTOCOL.json')
assert not (O/'FEATURE_SEAL.json').exists(),'Already sealed: do not overwrite.'
source(__file__)
cases=pd.read_csv(source(P/'cross_window_entry_mechanism_v1/FIXED_CASES.csv'));cases.day=pd.to_datetime(cases.day)
meta=pd.read_csv(source(P/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')).set_index('sid')
SM={x['symbol']:x for x in readj(U/'STOCK_MANIFEST.json')}
IM={x['series']:x for x in readj(U/'INDUSTRY_MANIFEST.json')}
assert len(cases)==25 and len(meta)==1709 and set(meta.index)==set(SM)
cases=cases.join(meta[['name','industry','sector_id']],on='sid').rename(columns={'sector_id':'sector'})
with np.load(source(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<=END]; di={d:i for i,d in enumerate(cal)}
assert cal.is_unique and cal.is_monotonic_increasing
startup={
 '300085.SZ':('2024-09-01','2024-10-31'), '002583.SZ':('2024-09-01','2024-10-31'),
 '300623.SZ':('2026-01-01','2026-06-30'), '300666.SZ':('2026-01-01','2026-06-30'),
 '301611.SZ':('2026-01-01','2026-06-30'), '603061.SH':('2026-01-01','2026-06-30'),
 '688498.SH':('2026-01-01','2026-06-30')}
target_eval={sid:set() for sid in cases.sid.unique()}
case_context=[]
for c in cases.to_dict('records'):
 idx=di[c['day']]; ds=cal[max(0,idx-63):idx+1]
 target_eval[c['sid']].update(ds)
 case_context += [dict(case_id=c['case_id'],sid=c['sid'],day=d,signal_day=c['day']) for d in ds]
for sid,(a,b) in startup.items():target_eval[sid].update(cal[(cal>=a)&(cal<=b)])
sector_eval={}
for sid,ds in target_eval.items():sector_eval.setdefault(meta.loc[sid,'sector_id'],set()).update(ds)
sector_save={}
for sec,ds in sector_eval.items():
 kept=set()
 for d in ds:kept.update(cal[max(0,di[d]-63):di[d]+1])
 sector_save[sec]=pd.DatetimeIndex(sorted(kept))
sids=sorted(meta[meta.sector_id.isin(cases.sector)].index)
assert len(sids)==389 and cases.sector.nunique()==12

snapshot=pd.read_csv(source(SN/'current-stock-master.industry-resolved.csv'))
bridge=pd.read_csv(source(SN/'a-industry-index-bridge.csv'))
snap_members={sec:set(snapshot.loc[snapshot.industry_index_symbol.eq(sec),'symbol']) for sec in cases.sector.unique()}
univ=[]
for sec in sorted(sector_eval):
 sample=set(meta[meta.sector_id.eq(sec)].index); full=snap_members[sec]
 assert sample.issubset(full),(sec,sorted(sample-full))
 univ.append(dict(sector=sec,industry=meta.loc[next(iter(sample)),'industry'],sample_N=len(sample),
   current_snapshot_N=len(full),outside_sample_N=len(full-sample),sample_share=len(sample)/len(full),
   snapshot_date='2026-10-22',historical_PIT=False,native_index_membership_historical_known=False))
univ=pd.DataFrame(univ);univ.to_csv(O/'UNIVERSE_COVERAGE.csv',index=False)

cmhash=readj(CM/'OUTPUT_HASHES.json')
def cmread(n):return pd.read_parquet(source(CM/n,cmhash.get(n)))
mR=cmread('RIGHT3.parquet');mK=cmread('KNOWN3.parquet');msector=cmread('COMMON_K_COMPARISON.parquet')
msector.day=pd.to_datetime(msector.day);msector=msector.set_index(['sector','day'])

def runlength(valid,ident):
 same=ident.eq(ident.shift()).fillna(False)
 starts=(~valid | ~valid.shift(fill_value=False) | ~same).cumsum()
 return valid.groupby(starts).cumsum().astype(int)
def midrank(x):
 # rank including self = past-less + .5*past-equal + 1.
 return (x.rolling(64,min_periods=64).rank(method='average')-1)/63
def calc(raw,calendar):
 q=raw.reindex(calendar)
 pv=q.close.gt(0)&np.isfinite(q.close)
 for col in ['price_eligible','observed_bar','is_observed_bar']:pv &=q[col].fillna(False).astype(bool)
 for col in ['source_invalid','synthetic_event_bar']:pv &=~q[col].fillna(True).astype(bool)
 pv &= q.raw_volume.gt(0)&np.isfinite(q.raw_volume)
 ident=q.segment_id.astype('string')+'|'+q.source_kind.astype('string')+'|'+q.source_path.astype('string')
 pv &=ident.notna()
 av=pv&q.amount.gt(0)&np.isfinite(q.amount)&q.volume_eligible.fillna(False).astype(bool)
 rp=runlength(pv,ident);rj=runlength(av,ident)
 r=np.log(q.close/q.close.shift()).where(pv&pv.shift(fill_value=False)&ident.eq(ident.shift()).fillna(False))
 s=(1.4826*r.abs().shift().rolling(63,min_periods=63).median()).clip(lower=1e-8)
 z=(r/s).where(rp>=65)
 a=np.log(q.amount/q.amount.shift().rolling(21,min_periods=21).median()).where(rj>=22)
 Uz=midrank(z);Uzj=midrank(z.where(rj>=65));Ua=midrank(a)
 kp=(rp>=128)&Uz.notna();kj=(rj>=128)&Uzj.notna()&Ua.notna()
 # Rank features are integer multiples of1/126; q is exactly integer/63.
 pplus=np.rint((2*Uz-1).clip(lower=0)*63).where(r>0,0).where(kp,-1).astype('int16')
 pminus=np.rint((1-2*Uz).clip(lower=0)*63).where(r<0,0).where(kp,-1).astype('int16')
 jp=np.rint((2*np.minimum(Uzj,Ua)-1).clip(lower=0)*63).where((r>0)&(a>0),0).where(kj,-1).astype('int16')
 jm=np.rint((2*np.minimum(1-Uzj,Ua)-1).clip(lower=0)*63).where((r<0)&(a>0),0).where(kj,-1).astype('int16')
 # Same information domain main control, natural price coverage separately.
 pp=pplus.where(kj,-1).astype('int16');pm=pminus.where(kj,-1).astype('int16')
 out=pd.DataFrame(dict(close=q.close,raw_close=q.raw_close,amount=q.amount,r=r,s=s,z=z,a=a,Uz=Uzj,Ua=Ua,
   price_Uz=Uz,price_run=rp,joint_run=rj,joint_known=kj,price_known=kp,jplus=jp,jminus=jm,
   pplus=pp,pminus=pm,pnatural_plus=pplus,pnatural_minus=pminus,source_identity=ident),index=calendar)
 return out

arrays={k:pd.DataFrame(index=cal,columns=sids,dtype='int16') for k in ['jplus','jminus','pplus','pminus','pnatural_plus','pnatural_minus']}
raw_targets={};target_features={};member_rows=[];scalar=[];prefix=[];QA['scale_floor']=1e-8
for n,sid in enumerate(sids):
 rec=SM[sid];sp=next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet'))
 raw=pd.read_parquet(source(sp,rec['source_sha256'][sp])).loc[:END]
 assert raw.index.is_unique and raw.index.is_monotonic_increasing
 zz=calc(raw,cal)
 for k in arrays:arrays[k][sid]=zz[k]
 ds=sector_save[meta.loc[sid,'sector_id']]
 zr=zz.loc[ds].copy();zr['sid']=sid;zr['sector']=meta.loc[sid,'sector_id'];zr['day']=zr.index
 zr['M3_known']=mK[sid].reindex(ds).fillna(False).astype(bool).to_numpy()
 zr['M3_right']=mR[sid].reindex(ds).where(mK[sid].reindex(ds).fillna(False)).to_numpy()
 member_rows.append(zr.reset_index(drop=True))
 if sid in target_eval:
  raw_targets[sid]=raw;target_features[sid]=zz
  for c in cases[cases.sid.eq(sid)].to_dict('records'):
   t=c['day'];ix=di[t];row=zz.loc[t]
   if row.joint_known:
    oldz=zz.z.where(zz.joint_run>=65).iloc[ix-63:ix].to_numpy()
    olda=zz.a.iloc[ix-63:ix].to_numpy()
    uz=(np.sum(oldz<row.z)+.5*np.sum(oldz==row.z))/63
    ua=(np.sum(olda<row.a)+.5*np.sum(olda==row.a))/63
    qp=max(0,2*min(uz,ua)-1) if row.r>0 and row.a>0 else 0
    qm=max(0,2*min(1-uz,ua)-1) if row.r<0 and row.a>0 else 0
    assert abs(uz-row.Uz)<1e-14 and abs(ua-row.Ua)<1e-14
    assert abs(qp-row.jplus/63)<1e-14 and abs(qm-row.jminus/63)<1e-14
    scalar.append(dict(case_id=c['case_id'],r=float(row.r),s=float(row.s),a=float(row.a),Uz=uz,Ua=ua,qplus=qp,qminus=qm,passed=True))
  if sid in ['000728.SZ','300085.SZ','300623.SZ']:
   cut={'000728.SZ':'2022-04-01','300085.SZ':'2024-09-12','300623.SZ':'2026-01-05'}[sid]
   pp=O/('PREFIX_'+sid+'_'+cut+'.parquet');raw.loc[:cut].to_parquet(pp)
   zsmall=calc(pd.read_parquet(pp),cal[cal<=cut])
   pd.testing.assert_frame_equal(zsmall,zz.loc[:cut],check_exact=True,check_freq=False)
   transformed=raw.copy();transformed['amount']=transformed.amount*10
   transformed[['open','high','low','close']]=transformed[['open','high','low','close']]*10
   zu=calc(transformed,cal)
   # Continuous values and ranks may differ only for exact floating ties after scale.
   for k in ['r','s','z','a']:np.testing.assert_allclose(zu[k],zz[k],rtol=1e-10,atol=1e-12,equal_nan=True)
   changed=int((zu[['jplus','jminus']].to_numpy()!=zz[['jplus','jminus']].to_numpy()).any(axis=1).sum())
   prefix.append(dict(sid=sid,cut=cut,physical_sha256=sha(pp),prefix_exact=True,
       continuous_unit_scaling_passed=True,q_rank_unit_scaling_changed_days=changed))
 if (n+1)%75==0:print('FEATURES',n+1,len(sids),round(time.monotonic()-START,1),flush=True)
members=pd.concat(member_rows,ignore_index=True);members.to_parquet(O/'MEMBER_FEATURES.parquet',index=False)
pd.DataFrame(scalar).to_csv(O/'SCALAR_CHECKS.csv',index=False)
save('PREFIX_CHECKS.json',prefix)

# Algebra/unknown bound check, not financial simulation.
boundchecks=[]
for vals,M in [([0,63],1),([1,17],2),([63,63,0],2),([0],2)]:
 N=len(vals)+M;S=sum(vals);T=sum(x*x for x in vals)
 lo=S*S-T;hi=(S+63*M)**2-(T+63**2*M)
 for extra in itertools.product([0,1,17,62,63],repeat=M):
  allq=vals+list(extra);direct=sum(allq[i]*allq[j] for i in range(N) for j in range(N) if i!=j)
  assert lo<=direct<=hi
 boundchecks.append(dict(known=vals,M=M,lo_numerator=lo,hi_numerator=hi,passed=True))
save('ALGEBRA_QA.json',dict(unknown_bounds=boundchecks,pair_formula_exact=True,
  J_identity='mean(q)^2-population_variance(q)/(N-1)',
  LOO_warning='Not a rank. Removing high ownq mechanically lowers peer J.',
  confidence_interval=False))

def aggregate(qp,qm,Nextra=0):
 # Integer units make interval comparisons and record ties exact.
 N=qp.shape[1]+Nextra
 if N<2:raise ValueError('N<2')
 def one(x):
  K=(x>=0).sum(axis=1).astype(np.int64);v=x.clip(lower=0).astype(np.int64)
  S=v.sum(axis=1);T=(v*v).sum(axis=1);M=N-K
  ln=S*S-T;un=(S+63*M)**2-(T+63**2*M)
  fixed_den=63**2*N*(N-1);kd=63**2*K*(K-1)
  pt=(ln/kd).where(K>=2)
  return pd.DataFrame(dict(N=N,K=K,M=M,positive=(x>0).sum(axis=1),Sunit=S,Tunit=T,
    Lnum=ln,Unum=un,L=ln/fixed_den,U=un/fixed_den,known_point=pt),index=x.index)
 plus=one(qp);minus=one(qm)
 histU=plus.Unum.shift().rolling(63,min_periods=63).max()
 histL=plus.Lnum.shift().rolling(63,min_periods=63).max()
 histPt=plus.known_point.shift().rolling(63,min_periods=63).max()
 true=(plus.Lnum>histU)&(plus.Lnum>minus.Unum)
 false=(plus.Unum<=histL)|(plus.Unum<=minus.Lnum)
 status=pd.Series('UNKNOWN',index=qp.index);status[true]='TRUE';status[false]='FALSE';status[histU.isna()]='UNKNOWN'
 known_event=(plus.known_point>histPt)&(plus.known_point>minus.known_point)
 known_event=known_event.where(histPt.notna()&plus.known_point.notna()&minus.known_point.notna())
 out=plus.add_prefix('plus_').join(minus.add_prefix('minus_'))
 out['event_status']=status;out['known_event']=known_event
 out['prior63_Lnum_max']=histL;out['prior63_Unum_max']=histU;out['prior63_known_max']=histPt
 out['known_record_below_previous_day']=known_event.fillna(False)&plus.known_point.lt(plus.known_point.shift())
 out['known_consecutive_record']=known_event.fillna(False)&known_event.shift().fillna(False)
 # Every exact known panel agrees with direct scalar sign andrecord.
 allknown=(plus.M==0)&(plus.M.shift().rolling(63,min_periods=63).max()==0)
 expected=np.where(known_event.fillna(False),'TRUE','FALSE')
 assert np.all(out.loc[allknown,'event_status'].to_numpy()==expected[allknown])
 return out

# Read only original stock and native index states at same dates, no strategy invocation.
stockstate={}
for sid in target_eval:
 rec=SM[sid]
 f=pd.read_parquet(source(rec['refs']['facts'],rec['output_sha256'].get(rec['refs']['facts']))).reindex(cal)
 cp=pd.read_parquet(source(rec['refs']['CP1'],rec['output_sha256'].get(rec['refs']['CP1']))).reindex(cal)
 stockstate[sid]=f[['i_target','i_floor','i_buy','g_grade','e0_target']].join(cp[['receipt','candidate']],rsuffix='_cp')
sectorstate={}
for sec in sector_eval:
 rec=IM[sec];sp=rec['refs']['state'];s=pd.read_parquet(source(sp,rec['output_sha256'][sp]))
 s.index=pd.to_datetime(s.day);sectorstate[sec]=s.reindex(cal)

daily=[];identrows=[];allagg={};events=[]
for sid,ds0 in target_eval.items():
 sec=meta.loc[sid,'sector_id'];peer=[s for s in sids if meta.loc[s,'sector_id']==sec and s!=sid]
 Nfull=len(snap_members[sec])-1;extra=Nfull-len(peer)
 agj=aggregate(arrays['jplus'][peer],arrays['jminus'][peer])
 agp=aggregate(arrays['pplus'][peer],arrays['pminus'][peer])
 agpn=aggregate(arrays['pnatural_plus'][peer],arrays['pnatural_minus'][peer])
 agfull=aggregate(arrays['jplus'][peer],arrays['jminus'][peer],extra)
 allagg[sid]=agj
 ds=pd.DatetimeIndex(sorted(ds0))
 z=agj.loc[ds].add_prefix('J_').join(agp.loc[ds].add_prefix('PRICE_')).join(agpn.loc[ds].add_prefix('PRICE_NATURAL_')).join(agfull.loc[ds,['plus_N','plus_K','plus_M','plus_L','plus_U','event_status']].add_prefix('FULL_CURRENT_'))
 z['sid']=sid;z['name']=meta.loc[sid,'name'];z['sector']=sec;z['industry']=meta.loc[sid,'industry'];z['day']=ds
 z=z.join(target_features[sid].loc[ds,['r','s','z','a','Uz','Ua','jplus','jminus','joint_known','price_known','joint_run']].add_prefix('target_'))
 z=z.join(stockstate[sid].loc[ds].add_prefix('stock_'))
 ms=msector.reindex(pd.MultiIndex.from_product([[sec],ds],names=['sector','day']));ms.index=ds
 z=z.join(ms[['N','K','M3_n','M3_right_fixed_lower','M3_right_fixed_upper','M3_candidate','M3_observed_candidate','sector_E0_valid','sector_stage','sector_authorization_usable','sector_receipt']].add_prefix('canonical_'))
 # Genuine ordinary M3 member participation, not J-matched population.
 mk=mK.reindex(ds)[peer].fillna(False).astype(bool);mr=mR.reindex(ds)[peer].fillna(False).astype(bool)&mk
 z['M3_LOO_K']=mk.sum(axis=1);z['M3_LOO_n']=mr.sum(axis=1)
 z['M3_LOO_lower']=z.M3_LOO_n/len(peer);z['M3_LOO_upper']=(z.M3_LOO_n+len(peer)-z.M3_LOO_K)/len(peer)
 z['M3_LOO_known_fraction']=(z.M3_LOO_n/z.M3_LOO_K).where(z.M3_LOO_K>0)
 jp=arrays['jplus'].loc[ds,peer];pp=arrays['pplus'].loc[ds,peer]
 z['joint_price_contributor_overlap']=((jp>0)&(pp>0)).sum(axis=1)
 z['joint_M3_contributor_overlap']=((jp>0)&mr).sum(axis=1)
 z['joint_not_M3_known']=((jp>0)&mk&~mr).sum(axis=1)
 z['M3_known_not_joint']=((jp>=0)&mr&~(jp>0)).sum(axis=1)
 z['joint_M3_unknown']=((jp>0)&~mk).sum(axis=1)
 jp_prev=arrays['jplus'][peer].shift().loc[ds]
 z['joint_new_participants']=((jp>0)&(jp_prev==0)).sum(axis=1)
 z['joint_continuing_participants']=((jp>0)&(jp_prev>0)).sum(axis=1)
 z['joint_left_participants']=((jp==0)&(jp_prev>0)).sum(axis=1)
 z['joint_unknown_to_positive']=((jp>0)&(jp_prev<0)).sum(axis=1)
 # Novel dates only descriptive; never call known point a true fixed-population event.
 z['J_vs_PRICE_status']=z.J_event_status+'|'+z.PRICE_event_status
 z['J_known_only_not_price_known_only']=z.J_known_event.fillna(False)&~z.PRICE_known_event.fillna(False)
 daily.append(z.reset_index(drop=True))
 # Preserve all exact contributors on named/fixed/event days, not outcome-selected.
 fixed_dates=set(cases.loc[cases.sid.eq(sid),'day'])
 interesting=set(ds[z.J_known_event.fillna(False).to_numpy()])|set(ds[z.PRICE_known_event.fillna(False).to_numpy()])|fixed_dates
 for d in sorted(interesting):
  for psid in peer:
   val=int(arrays['jplus'].loc[d,psid]);pv=int(arrays['pplus'].loc[d,psid])
   if val>0 or pv>0 or psid in set(cases.sid):
    identrows.append(dict(target_sid=sid,sector=sec,day=d,peer_sid=psid,peer_name=meta.loc[psid,'name'],
      joint_q_int=val,price_q_int=pv,joint_participates=val>0,price_participates=pv>0,
      ordinary_M3_known=bool(mK[psid].get(d,False)) if pd.notna(mK[psid].get(d,False)) else False,
      ordinary_M3_right=bool(mR[psid].get(d,False)) if pd.notna(mR[psid].get(d,False)) else None))
daily=pd.concat(daily,ignore_index=True)
assert not daily.duplicated(['sid','day']).any()
daily.to_csv(O/'TARGET_DAILY_PRELABEL.csv',index=False)
pd.DataFrame(identrows).to_csv(O/'PARTICIPANT_IDENTITIES.csv',index=False)
fixed=cases.merge(daily,on=['sid','day','name','sector','industry'],validate='one_to_one')
for idx,c in fixed.iterrows():
 ag=allagg[c.sid];past=ag.loc[cal[max(0,di[c.day]-63):di[c.day]+1]]
 for label,mask in [('definite',past.event_status.eq('TRUE')),('known_only',past.known_event.fillna(False))]:
  dd=past.index[mask];fixed.loc[idx,'latest_'+label+'_event_day']=str(dd[-1].date()) if len(dd) else None
  fixed.loc[idx,'latest_'+label+'_event_age']=di[c.day]-di[dd[-1]] if len(dd) else np.nan
fixed.to_csv(O/'FIXED_CASES_PRELABEL.csv',index=False)
contexts=pd.DataFrame(case_context).merge(daily,on=['sid','day'],validate='many_to_one')
contexts.to_csv(O/'FIXED_CASE_CONTEXT63.csv',index=False)
strows=[]
for sid,(a,b) in startup.items():
 t=daily[daily.sid.eq(sid)&daily.day.between(a,b)].copy();t['window']=a+'..'+b;strows.append(t)
st=pd.concat(strows,ignore_index=True);st.to_csv(O/'STARTUP_DAILY.csv',index=False)
ev=daily[daily.J_known_event.fillna(False)|daily.PRICE_known_event.fillna(False)|daily.J_event_status.eq('TRUE')|daily.PRICE_event_status.eq('TRUE')]
ev.to_csv(O/'RECORD_EVENT_DATES.csv',index=False)
# Predetermined startup2x2024/5x2026 identities. Statuscount duplicates across LOO targets are not independent events.
summaries=[]
for label,df in [('fixed25',fixed),('startup_target_days',st),('all_evaluation_target_days',daily)]:
 for status in ['TRUE','FALSE','UNKNOWN']:
  summaries.append(dict(scope=label,kind='J_fixed_population_status',status=status,count=int(df.J_event_status.eq(status).sum()),denominator=len(df)))
 summaries += [dict(scope=label,kind=k,count=int(df[k].fillna(False).sum()),denominator=len(df)) for k in ['J_known_event','PRICE_known_event','J_known_only_not_price_known_only']]
pd.DataFrame(summaries).to_csv(O/'EVENT_COUNTS.csv',index=False)
save('FEATURE_SOURCE_HASHES.json',SOURCES)
save('FEATURE_QA.json',dict(scalar_known_cases=len(scalar),fixed_cases=len(fixed),startup_target_days=len(st),
 target_days=len(daily),unique_sector_days=int(daily[['sector','day']].drop_duplicates().shape[0]),
 member_feature_rows=len(members),fixed_pool_members=1709,computed_members=len(sids),computed_sectors=len(sector_eval),
 source_hashes_verified=True,prefix_exact=True,unit_scaling_rank_tie_caveat=prefix,
 strategy_or_account_runs=0,parameter_scans=0,elapsed_seconds=time.monotonic()-START))
feature_files=[p for p in O.iterdir() if p.is_file() and p.name not in ['FEATURE_SEAL.json','run.log']]
save('FEATURE_SEAL.json',dict(sealed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 files={p.name:sha(p) for p in feature_files},labels_read_by_script=False,history_previously_seen=True))
print('SEALED',json.dumps(clean(dict(fixed=len(fixed),startup=len(st),eval=len(daily),counts=summaries,seconds=time.monotonic()-START)),ensure_ascii=False),flush=True)
