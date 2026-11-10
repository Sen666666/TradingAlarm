"""Post-result explanation only. No new choices, economic rerun, or threshold search."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
c=pd.read_csv(O/'ALL_CANDIDATES_COMMON_DOMAIN.csv',low_memory=False);s=pd.read_csv(O/'SEALED_CLOSE_SELECTED.csv',low_memory=False);x=pd.read_csv(O/'ALL_SWAPPED_ROUNDS.csv',low_memory=False);z=pd.read_csv(O/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False)
rows=[]
for (w,a,t),g in c[c.ranking_common_known & c.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')].groupby(['window','arm','event_type']):
 q=s[(s.window==w)&(s.arm==a)&(s.event_type==t)];base=q[q.ranking_strategy.eq('PVR_DESC')];new=q[q.ranking_strategy.eq('PVR3_PRIORITY')];true=g[g.PVR_state.eq(1)];false=g[g.PVR_state.eq(0)]
 rows.append(dict(window=w,arm=a,event_type=t,feasible=len(g),true=len(true),false=len(false),point_biserial_score_state=g.PVR_score.corr(g.PVR_state) if len(true) and len(false) else np.nan,current_ge60=int(g.PVR_score.ge(60).sum()),current_ge60_but_not3=int((g.PVR_score.ge(60)&g.PVR_state.eq(0)).sum()),persistent_mean_score=true.PVR_score.mean(),notpersistent_mean_score=false.PVR_score.mean(),baseline_selected_true=int(base.PVR_state.eq(1).sum()),new_selected_true=int(new.PVR_state.eq(1).sum()),selected=len(base),baseline_selected_true_fraction=base.PVR_state.eq(1).mean(),new_selected_true_fraction=new.PVR_state.eq(1).mean()))
pd.DataFrame(rows).to_csv(O/'PERSISTENCE_SCORE_OVERLAP.csv',index=False)
x=x.merge(c[['event_id','sid','PVR_state']],on=['event_id','sid'],validate='one_to_one');parts=[]
for (w,a,t,k),g in x.groupby(['window','arm','event_type','change']):
 d=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];win=d[d.net_pnl.gt(0)];loss=d[d.net_pnl.lt(0)];tail=d[d.net_return_on_buy_cash.ge(.3)]
 parts.append(dict(window=w,arm=a,event_type=t,change=k,all_rows=len(g),closed=len(d),wins=len(win),losses=len(loss),gross_winning_net_pnl_cny=win.net_pnl.sum() if len(d) else np.nan,gross_losing_net_pnl_cny=loss.net_pnl.sum() if len(d) else np.nan,closed_pnl_sum_descriptive_not_portfolio=d.net_pnl.sum() if len(d) else np.nan,closed_tail_count=len(tail),closed_tail_pnl_sum=tail.net_pnl.sum() if len(d) else np.nan,closed_nontail_pnl_sum=d.loc[d.net_return_on_buy_cash.lt(.3),'net_pnl'].sum() if len(d) else np.nan,mean_current_pvr=g.PVR_score.mean(),median_current_pvr=g.PVR_score.median(),persistent_true=int(g.PVR_state.eq(1).sum()),overlapping_independent_sums_not_account=True))
pd.DataFrame(parts).to_csv(O/'SWAP_WIN_LOSS_TAIL_CONTRIBUTION.csv',index=False)
# All net outcomes in a changed event must be closed before its paired comparison is reported.
paired=[]
for eid,g in x.groupby('event_id'):
 if set(g.change)!=set(['ADDED','REMOVED']):continue
 known=g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND').all();a=g[g.change.eq('ADDED')];b=g[g.change.eq('REMOVED')]
 paired.append(dict(event_id=eid,window=g.window.iloc[0],arm=g.arm.iloc[0],event_type=g.event_type.iloc[0],swaps=len(a),both_all_swapped_closed=known,added_minus_removed_pnl=(a.net_pnl.sum()-b.net_pnl.sum()) if known else np.nan,added_wins=int(a.net_pnl.gt(0).sum()) if known else np.nan,removed_wins=int(b.net_pnl.gt(0).sum()) if known else np.nan))
pair=pd.DataFrame(paired);pair.to_csv(O/'PAIRED_CHANGED_EVENT_DIAGNOSTIC.csv',index=False)
# Three-day values of every swapped identity, selected before looking up these past-only values.
p=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet');p.day=pd.to_datetime(p.day);by_sid={sid:g.sort_values('day') for sid,g in p.groupby('sid')};past=[]
for r in x.itertuples():
 v=by_sid[r.sid];v=v[v.day.le(pd.Timestamp(r.day))].tail(3)
 for k in v.itertuples():past.append(dict(event_id=r.event_id,sid=r.sid,name=r.name,window=r.window,arm=r.arm,event_type=r.event_type,change=r.change,decision_day=r.day,past_day=k.day,PVR=k.score,PVR3=k.state,valid=k.valid_observation,source_segment=k.source_segment))
pd.DataFrame(past).to_csv(O/'ALL_SWAPPED_PVR3_PAST_VALUES.csv',index=False)
print(pd.DataFrame(rows).query("arm=='M3' and event_type=='FALSE_TO_TRUE'").to_string(index=False));print('CONTRIBUTIONS');print(pd.DataFrame(parts).query("arm=='M3' and event_type=='FALSE_TO_TRUE'").to_string(index=False));print('PAIRED');print(pair.query("arm=='M3' and event_type=='FALSE_TO_TRUE'").groupby('window').agg(changed_events=('event_id','size'),all_swapped_closed_events=('both_all_swapped_closed','sum'),known_paired_delta=('added_minus_removed_pnl',lambda x:x.sum(min_count=1))).to_string())
