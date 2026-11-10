from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');F=U.parent/'pvr-current-v3-information-capital-20261101/original_score_function.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SELECTION_SEAL.json').exists()
env=dict(pd=pd,np=np);exec(compile(F.read_text(),str(F),'exec'),env);score=env['score']
c=pd.read_csv(B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',parse_dates=['day'],dtype={'window':str},low_memory=False);c=c[c.arm.eq('M3')&c.ranking_common_known&c.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].copy().reset_index(drop=True)
old=pd.read_csv(B/'SEALED_CLOSE_SELECTED.csv');old=old[old.ranking_strategy.eq('PVR_DESC')&old.arm.eq('M3')];ids=set(map(tuple,old[['event_id','sid']].to_numpy()));c['baseline_selected']=[(e,s) in ids for e,s in zip(c.event_id,c.sid)]
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))};im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index) for x in im])));cal=cal[cal<=pd.Timestamp('2026-06-30')]
hashes={str(p):sha(p) for p in [F,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',B/'SEALED_CLOSE_SELECTED.csv',O/'PROTOCOL.json',Path(__file__)]+[Path(x['refs']['CP1_input']) for x in im]}
cols=['r','s','q','u','b','m','e','E','current_stress','Q','new_score','G_grade','G_acute_down','raw_close','prev_raw_close','amount','amount_ref']
for col in cols:c[col]=np.nan
c['feature_known']=False;qa=[];pre=[];start=time.monotonic();w0=1/sum(.9**np.arange(21))
for j,(sid,g) in enumerate(c.groupby('sid',sort=True)):
 m=sm[sid];sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));fp=Path(m['refs']['facts']);p=pd.read_parquet(sp).loc[:g.day.max()];f=pd.read_parquet(fp).loc[:g.day.max()];z=score(p)
 hashes[str(sp)]=sha(sp);hashes[str(fp)]=sha(fp)
 a=p.reindex(cal[cal<=g.day.max()]);zz=z.reindex(a.index);ff=f.reindex(a.index)
 ident=a[['source_kind','source_path','segment_id']];valid=a.observed_bar.eq(True)&a.price_eligible.eq(True)&a.volume_eligible.eq(True)&~a.source_invalid.eq(True)&~a.synthetic_event_bar.eq(True)&a.raw_close.gt(0)&a.raw_volume.gt(0)&a.amount.gt(0)&ident.notna().all(axis=1)
 known=valid&valid.shift(fill_value=False)&ident.eq(ident.shift()).all(axis=1)&a.adjustment_factor.eq(a.adjustment_factor.shift())&zz[['r','scale','u','b','e','E']].notna().all(axis=1)&zz.scale.gt(0)
 err=float(np.nanmax(abs(z.score.reindex(g.day).to_numpy()-g.PVR_score.to_numpy())));assert err<1e-10,(sid,err)
 for ii,row in g.iterrows():
  t=row.day;v=zz.loc[t];q=v.r/v.scale;mult=1+.5*abs(v.u)*v.b;stress=w0*mult*(min(q,0)-min(v.u,0));Q=v.E+stress
  c.loc[ii,cols]=[v.r,v.scale,q,v.u,v.b,mult,v.e,v.E,stress,Q,50+50*np.tanh(2*Q),ff.at[t,'g_grade'],float(ff.at[t,'g_acute_down']),a.at[t,'raw_close'],a.raw_close.shift().at[t],a.at[t,'amount'],v.amount_ref]
  c.at[ii,'feature_known']=bool(known.at[t]) and np.isfinite(Q)
  if bool(c.at[ii,'feature_known']):
   assert abs(mult*v.u-v.e)<1e-12
   assert stress<=1e-12
   if v.r>=0:assert stress==0
 for _,gg in g.groupby('window'):
  for t in sorted(set([gg.day.min(),gg.day.max()])):
   short=score(p.loc[:t]);pd.testing.assert_frame_equal(short,z.loc[:t],check_exact=True);pre.append(dict(sid=sid,day=t,original_score_prefix_exact=True))
 qa.append(dict(sid=sid,n=len(g),known=int(c.loc[g.index,'feature_known'].sum()),max_score_error=err))
 if (j+1)%300==0:print('FEATURES',j+1,round(time.monotonic()-start,1),flush=True)
