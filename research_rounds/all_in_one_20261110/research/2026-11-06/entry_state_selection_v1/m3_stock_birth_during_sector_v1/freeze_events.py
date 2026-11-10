from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'EVENT_SEAL.json').exists()
src=[O/'PROTOCOL.json',Path(__file__),D/'COMMON_K_COMPARISON.parquet',D/'RIGHT3.parquet',D/'KNOWN3.parquet',D/'WARM_PREFIX_M_R.parquet',D/'WARM_PREFIX_M_K.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv',U/'STOCK_MANIFEST.json',R/'breadth_trade_contract_v1/ALL_CANDIDATES.csv']
hashes={str(p):sha(p) for p in src}
panel=pd.read_parquet(D/'COMMON_K_COMPARISON.parquet').sort_values(['sector','day'])
rr=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(D/'RIGHT3.parquet')]).sort_index().astype(bool)
kk=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(D/'KNOWN3.parquet')]).sort_index().astype(bool)
assert rr.index.equals(kk.index) and not rr.index.duplicated().any()
M=rr.astype('int8').where(kk,-1);prevM=M.shift()
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')
pv=pv.set_index(['day','sid'])
roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv');members=roster.groupby('sector_id').sid.apply(list).to_dict();names=roster.set_index('sid').name.to_dict()
sm={m['symbol']:m for m in json.load(open(U/'STOCK_MANIFEST.json'))}
windows=[('2022','2022-01-01','2022-12-31',None),('2024_924','2024-09-01','2024-12-31',None),('2026H1_SEMI','2026-01-01','2026-06-30','URFI881121')]
rows=[]
for sec,g in panel.groupby('sector'):
 g=g.copy();g['prevS']=g.M3_candidate.shift();start=g.M3_candidate.eq(1)&~g.prevS.eq(1);g['sector_run_start']=g.day.where(start).ffill();g['sector_run_age']=g.groupby(start.cumsum()).cumcount()
 for wn,lo,hi,specific in windows:
  if specific and specific!=sec:continue
  gg=g[g.day.between(lo,hi)&g.M3_candidate.eq(1)]
  for z in gg.itertuples():
   ids=members[sec];mt=M.loc[z.day,ids];pm=prevM.loc[z.day,ids]
   for sid in mt.index[mt.eq(1)]:
    pstock=pm.at[sid]
    if z.prevS==0:typ='A_SECTOR_BIRTH'
    elif z.prevS==1 and pstock==0:typ='B_STOCK_BIRTH_DURING_SECTOR'
    elif z.prevS==1 and pstock==1:continue
    else:typ='OTHER_UNKNOWN_OR_LEFT'
    q=pv.loc[(z.day,sid)]
    rows.append(dict(window=wn,day=z.day,sid=sid,name=names.get(sid,''),sector=sec,industry=z.sector_name,event_type=typ,previous_common_day=rr.index[rr.index.get_loc(z.day)-1],previous_sector_state=z.prevS,previous_stock_state=pstock,sector_run_start=z.sector_run_start,sector_run_age=z.sector_run_age,PVR_score=q.score,PVR_state=q.state,PVR_known=bool(np.isfinite(q.score) and q.state>=0 and q.valid_observation),sector_M3_n=z.M3_n,sector_N=z.N,sector_K=z.K,sector_delta3=z.M3_delta3,original_sector_authorization=z.sector_authorization_usable))
e=pd.DataFrame(rows);e['event_id']=[f'{w}|{t}|{pd.Timestamp(d).date()}|{s}|{i}' for w,t,d,s,i in zip(e.window,e.event_type,e.day,e.sector,e.sid)]
assert not e.duplicated(['window','day','sid']).any()
for sid,g in e.groupby('sid'):
 fp=Path(sm[sid]['refs']['facts']);hashes[str(fp)]=sha(fp);f=pd.read_parquet(fp).reindex(pd.DatetimeIndex(g.day))
 for c in ['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','close','raw_close','factor','segment_id']:
  e.loc[g.index,c]=f[c].to_numpy()
