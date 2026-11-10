from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;B=O.parent;A=B.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n')
feature=B/'CAUSAL_FEATURE_COVERAGE.csv';pairfile=A/'SAME_DAY_INDUSTRY_SMALL_POS_PAIRS.csv';roundfile=A/'ALL_CORE_PATH_DIAGNOSTICS.csv'
f=pd.read_csv(feature,parse_dates=['day']);pairs=pd.read_csv(pairfile,parse_dates=['day']);r=pd.read_csv(roundfile,parse_dates=['signal_day'])
assert not f.event_id.duplicated().any();assert not r.round_id.duplicated().any()
r=r.merge(f[['event_id','beta','Q','status','stock_recent','sector_recent']],on='event_id',how='left',suffixes=('','_feature'),validate='one_to_one')
byround=r.set_index('round_id');rows=[]
for z in pairs.itertuples(index=False):
 a=byround.loc[z.winner_round];b=byround.loc[z.loser_round]
 rows.append(dict(window=z.window,day=z.day,sector=z.sector,winner=z.winner,loser=z.loser,winner_round=z.winner_round,loser_round=z.loser_round,winner_event=a.event_id,loser_event=b.event_id,winner_beta=a.beta,loser_beta=b.beta,winner_Q=a.Q,loser_Q=b.Q,Q_diff=a.Q-b.Q,winner_recent=a.stock_recent,loser_recent=b.stock_recent,recent_diff=a.stock_recent-b.stock_recent,beta_diff=a.beta-b.beta,industry_recent=a.sector_recent,pvr_diff=a.PVR_score-b.PVR_score,known=pd.notna(a.Q) and pd.notna(b.Q)))
p=pd.DataFrame(rows)
p['Q_winner_higher']=p.Q_diff>0;p['recent_winner_higher']=p.recent_diff>0;p['PVR_winner_higher']=p.pvr_diff>0
out=[];maxrankdiff=0;mindiff=np.inf
for key,g in f.groupby(['window','day','sector'],sort=True):
 g=g.sort_values(['original_PVR','sid'],ascending=[False,True],kind='stable').copy().reset_index(drop=True)
 g['original_feasible_rank']=np.arange(1,len(g)+1)
 K=int(g.original_selected.sum());assert K==min(2,len(g));assert g.original_selected.tolist()==([True]*K+[False]*(len(g)-K))
 known=g.status.eq('KNOWN');slots=np.flatnonzero(known)
 ordering=g.loc[known].sort_values(['Q','original_PVR','sid'],ascending=[False,False,True],kind='stable').index.to_numpy()
 roundorder=g.loc[known].assign(Q12=lambda q:q.Q.round(12)).sort_values(['Q12','original_PVR','sid'],ascending=[False,False,True],kind='stable').index.to_numpy()
 assert np.array_equal(ordering,roundorder),'Real ranking not robust to12-decimal numerical representation; stop'
 if len(ordering)>1:mindiff=min(mindiff,float(np.diff(np.sort(g.loc[known,'Q'].to_numpy())).min()))
 newrank=np.arange(1,len(g)+1)
 for slot,idx in zip(slots,ordering):newrank[idx]=slot+1
 g['diagnostic_Q_rank']=newrank;g['diagnostic_Q_selected']=g.diagnostic_Q_rank<=K;g['K']=K
 assert (g.loc[~known,'diagnostic_Q_rank']==g.loc[~known,'original_feasible_rank']).all()
 assert g.diagnostic_Q_selected.sum()==K
 out.append(g)
