"""Single frozen E3.1 state-layer ranking trial. No original signal/account run."""
from pathlib import Path
import ast,json,hashlib,time
import numpy as np,pandas as pd,pyarrow.parquet as pq
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'equal_entry_validation_v1'
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
STATE=R/'epoch_v3/rolling_prebreak_v31/check_epoch_semantics.py'
source=STATE.read_text();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='run')
env=dict(np=np,pd=pd,D=D);exec(compile(ast.Module(body=[node],type_ignores=[]),str(STATE),'exec'),env);state_run=env['run']
manifest=json.loads((D.parent/'CACHE_DATASET.json').read_text());files=sorted(D.parent/p for p in manifest['files'])
K=20;fee=.005;tick=time.time();parts=[];audit=[]
# PHASE A: original candidate domain and E3.1 states; no forward label calculation.
for no,path in enumerate(files):
 sid=path.stem
 f=pq.read_table(path,columns=['day','source_row_present','native__e0_ready','native__g_ready','native__i_target','native__i_buy','native__i_entered','pvr__score']).to_pandas()
 states=pd.DataFrame(state_run(sid))
 assert len(states)==len(f) and np.array_equal(states.day.to_numpy(),f.day.dt.strftime('%Y-%m-%d').to_numpy())
 present=f.source_row_present.eq(True).to_numpy()
 domain=(f.source_row_present.eq(True)&f.native__e0_ready.eq(1)&f.native__g_ready.eq(True)&f.native__i_target.eq(1)&f.native__i_buy.eq(True)).to_numpy()
 raw=f.pvr__score.to_numpy(dtype=float,na_value=np.nan)
 starts=f.native__i_entered.eq(1).to_numpy()
 obs=np.cumsum(present);at=np.where(starts,np.arange(len(f)),-1);roots=np.maximum.accumulate(at)
 idx=np.flatnonzero(domain)
 q=states.iloc[idx][['sid','day','root_day','state','kind','local_tau','first_break_day','B','S','atr','research_candidate']].copy()
 q['t']=idx;q['pvr']=raw[idx];q['pvr_known']=np.isfinite(raw[idx]);q['original_root_index']=roots[idx]
 days=f.day.dt.strftime('%Y-%m-%d').to_numpy()
 q['original_root_day']=[days[r]if r>=0 else None for r in roots[idx]]
 q['original_epoch']=[sid+':'+days[r]if r>=0 else None for r in roots[idx]]
 q['original_age_common']=[i-r if r>=0 else np.nan for i,r in zip(idx,roots[idx])]
 q['original_age_obs']=[obs[i]-obs[r]if r>=0 else np.nan for i,r in zip(idx,roots[idx])]
 q['original_I_entered']=starts[idx]
 q['stratum']=np.where(q.state.eq('FIRST_BREAK')&q.first_break_day.eq(q.day),'FRESH_DAY0',np.where(q.state.eq('CONFIRMED'),'CONFIRMED',np.where(q.state.eq('PREBREAK'),'PREBREAK','OTHER_OR_UNKNOWN')))
 parts.append(q);audit.append(dict(sid=sid,original_i_buy=int(domain.sum()),pvr_known=int(np.isfinite(raw[idx]).sum()),left_root_unknown=int((roots[idx]<0).sum()),state_unknown=int(q.state.isin(['UNKNOWN','I_INACTIVE']).sum())))
 if(no+1)%500==0:print('states',no+1,'seconds',round(time.time()-tick,1),flush=True)
