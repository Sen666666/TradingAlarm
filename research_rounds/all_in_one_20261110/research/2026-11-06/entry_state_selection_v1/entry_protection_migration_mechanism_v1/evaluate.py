from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.load(open(O/'SELECTION_SEAL.json'));src=json.load(open(O/'SOURCE_HASHES.json'));assert all(sha(p)==h for p,h in seal['hashes'].items());assert all(sha(p)==h for p,h in src.items())
c=pd.read_csv(O/'FEATURES_AND_SELECTIONS.csv',parse_dates=['day'],dtype={'window':str});p=pd.read_csv(O/'SEALED_PAIRS.csv',parse_dates=['day'],dtype={'window':str})
z=pd.read_csv(R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',low_memory=False)
cols=['event_id','sid','status','entry_status','entry_day','exit_day','unknown_day','net_pnl','net_return_on_buy_cash','adds','entry_q','entry_price','entry_fee','total_buy_cash','label','tail30','core_net','add_net','member_state']
c=c.rename(columns={'status':'close_status'}).merge(z[cols],on=['event_id','sid'],validate='one_to_one',how='left');assert len(c)==14880 and c.status.notna().all()
def stats(g):
 d=g[g.label.isin(['W','L'])];w=d[d.net_pnl.gt(0)];l=d[d.net_pnl.le(0)]
 return dict(n=len(g),dates=g.day.nunique(),events=g.event_id.nunique(),W=len(w),L=len(l),U=int(g.label.eq('U').sum()),UNKNOWN=int(g.label.eq('UNKNOWN').sum()),NO_ENTRY=int(g.label.eq('NO_ENTRY').sum()),winrate=len(w)/len(d) if len(d) else np.nan,mean_win=w.net_pnl.mean(),mean_loss=-l.net_pnl.mean(),payoff=w.net_pnl.mean()/(-l.net_pnl.mean()),mean_net=d.net_pnl.mean(),tail30=int(d.tail30.sum()),core_wins=int(d.core_net.gt(0).sum()),mean_core=d.core_net.mean(),mean_add=d.add_net.mean(),core_positive_final_loss=int((d.core_net.gt(0)&d.net_pnl.le(0)).sum()),core_negative_final_win=int((d.core_net.le(0)&d.net_pnl.gt(0)).sum()),known=int(g.feature_known.sum()),mean_D=g.D.mean(),mean_Q=g.Q.mean())
out=[]
for scope,h in [('ALL',c),('PVR',c[c.baseline_selected]),('FLOOR_MIGRATION',c[c.new_selected]),('REMOVED',c[c.baseline_selected&~c.new_selected]),('ADDED',c[~c.baseline_selected&c.new_selected])]:
 for key,g in h.groupby(['window','event_type']):out.append(dict(scope=scope,window=key[0],event_type=key[1],**stats(g)))
summary=pd.DataFrame(out);summary.to_csv(O/'SUMMARY.csv',index=False);c.to_csv(O/'ALL_M3_RESULTS.csv',index=False)
pc=p.copy();fields=['name','label','net_pnl','net_return_on_buy_cash','tail30','core_net','add_net','PVR_score','Q','D','floor_progress','G_grade','amount_relative21','ret3','ret20','I_age','I_start','I_buy_today','CP1_today','member_state','entry_day','exit_day']
for side in ['removed','added']:
 v=c[['event_id','sid']+fields].rename(columns={'sid':side+'_sid',**{k:side+'_'+k for k in fields}})
 pc=pc.merge(v,on=['event_id',side+'_sid'],validate='one_to_one',how='left')
pc['both_closed']=pc.removed_label.isin(['W','L'])&pc.added_label.isin(['W','L']);pc['delta_net']=pc.added_net_pnl-pc.removed_net_pnl;pc['delta_win']=pc.added_label.eq('W').astype(int)-pc.removed_label.eq('W').astype(int);pc.to_csv(O/'PAIRED_RESULTS.csv',index=False)
psum=[];cl=[];cal=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet').index
for key,g in pc.groupby(['window','event_type']):
 q=g[g.both_closed];base=dict(window=key[0],event_type=key[1])
 psum.append(base|dict(all_pairs=len(g),both_closed=len(q),dates=q.day.nunique(),old_winrate=q.removed_label.eq('W').mean(),new_winrate=q.added_label.eq('W').mean(),old_mean_net=q.removed_net_pnl.mean(),new_mean_net=q.added_net_pnl.mean(),delta_net=q.delta_net.mean(),old_tails=int(q.removed_tail30.sum()),new_tails=int(q.added_tail30.sum())))
 if len(q)>1:
  for met in ['delta_net','delta_win']:
   vals=q[met].to_numpy();ids=cal.get_indexer(q.day)//20;us=pd.unique(ids);leave=np.array([vals[ids!=u].mean() for u in us if (ids!=u).any()])
   se=np.sqrt((len(leave)-1)/len(leave)*np.sum((leave-leave.mean())**2)) if len(leave)>1 else np.nan
   cl.append(base|dict(metric=met,clusters=len(us),estimate=vals.mean(),delete20daySE=se))
pd.DataFrame(psum).to_csv(O/'PAIRED_SUMMARY.csv',index=False);pd.DataFrame(cl).to_csv(O/'CLUSTER_DIAGNOSTIC.csv',index=False)
evrows=[]
for ev,g in c.groupby('event_id'):
 a=g[g.baseline_selected];b=g[g.new_selected];union=g[g.baseline_selected|g.new_selected];both=union.label.isin(['W','L']).all()
 evrows.append(dict(event_id=ev,window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],both_complete=both,K=len(a),delta_net=b.net_pnl.mean()-a.net_pnl.mean() if both else np.nan,delta_win=b.label.eq('W').mean()-a.label.eq('W').mean() if both else np.nan))
