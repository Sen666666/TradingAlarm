from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;E=O.parent
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
z=pd.read_csv(O/'ROUNDS.csv',parse_dates=['signal_day','entry_day','exit_day'],low_memory=False)
d=pd.read_csv(O/'DECISIONS.csv',parse_dates=['day'],low_memory=False)
a=pd.read_csv(O/'ACTIONS.csv',parse_dates=['day'],low_memory=False)
ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'],low_memory=False)
rows=[]
for (win,arm),g in z.groupby(['window','arm']):
 done=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];w=done[done.net_pnl.gt(0)];l=done[done.net_pnl.le(0)]
 entered=g.entry_status.eq('CONDITIONAL_OPEN_PROXY');unknown=g.status.str.contains('UNKNOWN');censored=g.status.str.contains('CENSORED');reject=g.status.str.contains('NOFILL')
 n=len(done);p=len(w)/n if n else np.nan;center=(p+1.96**2/(2*n))/(1+1.96**2/n) if n else np.nan;half=1.96*np.sqrt(p*(1-p)/n+1.96**2/(4*n*n))/(1+1.96**2/n) if n else np.nan
 rows.append(dict(window=win,arm=arm,selected=len(g),entered=int(entered.sum()),closed=n,wins=len(w),losses=len(l),win_rate=p,win_rate_wilson_low=center-half,win_rate_wilson_high=center+half,mean_win_cny=w.net_pnl.mean(),mean_loss_cny=l.net_pnl.mean(),win_loss_cny=w.net_pnl.mean()/(-l.net_pnl.mean()) if len(w) and len(l) else np.nan,win_loss_return=w.net_return_on_buy_cash.mean()/(-l.net_return_on_buy_cash.mean()) if len(w) and len(l) else np.nan,mean_return=done.net_return_on_buy_cash.mean(),median_return=done.net_return_on_buy_cash.median(),tail_ge30=int(done.net_return_on_buy_cash.ge(.3).sum()),max_return=done.net_return_on_buy_cash.max(),min_return=done.net_return_on_buy_cash.min(),loss_beyond3000=int(done.net_pnl.lt(-3000).sum()),worst_loss_cny=done.net_pnl.min(),unknown=int(unknown.sum()),unknown_after_entry=int((unknown&entered).sum()),censored=int(censored.sum()),censored_after_entry=int((censored&entered).sum()),known_nofill=int(reject.sum()),known_fees_all_actions=g.all_fees.sum(),closed_fees=done.all_fees.sum(),mean_closed_fees=done.all_fees.mean(),adds=int(g.added.fillna(False).sum()),post_birth_window_adds=g.post_birth_window_adds.sum()))
pd.DataFrame(rows).to_csv(O/'ARM_COMPARISON.csv',index=False)
coverage=[]
for (win,arm,typ),g in d.groupby(['window','arm','event_type']):
 x=z[(z.window==win)&(z.arm==arm)&(z.event_type==typ)]
 counts=g.decision.value_counts().to_dict()
 coverage.append(dict(window=win,arm=arm,event_type=typ,raw_births=len(g),I_qualified=int(g.I_qualified.sum()),PVR_known=int(g.PVR_known.sum()),I_and_PVR_known=int((g.I_qualified&g.PVR_known).sum()),selected=int(g.selected.sum()),entered=int(x.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),completed=int(x.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND').sum()),blocked_held=int(g.decision.eq('BLOCKED_HELD').sum()),blocked_unknown=int(g.decision.eq('BLOCKED_UNKNOWN').sum()),blocked_pending=int(g.decision.eq('BLOCKED_BUY_PENDING').sum()),decision_counts=json.dumps(counts)))
pd.DataFrame(coverage).to_csv(O/'ENTRY_FUNNEL.csv',index=False)
ad=d[d.event_type.eq('A_SECTOR_BIRTH')]
left=ad[ad.arm.eq('A_ONLY')].drop(columns='arm');right=ad[ad.arm.eq('A_UNION_B')].drop(columns='arm')
compare=left.merge(right,on=['window','event_id','day','sid'],suffixes=('_Aonly','_Union'),validate='one_to_one')
compare['comparison']=np.select([compare.selected_Aonly&compare.selected_Union,compare.selected_Aonly&~compare.selected_Union,~compare.selected_Aonly&compare.selected_Union],['BOTH_SELECTED','A_ONLY_SELECTED','UNION_ONLY_SELECTED'],default='NEITHER')
compare.to_csv(O/'A_RECEIPT_DISPLACEMENT.csv',index=False)
compare.groupby(['window','comparison','decision_Aonly','decision_Union']).size().rename('count').reset_index().to_csv(O/'A_DISPLACEMENT_COUNTS.csv',index=False)
# Full event-level named case output, including why a visually appealing birth was not bought.
named=['300085.SZ','002583.SZ','603061.SH','300623.SZ','688498.SH','300666.SZ','301611.SZ','300570.SZ','688502.SH','000833.SZ','002423.SZ','603005.SH','688233.SH','688220.SH','688008.SH','688536.SH']
cases=d[d.sid.isin(named)&d.window.ne('2022')].merge(z.drop(columns=['window','sid','event_type','PVR_score','name','industry','sector']),on=['arm','event_id'],how='left',suffixes=('','_outcome'),validate='one_to_one')
cases.to_csv(O/'NAMED_CASES.csv',index=False)
closed=z[z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
closed[closed.net_return_on_buy_cash.ge(.3)].sort_values(['window','arm','net_return_on_buy_cash'],ascending=[True,True,False]).to_csv(O/'ALL_CLOSED_TAILS_GE30.csv',index=False)
z[z.window.eq('2026H1_SEMI')].to_csv(O/'ALL_2026H1_SEMI_ROUNDS.csv',index=False)
# Daily action checks and exact cross-arm shared-event identity, not post hoc performance retuning.
shared=compare[compare.comparison.eq('BOTH_SELECTED')][['window','event_id']]
zz=z.merge(shared,on=['window','event_id'])
pairs=zz[zz.arm.eq('A_ONLY')].merge(zz[zz.arm.eq('A_UNION_B')],on=['window','event_id'],suffixes=('_Aonly','_Union'))
for col in ['status','entry_day','entry_q','entry_price','exit_day','net_pnl','net_return_on_buy_cash','all_fees','added']:
 l=pairs[col+'_Aonly'];r=pairs[col+'_Union']
 if pd.api.types.is_numeric_dtype(l):ok=np.isclose(l,r,equal_nan=True)
 else:ok=(l.eq(r)|(l.isna()&r.isna())).to_numpy()
 assert bool(ok.all()),('shared identical entry event differs',col)
save('REPORT_QA.json',dict(shared_selected_A_events=len(pairs),same_A_event_round_paths_identical=True,unknown_excluded_not_losses=True,no_aggregate_NAV_reported=True,denominator_reconciles=all(x['selected']==x['closed']+x['unknown']+x['censored']+x['known_nofill'] for x in rows)))
assert all(x['selected']==x['closed']+x['unknown']+x['censored']+x['known_nofill'] for x in rows)
print(pd.DataFrame(rows).to_string(index=False))
print('\nFUNNEL');print(pd.DataFrame(coverage).drop(columns='decision_counts').to_string(index=False))
print('\nDISPLACEMENT');print(compare.groupby(['window','comparison','decision_Union']).size().to_string())