cand=pd.concat(parts,ignore_index=True);cand['year']=cand.day.str[:4].astype(int)
cand.to_parquet(O/'ALL_ORIGINAL_I_BUY_WITH_STATES.parquet',index=False)
pd.DataFrame(audit).to_csv(O/'DOMAIN_AUDIT.csv',index=False)
select=[];queue=[]
for day,g in cand[cand.pvr_known].groupby('day',sort=True):
 g=g.sort_values(['pvr','sid'],ascending=[False,True])
 base=g.head(K).copy();base['strategy']='BASE_PVR';base['selection_role']='BASE';base['rank']=np.arange(1,len(base)+1)
 first=g[g.stratum.eq('FRESH_DAY0')].head(5);verified=g[g.stratum.eq('CONFIRMED')].head(15)
 # Explicit proposal order: 1 fresh then3 verified, repeated, then fixed-order fallback.
 ix=[];roles=[];ii=jj=0
 for cycle in range(5):
  if ii<len(first):ix.append(first.index[ii]);roles.append('FRESH_RESERVED');ii+=1
  for _ in range(3):
   if jj<len(verified):ix.append(verified.index[jj]);roles.append('CONFIRMED_RESERVED');jj+=1
 remaining=g[~g.index.isin(ix)].head(K-len(ix))
 ix+=list(remaining.index);roles+=['BASE_FALLBACK']*len(remaining)
 alt=g.loc[ix].copy();alt['strategy']='STATE_5F_15V';alt['selection_role']=roles;alt['rank']=np.arange(1,len(alt)+1)
 assert len(base)==len(alt)==min(K,len(g)) and alt.sid.is_unique
 base['slot_weight']=1/K;alt['slot_weight']=1/K;select.extend([base,alt])
 A=set(base.sid);B=set(alt.sid);queue.append(dict(day=day,original_pvr_known=len(g),fresh_available=int(g.stratum.eq('FRESH_DAY0').sum()),confirmed_available=int(g.stratum.eq('CONFIRMED').sum()),selected=len(base),intersection=len(A&B),added=len(B-A),removed=len(A-B),reserved_fresh=len(first),reserved_confirmed=len(verified),fallback=len(remaining),state_unknown_candidates=int(g.state.eq('UNKNOWN').sum())))