ev=pd.DataFrame(evrows);ev.to_csv(O/'EVENT_PAIRED_DIAGNOSTIC.csv',index=False)
dates=ev[ev.both_complete].groupby(['window','event_type','day']).agg(delta_net=('delta_net','mean'),delta_win=('delta_win','mean'),events=('event_id','size')).reset_index();dates.to_csv(O/'DATE_PAIRED_DIAGNOSTIC.csv',index=False)
ds=dates.groupby(['window','event_type']).agg(dates=('day','nunique'),delta_net=('delta_net','mean'),delta_win=('delta_win','mean'));ds.to_csv(O/'DATE_SUMMARY.csv')
tails=c[c.tail30&(c.baseline_selected!=c.new_selected)].copy();tails['change']=np.where(tails.new_selected,'ADDED','REMOVED');tails.to_csv(O/'CHANGED_TAILS.csv',index=False)
c.loc[c.feature_known,['D','floor_progress','Q']].describe(percentiles=[.001,.01,.5,.99,.999]).to_csv(O/'NUMERIC_DISTRIBUTION.csv')
for k in ['D','Q']:c[c.feature_known].sort_values(k).head(20).to_csv(O/('LOWEST_'+k+'.csv'),index=False)
c[c.feature_known].nlargest(20,'Q').to_csv(O/'HIGHEST_Q.csv',index=False)
save('QA.json',dict(old_input_and_seal_unchanged=all(sha(p)==h for p,h in src.items()) and all(sha(p)==h for p,h in seal['hashes'].items()),sameK=True,source_labels=str(R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv'),source_label_sha=sha(R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv'),no_new_simulation=True,full_account_runs=0,formula_parameter_scans=1))
print('MAIN\n',summary[summary.event_type.eq('FALSE_TO_TRUE')].to_string(index=False))
print('PAIRS\n',pd.DataFrame(psum).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('DATE\n',ds.to_string());print('CLUSTERS\n',pd.DataFrame(cl).to_string(index=False))
qc=pc[pc.event_type.eq('FALSE_TO_TRUE')&pc.both_closed]
disp=['window','day','removed_name','added_name','removed_PVR_score','added_PVR_score','removed_Q','added_Q','removed_D','added_D','removed_net_pnl','added_net_pnl','delta_net']
print('BEST_SWAPS\n',qc.nlargest(4,'delta_net')[disp].to_string(index=False));print('WORST_SWAPS\n',qc.nsmallest(4,'delta_net')[disp].to_string(index=False))
print('HIGHEST_Q\n',c[c.feature_known].nlargest(10,'Q')[['window','day','sid','name','D','floor_progress','Q','baseline_selected','new_selected','label','net_pnl']].to_string(index=False))