ranking=pd.concat(out,ignore_index=True);ranking.to_csv(O/'STATIC_QUEUE_RANKS.csv',index=False)
sel=ranking.set_index('event_id').diagnostic_Q_selected
p['winner_retained']=p.winner_event.map(sel);p['loser_retained']=p.loser_event.map(sel)
p.to_csv(O/'PAIRED_MECHANISM.csv',index=False)
summ=[];dates=[]
for w,g in p.groupby('window'):
 k=g[g.known]
 daily=k.groupby('day').agg(n=('Q_diff','size'),Q_diff=('Q_diff','mean'),recent_diff=('recent_diff','mean'),positive_pairs=('Q_winner_higher','sum'))
 daily['window']=w;dates.append(daily.reset_index())
 d=daily.Q_diff
 summ.append(dict(window=w,all_pairs=len(g),known_pairs=len(k),dates=len(daily),Q_winner_higher=int((k.Q_diff>0).sum()),Q_loser_higher=int((k.Q_diff<0).sum()),Q_equal=int((k.Q_diff==0).sum()),Q_diff_median=k.Q_diff.median(),Q_diff_pair_mean=k.Q_diff.mean(),Q_diff_date_equal_mean=d.mean(),date_mean_positive=int((d>0).sum()),date_mean_negative=int((d<0).sum()),date_mean_zero=int((d==0).sum()),recent_winner_higher=int((k.recent_diff>0).sum()),PVR_winner_higher=int((k.pvr_diff>0).sum()),Q_flips_raw_loser_to_winner=int(((k.recent_diff<=0)&(k.Q_diff>0)).sum()),Q_flips_raw_winner_to_loser=int(((k.recent_diff>0)&(k.Q_diff<=0)).sum()),Q_pair_winner_retained=int(k.winner_retained.sum()),Q_pair_loser_retained=int(k.loser_retained.sum()),leave_one_date_mean_min=float((d.sum()-d).min()/(len(d)-1)),leave_one_date_mean_max=float((d.sum()-d).max()/(len(d)-1)),largest_date_pairs=int(daily.n.max())))
summary=pd.DataFrame(summ);summary.to_csv(O/'PAIR_SUMMARY.csv',index=False);pd.concat(dates).to_csv(O/'DATE_CLUSTER_SUMMARY.csv',index=False)
# Matched feature-signal descriptions are conditioned on future labels and do not estimate strategy win probability.
old=r.merge(ranking[['event_id','diagnostic_Q_selected','original_feasible_rank','diagnostic_Q_rank']],on='event_id',validate='one_to_one')
old.to_csv(O/'ORIGINAL_SELECTED_RETENTION_DIAGNOSTIC.csv',index=False)
old.groupby(['window','diagnostic_group','diagnostic_Q_selected']).agg(n=('round_id','size'),old_core_net=('core_net',lambda a:a.sum(min_count=1))).to_csv(O/'OLD_LABEL_RETENTION_COUNTS.csv')
tails=old[old.tail30];tails.to_csv(O/'ORIGINAL_TAIL_RETENTION_DIAGNOSTIC.csv',index=False)
cs=[]
for w,g in ranking.groupby('window'):
 cs.append(dict(window=w,candidates=len(g),K_selected=int(g.original_selected.sum()),membership_in=int((~g.original_selected & g.diagnostic_Q_selected).sum()),membership_out=int((g.original_selected & ~g.diagnostic_Q_selected).sum()),changed_positions=int((g.original_feasible_rank!=g.diagnostic_Q_rank).sum()),unknown_positions_unchanged=bool((g.loc[g.status.ne('KNOWN'),'original_feasible_rank']==g.loc[g.status.ne('KNOWN'),'diagnostic_Q_rank']).all())))
pd.DataFrame(cs).to_csv(O/'QUEUE_CHANGE_COUNTS.csv',index=False)
hashes={str(v):sha(v) for v in [Path(__file__),O/'FREEZE.json',feature,pairfile,roundfile]}
save('SOURCE_HASHES.json',hashes);save('QA.json',dict(original_candidates=len(f),original_selected=len(r),static_only=True,new_economics=0,unknown_slots_preserved=True,real_rank_equivalent_at_12_decimals=True,min_adjacent_known_Q_difference=float(mindiff),candidate_formula_unchanged=True))
print(summary.to_string(index=False));print(pd.DataFrame(cs).to_string(index=False));print('OLD_LABEL_RETENTION');print(old.groupby(['window','diagnostic_group','diagnostic_Q_selected']).agg(n=('round_id','size'),old_core_net=('core_net',lambda a:a.sum(min_count=1))).to_string());print('TAIL_RETAINED');print(tails.groupby('window').diagnostic_Q_selected.agg(['count','sum']).to_string());print('TOP_DATE_CLUSTERS');print(pd.concat(dates).sort_values('n',ascending=False).head(12).to_string(index=False))
