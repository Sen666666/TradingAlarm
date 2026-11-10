from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, time
O=Path(__file__).resolve().parent; R=O.parent; B=R/'breadth_pvr3_priority_v1'; D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
F=U.parent/'pvr-current-v3-information-capital-20261101/original_score_function.py'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SELECTION_SEAL.json').exists()
env=dict(np=np,pd=pd); exec(compile(F.read_text(),str(F),'exec'),env); orig=env['score']
c=pd.read_csv(B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',parse_dates=['day'],low_memory=False)
c=c[c.arm.eq('M3') & c.ranking_common_known & c.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].copy().reset_index(drop=True); assert len(c)==14880
old=pd.read_csv(B/'SEALED_CLOSE_SELECTED.csv'); old=old[old.ranking_strategy.eq('PVR_DESC')&old.arm.eq('M3')]
oldids=set(map(tuple,old[['event_id','sid']].to_numpy())); c['baseline_selected']=[(e,s) in oldids for e,s in zip(c.event_id,c.sid)]
sm={r['symbol']:r for r in json.load(open(U/'STOCK_MANIFEST.json'))}
im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(r['refs']['CP1_input']).index) for r in im]))); cal=cal[cal<=pd.Timestamp('2026-06-30')]
w=.9**np.arange(20,-1,-1); w/=w.sum()
sources={str(p):sha(p) for p in [F,U/'STOCK_MANIFEST.json',B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',B/'SEALED_CLOSE_SELECTED.csv',O/'PROTOCOL.json',Path(__file__)]}
for k in ['E','M','Q','robust_score','positive_mass','negative_mass','max_day_age','positive_day_count','dependency_fraction']: c[k]=np.nan
c['feature_known']=False
aud=[]; prefixes=[]; start=time.monotonic()
for j,(sid,g) in enumerate(c.groupby('sid',sort=True)):
 sp=Path(next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet')))
 p=pd.read_parquet(sp).loc[:g.day.max()]; sources[str(sp)]=sha(sp)
 z=orig(p); target=z.reindex(g.day); err=np.nanmax(abs(target.score.to_numpy()-g.PVR_score.to_numpy()))
 assert err<1e-10,(sid,err)
 a=p.reindex(cal[cal<=g.day.max()]); zz=z.reindex(a.index)
 ident=a[['source_kind','source_path','segment_id']]; valid=a.observed_bar.eq(True)&a.price_eligible.eq(True)&a.volume_eligible.eq(True)&~a.source_invalid.eq(True)&~a.synthetic_event_bar.eq(True)&a.raw_close.gt(0)&a.raw_volume.gt(0)&a.amount.gt(0)&ident.notna().all(axis=1)
 same=ident.eq(ident.shift()).all(axis=1); block=(~same).cumsum()
 known=valid.rolling(22,min_periods=22).sum().eq(22)&block.eq(block.shift(21))&zz.e.notna().rolling(21,min_periods=21).sum().eq(21)
 for ii,row in g.iterrows():
  t=a.index.get_loc(row.day)
  if not bool(known.iloc[t]): continue
  es=zz.e.iloc[t-20:t+1].to_numpy(); ds=es*w; E=float(ds.sum()); M=float(max(0,ds.max())); Q=E-M
  np.testing.assert_allclose(E,zz.E.iloc[t],atol=1e-12,rtol=0)
  vals=[E,M,Q,50+50*np.tanh(2*Q),np.maximum(ds,0).sum(),-np.minimum(ds,0).sum(),20-int(np.argmax(ds)),int((es>0).sum()),M/np.maximum(ds,0).sum() if (ds>0).any() else np.nan]
  c.loc[ii,['E','M','Q','robust_score','positive_mass','negative_mass','max_day_age','positive_day_count','dependency_fraction']]=vals; c.at[ii,'feature_known']=True
 # Fixed deterministic first and last candidate of each window, truncated original reconstruction.
 for _,gg in g.groupby('window',sort=True):
  for t in sorted(set([gg.day.min(),gg.day.max()])):
   pre=orig(p.loc[:t]); pd.testing.assert_frame_equal(pre,z.loc[:t],check_exact=True)
   if t in a.index and known.at[t]:
    ds=pre.e.reindex(a.index[a.index<=t]).iloc[-21:].to_numpy()*w
    got=float(ds.sum()-max(0,ds.max())); expected=float(c.loc[g.index[g.day.eq(t)][0],'Q']); assert abs(got-expected)<1e-12
   prefixes.append(dict(sid=sid,day=t,exact=True))
 aud.append(dict(sid=sid,candidates=len(g),known=int(c.loc[g.index,'feature_known'].sum()),max_score_error=err))
 if (j+1)%300==0: print('FEATURES',j+1,round(time.monotonic()-start,1),flush=True)
# Member age is only descriptive, does not enter selection.
rr=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(D/'RIGHT3.parquet')]).sort_index()
kk=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(D/'KNOWN3.parquet')]).sort_index()
di=rr.index.get_indexer(c.day); si=rr.columns.get_indexer(c.sid); rv=rr.to_numpy(dtype=bool); kv=kk.to_numpy(dtype=bool)
assert (rv[di,si]&kv[di,si]).all()
c['member_state']=np.where(~kv[di-1,si],'PREV_UNKNOWN',np.where(rv[di-1,si],'CONTINUING','FRESH'))
c['new_selected']=False; c['baseline_rank']=0; c['new_rank']=0; pairs=[]
for ev,g in c.groupby('event_id',sort=True):
 base=g.sort_values(['PVR_score','sid'],ascending=[False,True]); order=list(base.index); slots=np.flatnonzero(base.feature_known.to_numpy())
 known=base[base.feature_known].sort_values(['Q','PVR_score','sid'],ascending=[False,False,True])
 for pos,idx in zip(slots,known.index):order[pos]=idx
 K=int(g.baseline_selected.sum()); assert K==min(2,len(g))
 assert set(base.head(K).index)==set(g[g.baseline_selected].index)
 c.loc[base.index,'baseline_rank']=np.arange(1,len(g)+1); c.loc[order,'new_rank']=np.arange(1,len(g)+1); c.loc[order[:K],'new_selected']=True
 rem=[i for i in base.head(K).index if i not in order[:K]]; add=[i for i in order[:K] if i not in base.head(K).index]; assert len(rem)==len(add)
 for a,b in zip(rem,add):pairs.append(dict(pair_id=len(pairs),event_id=ev,window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],sector=g.sector.iloc[0],removed_index=a,added_index=b,removed_sid=c.at[a,'sid'],added_sid=c.at[b,'sid']))
