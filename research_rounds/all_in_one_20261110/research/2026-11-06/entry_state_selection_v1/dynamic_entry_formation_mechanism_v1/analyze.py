"""Descriptive entry-clock anatomy on repaired dynamic baseline; never execute orders or replay a strategy."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1';D=E/'relative_priority_equity_run_2022_v1';P=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
sources={str(p) for p in [Path(__file__),D/'report/CORE_AND_FULL_ROUNDS.csv',D/'dynamic/DECISIONS.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',U/'STOCK_MANIFEST.json',H,P/'COMMON_K_COMPARISON.parquet',P/'RIGHT3.parquet',P/'KNOWN3.parquet',P/'WARM_PREFIX_M_R.parquet',P/'WARM_PREFIX_M_K.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv']}
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<=pd.Timestamp('2026-06-30')];di={d:i for i,d in enumerate(cal)}
b=pd.read_csv(D/'report/CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip',low_memory=False);b=b[b.arm.eq('A_UNION_B')].copy()
dec=pd.read_csv(D/'dynamic/DECISIONS.csv',float_precision='round_trip',low_memory=False);dec=dec[dec.arm.eq('A_UNION_B')].copy()
events=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',float_precision='round_trip',low_memory=False);events=events[events.window.eq('2022')&events.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
assert len(b)==2732 and b.event_id.is_unique and dec.event_id.is_unique
roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');assert len(roster)==1709
rr=pd.concat([pd.read_parquet(P/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(P/'RIGHT3.parquet')]).sort_index().reindex(cal)
kk=pd.concat([pd.read_parquet(P/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(P/'KNOWN3.parquet')]).sort_index().reindex(cal)
panel=pd.read_parquet(P/'COMMON_K_COMPARISON.parquet');sec={s:g.set_index('day').M3_candidate.reindex(cal) for s,g in panel.groupby('sector')}
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet');pv=pv[pv.day.between('2022-01-01','2022-12-31')].set_index(['sid','day'])
facts={};eventfeatures=[];probes=[];start=time.time()
for ni,sid in enumerate(roster.index):
 fp=manifest[sid]['refs']['facts'];assert sha(fp)==manifest[sid]['output_sha256'][fp];sources.add(fp)
 f=pd.read_parquet(fp).reindex(cal);seg=f.segment_id;adjacent=seg.notna()&seg.shift().notna()&seg.eq(seg.shift())
 sp=next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'));assert sha(sp)==manifest[sid]['source_sha256'][sp];sources.add(sp)
 lineage=pd.read_parquet(sp,columns=['source_kind','source_path','segment_id']).reindex(cal)
 for lc in ['source_kind','source_path','segment_id']:
  adjacent=adjacent&lineage[lc].notna()&lineage[lc].shift().notna()&lineage[lc].eq(lineage[lc].shift())
 fields={}
 for target,label in [('i_target','I'),('e0_target','E0')]:
  known=f[target].isin([0,1])&seg.notna()
  boundary=f[target].eq(1)&f[target].shift().eq(0)&adjacent&known&known.shift(fill_value=False)
  reset=~f[target].eq(1)|~adjacent|~known
  roots=np.full(len(f),-1,dtype=int);root=-1
  reseta=reset.fillna(True).to_numpy(dtype=bool);bounda=boundary.fillna(False).to_numpy(dtype=bool);ona=f[target].eq(1).fillna(False).to_numpy(dtype=bool)
  for j in range(len(f)):
   if reseta[j]:root=-1
   if bounda[j]:root=j
   roots[j]=root if ona[j] else -1
  fields[label+'_root_idx']=roots;fields[label+'_birth']=boundary.to_numpy()
 fields['I_age']=np.where(fields['I_root_idx']>=0,np.arange(len(f))-fields['I_root_idx'],np.nan)
 ir=pd.Series(fields['I_root_idx'],index=cal)
 buy=f.i_buy.eq(True)&f.i_target.eq(1)
 buyord=buy.groupby(ir).cumsum();buyord[ir.lt(0)]=np.nan
 fields['i_buy_ordinal']=buyord.to_numpy()
 iq=f.e0_ready.eq(1)&f.g_ready.eq(True)&f.i_target.eq(1)&f.i_floor.gt(0)&pd.Series(np.isfinite(pd.to_numeric(f.i_floor,errors='coerce').to_numpy(dtype=float,na_value=np.nan)),index=cal)
 m=rr[sid].eq(True)&kk[sid].eq(True);mk=kk[sid].eq(True)
 s=sec[roster.loc[sid,'sector_id']]
 continuous=s.eq(1)&s.shift().eq(1)&m&m.shift(fill_value=False)&mk&mk.shift(fill_value=False)
 # Additional clock receipt only. Not a new executed strategy; baseline-state/unused-slot proxy below.
 c=continuous&pd.Series(fields['I_birth'],index=cal)&iq&adjacent
 c=c&pd.Series(cal.year==2022,index=cal)
 sg=events[events.sid.eq(sid)]
 for r in sg.itertuples():
  t=pd.Timestamp(r.day);j=di[t];v=f.loc[t]
  for key in ['e0_target','i_target','i_buy','g_grade','g_fresh_up','g_acute_down']:
   a=getattr(r,key);bb=v[key];assert (pd.isna(a) and pd.isna(bb)) or a==bb,(sid,t,key,a,bb)
  root=fields['I_root_idx'][j]
  eventfeatures.append(dict(event_id=r.event_id,I_root=str(cal[root].date()) if root>=0 else None,I_age=fields['I_age'][j],I_clock='FIRST_KNOWN_I_0_TO_1' if fields['I_birth'][j] else 'LATER_I_BUY' if pd.notna(v.i_buy) and v.i_buy==True else 'PERSISTENT_I_NO_BUY',I_root_known=root>=0,E0_root=str(cal[fields['E0_root_idx'][j]].date()) if fields['E0_root_idx'][j]>=0 else None,E0_birth=bool(fields['E0_birth'][j]),i_buy_ordinal=fields['i_buy_ordinal'][j],previous_G=f.g_grade.iloc[j-1],current_G=v.g_grade,original_I_distance_log=np.log(v.close/v.i_floor) if v.i_floor>0 else np.nan))
 for t in cal[c.fillna(False).to_numpy(dtype=bool)]:
  j=di[t];r=pv.loc[(sid,t)];g=b[b.sid.eq(sid)]
  prior=g[pd.to_datetime(g.signal_day)<=t].sort_values('signal_day');state='FLAT';owner=None
  if len(prior):
   last=prior.iloc[-1];owner=last.round_id
   if 'UNKNOWN' in last.status:state='UNKNOWN' if t>=pd.Timestamp(last.status_day) else 'BUY_PENDING' if pd.isna(last.entry_day) or t<pd.Timestamp(last.entry_day) else 'HELD'
   elif last.status=='COMPLETE_CONDITIONAL_STOCK_ROUND':state='FLAT' if t>=pd.Timestamp(last.exit_day) else 'BUY_PENDING' if t<pd.Timestamp(last.entry_day) else 'HELD'
   elif 'NOFILL' in last.status:state='FLAT' if t>=pd.Timestamp(last.status_day) else 'BUY_PENDING'
   else:state='OTHER_UNRESOLVED'
  probes.append(dict(day=str(t.date()),sid=sid,name=roster.loc[sid,'name'],sector=roster.loc[sid,'sector_id'],I_root=str(t.date()),e0_target=f.at[t,'e0_target'],i_buy=f.at[t,'i_buy'],g_grade=f.at[t,'g_grade'],PVR_score=r.score,PVR_known=bool(pd.notna(r.score) and r.state>=0 and r.valid_observation),baseline_state=state,baseline_previous_round=owner,adjusted_close=f.at[t,'close'],raw_close=f.at[t,'raw_close']))
 if (ni+1)%400==0:print('LOADED',ni+1,round(time.time()-start,1),flush=True)
ef=pd.DataFrame(eventfeatures)
ev=events.merge(ef,on='event_id',validate='one_to_one')
ev=ev.sort_values(['sid','day'])
ev['qualified_AB_ordinal_in_I']=np.nan
ok=ev.I_and_PVR_known&ev.I_root_known
ev.loc[ok,'qualified_AB_ordinal_in_I']=ev[ok].groupby(['sid','I_root']).cumcount()+1
feas=dec[dec.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])][['event_id','decision']]
ev=ev.merge(feas,on='event_id',how='left',validate='one_to_one')
ok=ev.decision.notna()&ev.I_root_known
ev['feasible_AB_ordinal_in_I']=np.nan;ev.loc[ok,'feasible_AB_ordinal_in_I']=ev[ok].groupby(['sid','I_root']).cumcount()+1
extra=[c for c in ev.columns if c not in b.columns or c=='event_id']
z=b.merge(ev[extra],on='event_id',validate='one_to_one')
z=z.sort_values(['sid','signal_day']);z['admission_ordinal']=z.groupby('sid').cumcount()+1
z['admission_kind']=np.where(z.admission_ordinal.eq(1),'FIRST_ADMISSION_IN_2022','LATER_ADMISSION')
z['prior_status']=z.groupby('sid').status.shift()
z['reentry_kind']=np.where(z.admission_ordinal.eq(1),'FIRST_ADMISSION_IN_2022',np.where(z.prior_status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND'),'AFTER_ACTUAL_EXIT',np.where(z.prior_status.str.contains('NOFILL').fillna(False),'AFTER_NOFILL','OTHER')))
z['first_feasible_in_I']=z.feasible_AB_ordinal_in_I.map(lambda v:'UNKNOWN_ROOT' if pd.isna(v) else 'FIRST_FEASIBLE_AB' if v==1 else 'LATER_FEASIBLE_AB')
z.loc[z.I_root.notna()&z.I_root.lt('2022-01-01'),'first_feasible_in_I']='LEFT_CENSORED_PRE2022_I'
z['quarter']=pd.to_datetime(z.signal_day).dt.quarter
z['month']=pd.to_datetime(z.signal_day).dt.to_period('M').astype(str)
z['i_age_bucket']=pd.cut(z.I_age,[-1,0,5,20,np.inf],labels=['0_BIRTH','1_5','6_20','21_PLUS']).astype(str)
z['g_transition']=np.where(z.current_G.gt(z.previous_G),'UPGRADE',np.where(z.current_G.lt(z.previous_G),'DOWNGRADE',np.where(z.current_G.eq(z.previous_G),'SAME','UNKNOWN')))
z['tail30']=z.core_return.ge(.3);z['tail50']=z.core_return.ge(.5)
z.to_csv(O/'BASELINE_ENTRY_FEATURES.csv',index=False)
def metric(g):
 c=g[g.evidence_usable_closed];cond=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
 return dict(admitted=len(g),conditional_closed=len(cond),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),closed_coverage_unknown=int((cond.financial_coverage_status=='COVERAGE_UNKNOWN').sum()),evidence_closed=len(c),wins=int(c.core_net.gt(0).sum()),losses=int(c.core_net.lt(0).sum()),win_rate=float(c.core_net.gt(0).mean()) if len(c) else None,net_sum_cny=float(c.core_net.sum()) if len(c) else None,mean_net_cny=float(c.core_net.mean()) if len(c) else None,mean_return=float(c.core_return.mean()) if len(c) else None,tail30=int(c.tail30.sum()),tail50=int(c.tail50.sum()),conditional_win_rate=float(cond.core_net.gt(0).mean()) if len(cond) else None)
out=[]
fields=['event_type','admission_kind','reentry_kind','e0_target','I_clock','i_buy','g_grade','g_fresh_up','g_acute_down','g_transition','first_feasible_in_I','i_age_bucket','previous_stock_state','already_invited_at_sector_birth','quarter']
for field in fields:
 for val,g in z.groupby(field,dropna=False):out.append(dict(feature=field,value=str(val),**metric(g)))
pd.DataFrame(out).to_csv(O/'STRATA.csv',index=False)
out=[]
for fs in [['event_type','admission_kind'],['event_type','I_clock'],['event_type','first_feasible_in_I'],['event_type','g_grade'],['quarter','event_type'],['quarter','admission_kind'],['quarter','I_clock'],['quarter','g_grade'],['quarter','i_buy'],['event_type','i_buy'],['quarter','event_type','admission_kind']]:
 for val,g in z.groupby(fs,dropna=False):out.append(dict(features='|'.join(fs),values='|'.join(map(str,val)),**metric(g)))
pd.DataFrame(out).to_csv(O/'CROSS_STRATA.csv',index=False)
# Date-equal conditional comparison, not causal effects or outcome-based matching.
res=[]
for field in ['event_type','admission_kind','I_clock','i_buy','first_feasible_in_I']:
 c=z[z.evidence_usable_closed]
 for v in c[field].dropna().unique():
  a=c[c[field].eq(v)].groupby('signal_day').agg(n=('sid','size'),wr=('core_net',lambda x:(x>0).mean()),mean=('core_net','mean'))
  bb=c[~c[field].eq(v)].groupby('signal_day').agg(n=('sid','size'),wr=('core_net',lambda x:(x>0).mean()),mean=('core_net','mean'))
  j=a.join(bb,lsuffix='_group',rsuffix='_other',how='inner')
  res.append(dict(feature=field,value=str(v),overlap_dates=len(j),date_equal_win_diff=(j.wr_group-j.wr_other).mean(),date_equal_mean_net_diff=(j['mean_group']-j['mean_other']).mean(),group_rounds_on_common_dates=j.n_group.sum(),other_rounds_on_common_dates=j.n_other.sum()))
pd.DataFrame(res).to_csv(O/'DATE_EQUAL_DESCRIPTIVE.csv',index=False)
# Qualified I-birth clock preflight, not close-quantity-checked/orderable new entries.
pc=pd.DataFrame(probes)
ab=set(zip(ev.sid,ev.day));assert not any((r.sid,r.day) in ab for r in pc.itertuples())
ad=dec[dec.decision.eq('SELECTED_PENDING')].groupby(['day','sector']).size()
pc['baseline_AB_K']=[int(ad.get((d,s),0)) for d,s in zip(pc.day,pc.sector)]
pc['remaining_slots']=(2-pc.baseline_AB_K).clip(lower=0)
pc['baseline_flat_knownPVR']=pc.baseline_state.eq('FLAT')&pc.PVR_known
pc['unverified_close_feasibility']=True
eligible=pc[pc.baseline_flat_knownPVR].sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True]).copy()
eligible['prequantity_rank']=eligible.groupby(['day','sector']).cumcount()+1
pc=pc.merge(eligible[['day','sid','prequantity_rank']],on=['day','sid'],how='left',validate='one_to_one')
pc['fits_residual_slot_before_quantity']=pc.baseline_flat_knownPVR&pc.prequantity_rank.le(pc.remaining_slots)
pc.to_csv(O/'I_BIRTH_CLOCK_PREFLIGHT.csv',index=False)
pc.groupby(['baseline_state','PVR_known','baseline_AB_K']).size().to_csv(O/'I_BIRTH_CLOCK_SCOPE.csv')
summary={'baseline':metric(z),'clock_probe':{'raw_stock_receipts':len(pc),'stocks':pc.sid.nunique(),'baseline_flat_knownPVR':int(pc.baseline_flat_knownPVR.sum()),'fits_residual_slot_before_quantity':int(pc.fits_residual_slot_before_quantity.sum()),'unknown_baseline_state':int(pc.baseline_state.eq('UNKNOWN').sum()),'not_executed_or_quantity_checked':True},'qa':{'original_2732_identical_ids':set(z.round_id)==set(b.round_id),'I_root_unknown_in_admitted':int((~z.I_root_known).sum()),'event_fact_exact_checks':len(ev),'first_vs_reentry_only_since2022':True,'no_new_strategy_or_account':True,'cached_signal_state_not_upstream_PIT_proof':True,'seconds':time.time()-start}}
save(O/'SUMMARY.json',summary);save(O/'SOURCE_HASHES.json',{p:sha(p) for p in sorted(sources)})
save(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,indent=2));print(pd.DataFrame(out).to_string(index=False))
