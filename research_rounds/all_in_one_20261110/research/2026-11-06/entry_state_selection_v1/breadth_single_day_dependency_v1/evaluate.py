from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;B=R/'breadth_pvr3_priority_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.load(open(O/'SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in seal['hashes'].items())
src=json.load(open(O/'SOURCE_HASHES.json'));assert all(sha(p)==h for p,h in src.items())
c=pd.read_csv(O/'FEATURES_AND_SELECTIONS.csv',parse_dates=['day']);p=pd.read_csv(O/'SEALED_CHANGED_PAIRS.csv',parse_dates=['day'])
z=pd.read_csv(B/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False);z=z[z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')]
cols=['event_id','sid','status','entry_status','entry_day','exit_day','unknown_day','net_pnl','net_return_on_buy_cash','adds','entry_q','entry_price','entry_fee','total_buy_cash']
c=c.rename(columns={'status':'close_status'}).merge(z[cols],on=['event_id','sid'],validate='one_to_one',how='left',sort=False);assert len(c)==14880 and c.status.notna().all()
c['label']='UNKNOWN';done=c.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');c.loc[done,'label']=np.where(c.loc[done,'net_pnl'].gt(0),'W','L');c.loc[c.status.str.startswith('OPEN_CENSORED'),'label']='U';c.loc[c.status.isin(['NEXT_OPEN_BELOW_PROTECTION','MINIMUM_LOT_NOT_FUNDED']),'label']='NO_ENTRY';c['tail30']=done&c.net_return_on_buy_cash.ge(.3)
core=pd.read_csv(R/'breadth_member_quality_v1/ALL_M3_RESULTS.csv',usecols=['event_id','sid','core_net','add_net','label'])
v=c.merge(core,on=['event_id','sid'],validate='one_to_one',suffixes=('','_ref'));assert v.label.eq(v.label_ref).all();c=v.drop(columns='label_ref')
assert np.allclose(c.loc[done,'net_pnl'],c.loc[done,'core_net']+c.loc[done,'add_net'])
def stats(g):
 d=g[g.label.isin(['W','L'])];w=d[d.label.eq('W')];l=d[d.label.eq('L')]
 return dict(n=len(g),dates=g.day.nunique(),events=g.event_id.nunique(),stocks=g.sid.nunique(),W=len(w),L=len(l),U=int(g.label.eq('U').sum()),UNKNOWN=int(g.label.eq('UNKNOWN').sum()),NO_ENTRY=int(g.label.eq('NO_ENTRY').sum()),winrate=len(w)/len(d) if len(d) else np.nan,mean_win=w.net_pnl.mean(),mean_loss=-l.net_pnl.mean(),payoff=w.net_pnl.mean()/(-l.net_pnl.mean()),mean_net=d.net_pnl.mean(),mean_return=d.net_return_on_buy_cash.mean(),tail30=int(d.tail30.sum()),mean_core=d.core_net.mean(),mean_add=d.add_net.mean(),fresh_fraction=g.member_state.eq('FRESH').mean(),feature_known=int(g.feature_known.sum()),mean_PVR=g.PVR_score.mean(),mean_Q=g.Q.mean(),mean_M=g.M.mean(),mean_dependency=g.dependency_fraction.mean(),mean_max_age=g.max_day_age.mean(),mean_initial_cash=(g.entry_q*g.entry_price+g.entry_fee).mean())
out=[]
for scope,h in [('ALL',c),('PVR',c[c.baseline_selected]),('DROP_MAX',c[c.new_selected]),('REMOVED',c[c.baseline_selected&~c.new_selected]),('ADDED',c[~c.baseline_selected&c.new_selected])]:
 for key,g in h.groupby(['window','event_type']):out.append(dict(scope=scope,window=key[0],event_type=key[1],**stats(g)))
summary=pd.DataFrame(out);summary.to_csv(O/'SUMMARY.csv',index=False);c.to_csv(O/'ALL_M3_RESULTS.csv',index=False)
pc=p.copy()
for side,ix in [('removed','removed_index'),('added','added_index')]:
 rows=c.loc[p[ix]].reset_index(drop=True)
 assert rows.sid.eq(p[side+'_sid']).all()
 for col in ['name','label','net_pnl','net_return_on_buy_cash','tail30','core_net','add_net','PVR_score','Q','M','max_day_age','dependency_fraction','member_state','entry_day','exit_day','unknown_day','I_start','I_buy_today','CP1_today']:
  pc[side+'_'+col]=rows[col].to_numpy()
pc['both_closed']=pc.removed_label.isin(['W','L'])&pc.added_label.isin(['W','L'])
pc['delta_net']=pc.added_net_pnl-pc.removed_net_pnl
pc['delta_win']=pc.added_label.eq('W').astype(float)-pc.removed_label.eq('W').astype(float)
pc.to_csv(O/'PAIRED_RESULTS.csv',index=False)
pair_s=[];cl=[]
cal=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet').index
for key,g in pc.groupby(['window','event_type']):
 q=g[g.both_closed];base=dict(window=key[0],event_type=key[1])
 pair_s.append(base|dict(all_pairs=len(g),both_closed=len(q),dates=q.day.nunique(),events=q.event_id.nunique(),removed_W=int(q.removed_label.eq('W').sum()),added_W=int(q.added_label.eq('W').sum()),removed_winrate=q.removed_label.eq('W').mean(),added_winrate=q.added_label.eq('W').mean(),removed_mean_net=q.removed_net_pnl.mean(),added_mean_net=q.added_net_pnl.mean(),delta_net=q.delta_net.mean(),delta_win=q.delta_win.mean(),removed_tails=int(q.removed_tail30.sum()),added_tails=int(q.added_tail30.sum()),added_win_removed_loss=int((q.added_label.eq('W')&q.removed_label.eq('L')).sum()),added_loss_removed_win=int((q.added_label.eq('L')&q.removed_label.eq('W')).sum())))
 if len(q)>1:
  for metric in ['delta_net','delta_win']:
   vals=q[metric].to_numpy()
   for unit,ids in [('signal_date',q.day.to_numpy()),('20_common_day_block',cal.get_indexer(q.day)//20)]:
    us=pd.unique(ids);leave=np.array([vals[ids!=u].mean() for u in us if (ids!=u).any()])
    se=np.sqrt((len(leave)-1)/len(leave)*np.sum((leave-leave.mean())**2)) if len(leave)>1 else np.nan
    cl.append(base|dict(metric=metric,unit=unit,clusters=len(us),estimate=vals.mean(),delete_cluster_SE=se,leave_min=leave.min() if len(leave) else None,leave_max=leave.max() if len(leave) else None))
   us=sorted(set(q.removed_sid)|set(q.added_sid));leave=np.array([vals[(q.removed_sid.ne(u)&q.added_sid.ne(u)).to_numpy()].mean() for u in us])
   se=np.sqrt((len(leave)-1)/len(leave)*np.sum((leave-leave.mean())**2))
   cl.append(base|dict(metric=metric,unit='either_stock_endpoint',clusters=len(us),estimate=vals.mean(),delete_cluster_SE=se,leave_min=leave.min(),leave_max=leave.max()))
pd.DataFrame(pair_s).to_csv(O/'PAIRED_SUMMARY.csv',index=False);pd.DataFrame(cl).to_csv(O/'CLUSTER_DIAGNOSTIC.csv',index=False)
# Both selections complete in exact event; all events including unchanged contribute, no ex-post re-selection.
evrows=[]
for ev,g in c.groupby('event_id'):
 a=g[g.baseline_selected];b=g[g.new_selected];union=g[g.baseline_selected|g.new_selected]
 both=union.label.isin(['W','L']).all()
 evrows.append(dict(event_id=ev,window=g.window.iloc[0],event_type=g.event_type.iloc[0],day=g.day.iloc[0],both_complete=both,K=len(a),delta_net=b.net_pnl.mean()-a.net_pnl.mean() if both else np.nan,delta_win=b.label.eq('W').mean()-a.label.eq('W').mean() if both else np.nan,changed=not set(a.sid).issubset(set(b.sid))))
ev=pd.DataFrame(evrows);ev.to_csv(O/'EVENT_PAIRED_DIAGNOSTIC.csv',index=False)
dates=ev[ev.both_complete].groupby(['window','event_type','day']).agg(delta_net=('delta_net','mean'),delta_win=('delta_win','mean'),events=('event_id','size')).reset_index();dates.to_csv(O/'DATE_PAIRED_DIAGNOSTIC.csv',index=False)
dd=[]
for key,g in ev.groupby(['window','event_type']):
 q=g[g.both_complete];v=dates[dates.window.eq(key[0])&dates.event_type.eq(key[1])]
 dd.append(dict(window=key[0],event_type=key[1],all_events=len(g),both_complete_events=len(q),common_dates=v.day.nunique(),event_equal_delta_net=q.delta_net.mean(),event_equal_delta_win=q.delta_win.mean(),date_equal_delta_net=v.delta_net.mean(),date_equal_delta_win=v.delta_win.mean()))
pd.DataFrame(dd).to_csv(O/'EVENT_DATE_SUMMARY.csv',index=False)
tails=c[c.tail30&(c.baseline_selected!=c.new_selected)].copy();tails['change']=np.where(tails.new_selected,'ADDED','REMOVED');tails.to_csv(O/'CHANGED_TAILS.csv',index=False)
pc.groupby(['window','event_type','removed_label','added_label']).size().rename('pairs').reset_index().to_csv(O/'PAIR_LABEL_COUNTS.csv',index=False)
feature=c.groupby(['window','event_type','member_state']).agg(n=('sid','size'),known=('feature_known','sum'),mean_PVR=('PVR_score','mean'),mean_M=('M','mean'),mean_dependency=('dependency_fraction','mean'),mean_Q=('Q','mean'),old_count=('baseline_selected','sum'),new_count=('new_selected','sum'));feature.to_csv(O/'MEMBER_STATE_DIAGNOSTIC.csv')
# Inputs and prior seal must remain unchanged.
assert all(sha(p)==h for p,h in seal['hashes'].items());assert all(sha(p)==h for p,h in src.items())
dump('QA.json',dict(selected_K_preserved=True,unknown_slots_preserved=True,baseline_identity_exact=True,source_and_selection_hashes_unchanged=True,outcome_source_sha256=sha(B/'rounds/ALL_SHADOW_ROUNDS.csv'),closed_cashflow_decomposition_rows=int(done.sum()),no_new_economic_simulation=True,no_account=True,no_parameter_search=True))
print('MAIN\n',summary[summary.event_type.eq('FALSE_TO_TRUE')].to_string(index=False));print('PAIRED\n',pd.DataFrame(pair_s).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('DATE\n',pd.DataFrame(dd).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print('CLUSTERS\n',pd.DataFrame(cl).query("event_type=='FALSE_TO_TRUE'").to_string(index=False))
cols=['window','day','name','sid','change','PVR_score','robust_score','M','max_day_age','member_state','net_pnl','net_return_on_buy_cash']
print('CHANGED TAILS\n',tails[tails.event_type.eq('FALSE_TO_TRUE')][cols].sort_values(['window','change','net_pnl'],ascending=[True,True,False]).to_string(index=False))
qc=pc[pc.event_type.eq('FALSE_TO_TRUE')&pc.both_closed];cols=['window','day','removed_name','added_name','removed_PVR_score','added_PVR_score','removed_Q','added_Q','removed_member_state','added_member_state','removed_net_pnl','added_net_pnl','delta_net']
print('POSITIVE_EXAMPLES\n',qc.nlargest(5,'delta_net')[cols].to_string(index=False));print('NEGATIVE_EXAMPLES\n',qc.nsmallest(5,'delta_net')[cols].to_string(index=False))
