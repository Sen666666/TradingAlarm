from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
from scipy.optimize import linear_sum_assignment
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1';D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'PAIR_SEAL.json').exists()
p=dict(question='Same-day same-industry equal current PVR: newly established M3 versus already established M3. Not a hard gate or ranking optimization.',history='Prior full outcomes and related studies have been seen. Diagnostic only, not OOS.',source='Exact22196 common-known close-feasible independent shadows; only M3 is analyzed; PVR3 identities retained separately and never mixed.',state='Canonical mu5 original right3 with known3, previous immediate common session using actual2021Dec29-31 prefix. FRESH:today known true and prev known false; CONTINUING:today and prev known true; PREV_UNKNOWN separately. Any today not known true is an error.',matching='Within exact event_id (same arm/date/industry/event_type), I_valid=True, exact I_buy_today and CP1_today. Original contract is same initial probe role for everyone; these extra two flags conservatively stratify native I/CP status. Not same I_start across different stocks. Both pass identical t-close original nominal/risk/lot/capacity feasibility. No next-open or future outcome filtering. Maximum-cardinality one-to-one without-replacement fresh/continuing matching with abs current PVR difference<=5; then minimize total PVR distance. Sort stock codes first for deterministic ties.',budget='Same2pct reference initial nominal,.25pct plan risk,2pct one profitable freshCP add,4pct slot. Actual cash/quantity can differ due to risk/lot; report balance. No original shared-capital admission added.',labels='Reuse final same-contract full0to0 net W/L; OPEN=U; missing/source/factor UNKNOWN separate; explicit no-entry separate. Future labels only after pair seal. Pairwise differences only among pairs where both complete; also each side all matched counts and missingness reported.',windows='2022 full calendar year;2024Sep-Dec entire existing window, NOT all2024;2026H1 semiconductor. FALSE_TO_TRUE main, other industry event types separate.',stop='No scan, no account, no formulas fitted. Stop if low support, unstable direction or material tail opportunity cost. No promotion on these consumed histories.')
dump('PROTOCOL.json',p)
src=[B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',B/'SEALED_CLOSE_SELECTED.csv']+[D/(x+'.parquet') for x in ['RIGHT3','KNOWN3','WARM_PREFIX_M_R','WARM_PREFIX_M_K']]
hashes={str(x):sha(x) for x in src}
a=pd.read_csv(B/'ALL_CANDIDATES_COMMON_DOMAIN.csv',parse_dates=['day'],low_memory=False);c=a[a.ranking_common_known&a.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].copy();assert len(c)==22196
c=c[c.arm.eq('M3')].copy().reset_index(drop=True);assert c.I_valid.eq(True).all()
r=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(D/'RIGHT3.parquet')]).sort_index()
k=pd.concat([pd.read_parquet(D/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(D/'KNOWN3.parquet')]).sort_index()
assert r.index.equals(k.index) and r.columns.equals(k.columns) and not r.index.duplicated().any()
di=r.index.get_indexer(c.day);si=r.columns.get_indexer(c.sid);assert min(di)>0 and min(si)>=0
rr=r.to_numpy(dtype=bool);kk=k.to_numpy(dtype=bool);assert (rr[di,si]&kk[di,si]).all()
c['previous_common_day']=r.index[di-1];c['prev_M3_known']=kk[di-1,si];c['prev_M3_true']=rr[di-1,si]&kk[di-1,si]
c['member_state']=np.where(~c.prev_M3_known,'PREV_UNKNOWN',np.where(c.prev_M3_true,'CONTINUING','FRESH'))
c['I_age_common']=di-r.index.get_indexer(pd.to_datetime(c.I_start));c.loc[r.index.get_indexer(pd.to_datetime(c.I_start))<0,'I_age_common']=np.nan
sel=pd.read_csv(B/'SEALED_CLOSE_SELECTED.csv',usecols=['event_id','sid','ranking_strategy'])
base=set(map(tuple,sel[sel.ranking_strategy.eq('PVR_DESC')][['event_id','sid']].to_numpy()))
c['baseline_selected']=[(e,s) in base for e,s in zip(c.event_id,c.sid)]
c['match_reason']='PREV_UNKNOWN';c.loc[c.member_state.ne('PREV_UNKNOWN'),'match_reason']='NO_OPPOSITE_SAME_ROLE'
pairs=[];groups=[]
for key,g in c.groupby(['event_id','I_buy_today','CP1_today'],sort=True):
 f=g[g.member_state.eq('FRESH')].sort_values('sid');s=g[g.member_state.eq('CONTINUING')].sort_values('sid')
 n,m=len(f),len(s);npair=0
 if n and m:
  gap=abs(f.PVR_score.to_numpy()[:,None]-s.PVR_score.to_numpy()[None,:]);valid=gap<=5
  c.loc[f.index,'match_reason']=np.where(valid.any(axis=1),'CAPACITY_COMPETITION','NO_OPPOSITE_WITHIN_5')
  c.loc[s.index,'match_reason']=np.where(valid.any(axis=0),'CAPACITY_COMPETITION','NO_OPPOSITE_WITHIN_5')
  # A dummy for every fresh row avoids forcing invalid matches. 10000 exceeds all possible sum of valid distances in any group.
  cost=np.concatenate([np.where(valid,gap,1e9),np.full((n,n),10000.)],axis=1)
  ii,jj=linear_sum_assignment(cost)
  for i,j in zip(ii,jj):
   if j>=m or not valid[i,j]:continue
   fi,ci=int(f.index[i]),int(s.index[j]);c.loc[[fi,ci],'match_reason']='MATCHED';npair+=1
   pairs.append(dict(pair_id=len(pairs),event_id=key[0],window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],sector=g.sector.iloc[0],industry=g.industry.iloc[0],I_buy_today=key[1],CP1_today=key[2],fresh_index=fi,continuing_index=ci,fresh_sid=f.sid.iloc[i],continuing_sid=s.sid.iloc[j],fresh_PVR=f.PVR_score.iloc[i],continuing_PVR=s.PVR_score.iloc[j],PVR_gap=gap[i,j]))
 groups.append(dict(event_id=key[0],window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],I_buy_today=key[1],CP1_today=key[2],fresh=n,continuing=m,unknown=int(g.member_state.eq('PREV_UNKNOWN').sum()),matched_pairs=npair))
pairs=pd.DataFrame(pairs);groups=pd.DataFrame(groups)
c.to_csv(O/'FEATURES_AND_COVERAGE.csv',index=False);pairs.to_csv(O/'SEALED_PAIRS.csv',index=False);groups.to_csv(O/'GROUP_COVERAGE.csv',index=False)
cover=c.groupby(['window','event_type','member_state','match_reason']).agg(rows=('sid','size'),stocks=('sid','nunique'),dates=('day','nunique'),selected=('baseline_selected','sum')).reset_index();cover.to_csv(O/'COVERAGE.csv',index=False)
dump('PAIR_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),candidate_M3=len(c),pairs=len(pairs),future_labels_used_for_matching=False,source_hashes=hashes,output_hashes={str(O/n):sha(O/n) for n in ['PROTOCOL.json','FEATURES_AND_COVERAGE.csv','SEALED_PAIRS.csv','GROUP_COVERAGE.csv']},no_original_files_changed=True))
print('STATE COUNTS\n',c.groupby(['window','event_type','member_state']).size().to_string())
print('PAIRS\n',pairs.groupby(['window','event_type']).agg(pairs=('pair_id','size'),dates=('day','nunique'),events=('event_id','nunique'),mean_PVR_gap=('PVR_gap','mean')).to_string())
print('COVERAGE\n',cover.to_string(index=False))