c['new_selected']=False;c['baseline_rank']=0;c['new_rank']=0;pairs=[]
for ev,g in c.groupby('event_id',sort=True):
 base=g.sort_values(['PVR_score','sid'],ascending=[False,True]);order=list(base.index);slots=np.flatnonzero(base.feature_known.to_numpy());kn=base[base.feature_known].sort_values(['Q','PVR_score','sid'],ascending=[False,False,True])
 for pos,ii in zip(slots,kn.index):order[pos]=ii
 K=int(g.baseline_selected.sum());assert K==min(2,len(g));assert set(base.head(K).index)==set(g[g.baseline_selected].index)
 c.loc[base.index,'baseline_rank']=np.arange(1,len(g)+1);c.loc[order,'new_rank']=np.arange(1,len(g)+1);c.loc[order[:K],'new_selected']=True
 rem=[i for i in base.head(K).index if i not in order[:K]];add=[i for i in order[:K] if i not in base.head(K).index]
 for a,b in zip(rem,add):pairs.append(dict(pair_id=len(pairs),event_id=ev,window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],sector=g.sector.iloc[0],removed_sid=c.at[a,'sid'],added_sid=c.at[b,'sid']))
assert c.groupby('event_id').baseline_selected.sum().equals(c.groupby('event_id').new_selected.sum());assert (c.loc[~c.feature_known,'baseline_rank']==c.loc[~c.feature_known,'new_rank']).all()
c.to_csv(O/'FEATURES_AND_SELECTIONS.csv',index=False);pd.DataFrame(pairs).to_csv(O/'SEALED_PAIRS.csv',index=False);pd.DataFrame(qa).to_csv(O/'SOURCE_QA.csv',index=False);pd.DataFrame(pre).to_csv(O/'PREFIX_QA.csv',index=False)
known=c[c.feature_known];known[['s','q','E','current_stress','Q']].describe(percentiles=[.001,.01,.5,.99,.999]).to_csv(O/'SCALE_DISTRIBUTION.csv')
known.nsmallest(20,'q').to_csv(O/'MOST_NEGATIVE_Q_STANDARDIZED.csv',index=False);known.nsmallest(20,'s').to_csv(O/'SMALLEST_S.csv',index=False)
assert all(sha(p)==h for p,h in hashes.items());save('SOURCE_HASHES.json',hashes)
files=['PROTOCOL.json','freeze.py','FEATURES_AND_SELECTIONS.csv','SEALED_PAIRS.csv','SOURCE_QA.csv','PREFIX_QA.csv','SCALE_DISTRIBUTION.csv','MOST_NEGATIVE_Q_STANDARDIZED.csv','SMALLEST_S.csv']
save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/f):sha(O/f) for f in files},candidates=len(c),source_files=len(hashes),no_new_forward_outcome_join=True,one_formula=True,w0=w0,baseline_reproduced=True,unknown_slot_and_K_unchanged=True))
print('SUMMARY',c.groupby(['window','event_type']).agg(N=('sid','size'),known=('feature_known','sum'),negative_current=('r',lambda s:(s<0).sum()),changed_out=('baseline_selected','sum')).to_string())
print('DISTRIBUTION\n',known[['s','q','E','current_stress','Q']].describe(percentiles=[.001,.01,.5,.99,.999]).to_string())
print('CHANGES\n',pd.DataFrame(pairs).groupby(['window','event_type']).size().to_string())
print('WORST_Q\n',known.nsmallest(12,'q')[['window','day','sid','name','s','r','q','PVR_score','new_score','current_stress','baseline_selected','new_selected']].to_string(index=False))