sel=pd.concat(select,ignore_index=True)
sel.to_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',index=False)
pd.DataFrame(queue).to_csv(O/'QUEUE_OVERLAP_AND_BACKFILL.csv',index=False)
receipt=dict(status='SEALED_BEFORE_FORWARD_LABELS',time=time.time(),source_state_sha256=hashlib.sha256(STATE.read_bytes()).hexdigest(),code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((O/'ALL_ORIGINAL_I_BUY_WITH_STATES.parquet').read_bytes()).hexdigest(),selection_sha256=hashlib.sha256((O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet').read_bytes()).hexdigest(),candidate_rows=len(cand),pvr_known_rows=int(cand.pvr_known.sum()),selected_stockdays=len(sel),future_open_used_for_selection=False)
(O/'RANK_SEAL.json').write_text(json.dumps(receipt,indent=2))
print('RANKS_SEALED',json.dumps(receipt),flush=True)
# PHASE B: exactly the same label per stock/signal day for either strategy.
entry=cand[cand.original_I_entered&cand.pvr_known&cand.original_epoch.notna()].copy()
keys=pd.concat([sel[['sid','day','t']],entry[['sid','day','t']]]).drop_duplicates(['sid','day'])
labels=[]
for no,(sid,g) in enumerate(keys.groupby('sid')):
 f=pq.read_table(D/(sid+'.parquet'),columns=['day','source_row_present','price__open','price__high','price__low','price__close','native__e0_ready','native__i_target']).to_pandas()
 days=f.day.dt.strftime('%Y-%m-%d').to_numpy();n=len(f)
 C=f.price__close.to_numpy(dtype=float,na_value=np.nan);P=f.price__open.to_numpy(dtype=float,na_value=np.nan);H=f.price__high.to_numpy(dtype=float,na_value=np.nan);L=f.price__low.to_numpy(dtype=float,na_value=np.nan)
 present=f.source_row_present.eq(True).to_numpy();valid=present&np.isfinite(C)&(C>0);ogood=np.isfinite(P)&(P>0)
 ik=f.source_row_present.eq(True).to_numpy()&f.native__e0_ready.eq(1).to_numpy()&f.native__i_target.isin([0,1]).to_numpy()
 zero=np.flatnonzero(ik&f.native__i_target.eq(0).to_numpy())
 for _,r in g.iterrows():
  t=int(r.t);en=t+1;opok=en<n and ogood[en]
  z=dict(sid=sid,day=r.day,entry_index=en,entry_day=days[en]if en<n else None,entry_open=P[en]if opok else np.nan,open_known=bool(opok),entry_gap=P[en]/C[t]-1 if opok else np.nan,entry_flat_posthoc=bool(en<n and P[en]==H[en]==L[en]==C[en]),entry_flat_up_posthoc=bool(en<n and P[en]==H[en]==L[en]==C[en]and P[en]>C[t]),entry_flat_down_posthoc=bool(en<n and P[en]==H[en]==L[en]==C[en]and P[en]<C[t]))
  for h in [20,60]:
   end=en+h-1;ok=opok and end<n and np.all(valid[en:end+1]);arr=C[en:end+1]if ok else np.array([])
   z['complete'+str(h)]=bool(ok);z['end_day'+str(h)]=days[end]if end<n else None
   z['ret'+str(h)]=arr[-1]/P[en]-1 if ok else np.nan;z['net'+str(h)]=z['ret'+str(h)]-fee if ok else np.nan
   z['mae'+str(h)]=min(0,arr.min()/P[en]-1)if ok else np.nan;z['mfe'+str(h)]=max(0,arr.max()/P[en]-1)if ok else np.nan
  # Original I-state-only hold. Not position-specific CP/real account exit.
  zz=zero[zero>=en];exclose=int(zz[0])if len(zz)else None
  ex=exclose+1 if exclose is not None else None
  known=opok and ex is not None and ex<n and ogood[ex]and np.all(ik[en:exclose+1])and np.all(valid[en:exclose+1])
  z.update(I_exit_close_day=days[exclose]if exclose is not None else None,I_exit_open_day=days[ex]if ex is not None and ex<n else None,I_complete=bool(known),I_right_censored=exclose is None,I_exit_missing_open=bool(ex is not None and(ex>=n or not ogood[ex])),I_interrupted_knowledge=bool(exclose is not None and not np.all(ik[en:exclose+1])),I_hold_common_days=ex-en if known else np.nan,I_exit_open=P[ex]if ex is not None and ex<n and ogood[ex]else np.nan)
  z['I_ret']=P[ex]/P[en]-1 if known else np.nan;z['I_net']=z['I_ret']-fee if known else np.nan
  z['I_mae']=min(0,np.min(np.r_[C[en:exclose+1],P[ex]])/P[en]-1)if known else np.nan
  z['I_mfe']=max(0,np.max(np.r_[C[en:exclose+1],P[ex]])/P[en]-1)if known else np.nan
  z['I_exit_gap']=P[ex]/C[exclose]-1 if known else np.nan
  z['I_exit_flat_down_posthoc']=bool(known and P[ex]==H[ex]==L[ex]==C[ex]and P[ex]<C[exclose])
  labels.append(z)
 if(no+1)%1000==0:print('labels stocks',no+1,'rows',len(labels),flush=True)
lab=pd.DataFrame(labels);lab.to_parquet(O/'SHARED_STOCKDAY_LABELS.parquet',index=False)
joined=sel.merge(lab,on=['sid','day'],validate='many_to_one')
joined['support_risk']=(joined.entry_open-joined.S)/joined.entry_open
joined.loc[~np.isfinite(joined.support_risk)|(joined.support_risk<=0),'support_risk']=np.nan
joined['I_net_R']=joined.I_net/joined.support_risk
joined.to_parquet(O/'SELECTED_SAME_PATH_LABELS.parquet',index=False)
ent=entry.merge(lab,on=['sid','day'],validate='one_to_one');ent['big60']=ent.complete60&ent.mfe60.ge(.3)&ent.ret60.ge(.2)
ent.to_parquet(O/'FIXED_ORIGINAL_I_ENTRY_LABELS.parquet',index=False)
(O/'GENERATION_COMPLETION.json').write_text(json.dumps(dict(status='COMPLETE_PRICE_PATH_PAIRING_NOT_ACCOUNT',seconds=time.time()-tick,stocks=len(files),original_i_buy=len(cand),pvr_known=int(cand.pvr_known.sum()),selection_rows=len(sel),shared_labels=len(lab),fixed_original_entry_rows=len(ent),account_runs=0,original_signal_reruns=0,state_rule_changes=0,parameter_searches=0),indent=2))
print((O/'GENERATION_COMPLETION.json').read_text())