assert c.groupby('event_id').baseline_selected.sum().equals(c.groupby('event_id').new_selected.sum())
assert (c.loc[~c.feature_known,'baseline_rank']==c.loc[~c.feature_known,'new_rank']).all()
c.to_csv(O/'FEATURES_AND_SELECTIONS.csv',index=False); pd.DataFrame(pairs).to_csv(O/'SEALED_CHANGED_PAIRS.csv',index=False)
pd.DataFrame(aud).to_csv(O/'SOURCE_RECONSTRUCTION_QA.csv',index=False); pd.DataFrame(prefixes).to_csv(O/'PREFIX_QA.csv',index=False)
cover=c.groupby(['window','event_type']).agg(N=('sid','size'),known=('feature_known','sum'),oldK=('baseline_selected','sum'),newK=('new_selected','sum')).reset_index(); cover.to_csv(O/'COVERAGE.csv',index=False)
assert all(sha(p)==h for p,h in sources.items())
save('SOURCE_HASHES.json',sources)
files=['PROTOCOL.json','FEATURES_AND_SELECTIONS.csv','SEALED_CHANGED_PAIRS.csv','SOURCE_RECONSTRUCTION_QA.csv','PREFIX_QA.csv']
save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/f):sha(O/f) for f in files},new_forward_labels_loaded=False,candidates=len(c),changed_pairs=len(pairs),source_files=len(sources),prefix_tests=len(prefixes),seconds=time.monotonic()-start))
print(cover.to_string(index=False));print('CHANGES',pd.DataFrame(pairs).groupby(['window','event_type']).size().to_string());print('SEALED')
