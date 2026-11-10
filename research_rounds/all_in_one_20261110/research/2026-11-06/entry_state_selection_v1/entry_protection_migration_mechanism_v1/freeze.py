from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SELECTION_SEAL.json').exists()
c=pd.read_csv(B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',parse_dates=['day'],low_memory=False)
c=c[c.arm.eq('M3')&c.ranking_common_known&c.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].copy().reset_index(drop=True)
old=pd.read_csv(B/'SEALED_CLOSE_SELECTED.csv');old=old[old.ranking_strategy.eq('PVR_DESC')&old.arm.eq('M3')]
ids=set(map(tuple,old[['event_id','sid']].to_numpy()));c['baseline_selected']=[(e,s) in ids for e,s in zip(c.event_id,c.sid)]
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index) for x in im])));cal=cal[cal<=pd.Timestamp('2026-06-30')]
src=[U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',B/'SEALED_CLOSE_SELECTED.csv',O/'PROTOCOL.json',Path(__file__)]+[Path(x['refs']['CP1_input']) for x in im]
hashes={str(p):sha(p) for p in src};qa=[];pre=[]
for col in ['C','F','F_lag3','D','floor_progress','Q','G_grade','amount_relative21','ret3','ret20','I_age']:c[col]=np.nan
c['feature_known']=False;c['feature_reason']='UNKNOWN';start=time.monotonic()
for j,(sid,g) in enumerate(c.groupby('sid',sort=True)):
 m=sm[sid];fp=Path(m['refs']['facts']);sp=Path(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')))
 f=pd.read_parquet(fp).loc[:g.day.max()].reindex(cal[cal<=g.day.max()]);p=pd.read_parquet(sp).loc[:g.day.max()].reindex(f.index)
 hashes[str(fp)]=sha(fp);hashes[str(sp)]=sha(sp)
 ident=p[['source_kind','source_path','segment_id']];valid=p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&~p.source_invalid.eq(True)&~p.synthetic_event_bar.eq(True)&p.raw_close.gt(0)&p.raw_volume.gt(0)&p.amount.gt(0)&ident.notna().all(axis=1)
 same=ident.eq(ident.shift()).all(axis=1)&p.adjustment_factor.eq(p.adjustment_factor.shift())
 same4=same.rolling(3,min_periods=3).sum().eq(3)
 active=f.i_target.eq(1); pos=f.i_floor.gt(0)&f.close.gt(f.i_floor)&np.isfinite(f.i_floor)&np.isfinite(f.close)
 known=valid.rolling(4,min_periods=4).sum().eq(4)&same4&active.rolling(4,min_periods=4).sum().eq(4)&f.i_floor.gt(0).rolling(4,min_periods=4).sum().eq(4)&pos
 D=np.log(f.close/f.i_floor);progress=np.log(f.i_floor/f.i_floor.shift(3));Q=progress/D
 # Native floor/close mapping checked at every candidate. No source gap skipping.
 target=f.reindex(g.day);raw=p.reindex(g.day)
 err=float(np.nanmax(abs(target.close.to_numpy()-g.known_close_raw.to_numpy()*raw.adjustment_factor.to_numpy())))
 ferr=float(np.nanmax(abs(target.i_floor.to_numpy()-g.close_floor_raw.to_numpy()*raw.adjustment_factor.to_numpy())))
 assert err<1e-6 and ferr<1e-6,(sid,err,ferr)
 Arel=p.amount/p.amount.shift().rolling(21,min_periods=21).median()
 ages=pd.Series(np.arange(len(f)),index=f.index);starti=ages.where(~active.shift(fill_value=False)&active).ffill();iage=ages-starti
 for ii,r in g.iterrows():
  t=r.day;k=bool(known.at[t]) and np.isfinite(Q.at[t]);reason='KNOWN' if k else ('C_NOT_ABOVE_F' if not bool(pos.at[t]) else 'SOURCE_VALIDITY_OR_I_ROOT')
  c.at[ii,'feature_known']=k;c.at[ii,'feature_reason']=reason
  vals=[f.at[t,'close'],f.at[t,'i_floor'],f.i_floor.shift(3).at[t],D.at[t],progress.at[t],Q.at[t] if k else np.nan,f.at[t,'g_grade'],Arel.at[t],f.close.pct_change(3,fill_method=None).at[t],f.close.pct_change(20,fill_method=None).at[t],iage.at[t]]
  c.loc[ii,['C','F','F_lag3','D','floor_progress','Q','G_grade','amount_relative21','ret3','ret20','I_age']]=vals
 for _,gg in g.groupby('window'):
  for t in sorted(set([gg.day.min(),gg.day.max()])):
   k=f.index.get_loc(t);q=np.log(f.iloc[k].i_floor/f.iloc[k-3].i_floor)/np.log(f.iloc[k].close/f.iloc[k].i_floor) if k>=3 else np.nan
   if known.at[t]:assert abs(q-Q.at[t])<1e-12
   pre.append(dict(sid=sid,day=t,check='four-date scalar prefix vs vector',known=bool(known.at[t])))
 qa.append(dict(sid=sid,n=len(g),known=int(c.loc[g.index,'feature_known'].sum()),close_error=err,floor_error=ferr))
 if (j+1)%300==0:print('FEATURES',j+1,round(time.monotonic()-start,1),flush=True)
c['new_selected']=False;c['baseline_rank']=0;c['new_rank']=0;pairs=[]
for ev,g in c.groupby('event_id',sort=True):
 base=g.sort_values(['PVR_score','sid'],ascending=[False,True]);order=list(base.index);slots=np.flatnonzero(base.feature_known.to_numpy());kn=base[base.feature_known].sort_values(['Q','PVR_score','sid'],ascending=[False,False,True])
 for pos,ii in zip(slots,kn.index):order[pos]=ii
 K=int(g.baseline_selected.sum());assert K==min(2,len(g));assert set(base.head(K).index)==set(g[g.baseline_selected].index)
 c.loc[base.index,'baseline_rank']=np.arange(1,len(g)+1);c.loc[order,'new_rank']=np.arange(1,len(g)+1);c.loc[order[:K],'new_selected']=True
 rem=[i for i in base.head(K).index if i not in order[:K]];add=[i for i in order[:K] if i not in base.head(K).index]
 for a,b in zip(rem,add):pairs.append(dict(pair_id=len(pairs),event_id=ev,window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],sector=g.sector.iloc[0],removed_sid=c.at[a,'sid'],added_sid=c.at[b,'sid']))
assert c.groupby('event_id').baseline_selected.sum().equals(c.groupby('event_id').new_selected.sum())
assert (c.loc[~c.feature_known,'baseline_rank']==c.loc[~c.feature_known,'new_rank']).all()
c.to_csv(O/'FEATURES_AND_SELECTIONS.csv',index=False);pd.DataFrame(pairs).to_csv(O/'SEALED_PAIRS.csv',index=False);pd.DataFrame(qa).to_csv(O/'SOURCE_QA.csv',index=False);pd.DataFrame(pre).to_csv(O/'PREFIX_ALGEBRA_QA.csv',index=False)
assert all(sha(p)==h for p,h in hashes.items());save('SOURCE_HASHES.json',hashes)
files=['PROTOCOL.json','FEATURES_AND_SELECTIONS.csv','SEALED_PAIRS.csv','SOURCE_QA.csv','PREFIX_ALGEBRA_QA.csv','freeze.py']
save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/f):sha(O/f) for f in files},formula_scans=1,forward_outcome_joined=False,raw_files_contain_future_but_features_truncated=True,source_files=len(hashes),candidates=len(c),changed_pairs=len(pairs)))
print(c.groupby(['window','event_type']).agg(N=('sid','size'),known=('feature_known','sum'),old=('baseline_selected','sum'),new=('new_selected','sum')).to_string())
print('D/Q distribution',c.loc[c.feature_known,['D','floor_progress','Q']].describe(percentiles=[.001,.01,.5,.99,.999]).to_string());print('SEALED',len(c),len(pairs))