e['I_qualified']=e.e0_ready.eq(1)&e.g_ready.eq(True)&e.i_target.eq(1)&np.isfinite(e.i_floor)&e.i_floor.gt(0)
e['I_and_PVR_known']=e.I_qualified&e.PVR_known
# Original A membership reconstructed before any path or outcome read.
old=pd.read_csv(R/'breadth_trade_contract_v1/ALL_CANDIDATES.csv',parse_dates=['day'],dtype={'window':str})
old=old[old.arm.eq('M3')&old.event_type.eq('FALSE_TO_TRUE')]
oldset=set(map(tuple,old[['window','day','sid']].to_numpy()))
newset=set(map(tuple,e[e.event_type.eq('A_SECTOR_BIRTH')&e.PVR_state.ge(0)][['window','day','sid']].to_numpy()))
assert oldset==newset,dict(old_only=len(oldset-newset),new_only=len(newset-oldset))
j=old[['window','day','sid','I_valid']].merge(e[e.event_type.eq('A_SECTOR_BIRTH')][['window','day','sid','I_qualified']],on=['window','day','sid'],validate='one_to_one')
assert j.I_valid.eq(j.I_qualified).all()
e.to_csv(O/'SEALED_ALL_BIRTH_EVENTS.csv',index=False)
summ=e.groupby(['window','event_type']).agg(events=('sid','size'),stocks=('sid','nunique'),dates=('day','nunique'),sector_days=('sector_run_start',lambda x:np.nan),I_qualified=('I_qualified','sum'),PVR_known=('PVR_known','sum'),I_and_PVR_known=('I_and_PVR_known','sum')).reset_index()
summ['sector_days']=[len(g[['day','sector']].drop_duplicates()) for _,g in e.groupby(['window','event_type'])]
summ.to_csv(O/'EVENT_COUNTS.csv',index=False)
b=e[e.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR')];by=b.groupby(['window','sector','industry']).agg(events=('sid','size'),stocks=('sid','nunique'),dates=('day','nunique'),I_qualified=('I_qualified','sum'),I_and_PVR_known=('I_and_PVR_known','sum')).reset_index();by.to_csv(O/'NEW_BIRTHS_BY_INDUSTRY.csv',index=False)
# Per B receipt, describe whether the same sid was already invited at the A birth of this same sector run.
a=e[e.event_type.eq('A_SECTOR_BIRTH')];ak=set(map(tuple,a[['window','sector_run_start','sid']].to_numpy()))
e['already_invited_at_sector_birth']=[(w,st,sid) in ak if typ=='B_STOCK_BIRTH_DURING_SECTOR' else False for w,st,sid,typ in zip(e.window,e.sector_run_start,e.sid,e.event_type)]
# This is an invitation, never actual stock position.
e.to_csv(O/'SEALED_ALL_BIRTH_EVENTS.csv',index=False)
bb=e[e.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR')]
rrr=bb.groupby(['window','already_invited_at_sector_birth']).agg(events=('sid','size'),I_and_PVR_known=('I_and_PVR_known','sum')).reset_index();rrr.to_csv(O/'REPEATED_INVITATION_COUNTS.csv',index=False)
# Check causal edge reconstruction using physically truncated state arrays, fixed endpoint samples.
checks=[]
for wn,gg in e.groupby('window'):
 for day in sorted(gg.day.unique())[::max(1,gg.day.nunique()//5)]:
  tt=pd.Timestamp(day);prefix=M.loc[:tt];previous=prefix.shift();g0=gg[gg.day.eq(tt)]
  for z in g0.itertuples():
   assert int(prefix.at[tt,z.sid])==1
   assert (pd.isna(previous.at[tt,z.sid]) and pd.isna(z.previous_stock_state)) or previous.at[tt,z.sid]==z.previous_stock_state
  checks.append(dict(window=wn,day=tt,event_rows=len(g0),exact=True))
save('QA.json',dict(original_A_identity_exact=True,original_A_rows=len(oldset),original_A_I_qualification_exact=True,duplicate_stock_date=0,checks=checks,full_panel_shifts_before_windows=True,no_forward_labels_loaded=True,known_false_not_unknown=True,no_accounts=True))
save('SOURCE_HASHES.json',hashes)
save('EVENT_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC'),source_hashes=hashes,outputs={n:sha(O/n) for n in ['PROTOCOL.json','SEALED_ALL_BIRTH_EVENTS.csv','EVENT_COUNTS.csv','NEW_BIRTHS_BY_INDUSTRY.csv','REPEATED_INVITATION_COUNTS.csv','QA.json']},history_seen=True,no_new_forward_labels_before_seal=True))
print(summ.to_string(index=False));print('REPEATED\n',rrr.to_string(index=False));print('ORIGINAL EXACT',len(oldset))
