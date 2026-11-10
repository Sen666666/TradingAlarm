"""Descriptive decomposition of the single sealed run, no new consumer or labels fed back."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;D=O/'report'
z=pd.read_csv(D/'INITIAL_AND_FULL_ROUNDS.csv',low_memory=False);nd=pd.read_csv(O/'economic/DECISIONS.csv',low_memory=False);attrs=pd.read_csv(D/'BASELINE_AB_DISPOSITION.csv');tails=pd.read_csv(D/'BASELINE_44_TAILS.csv')
b=z[z.arm.eq('A_UNION_B')];n=z[z.arm.eq('AB_FAST_SMALL')];bi=set(b.event_id);ni=set(n.event_id)
def stat(g):
 done=g[g.initial_evidence_usable]
 return dict(permits=len(g),confirmed_fill=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),financial_unknown_closed=int((g.initial_closed&~g.initial_evidence_usable).sum()),usable_closed=len(done),wins=int(done.initial_net.gt(0).sum()),win_rate=float(done.initial_net.gt(0).mean()) if len(done) else None,mean_net=float(done.initial_net.mean()) if len(done) else None,net_sum=float(done.initial_net.sum()),winners_sum=float(done.loc[done.initial_net>0,'initial_net'].sum()),losers_sum=float(done.loc[done.initial_net<=0,'initial_net'].sum()),tail50=int(done.initial_return.ge(.5).sum()))
co=[]
for name,g in [('COMMON_BASELINE',b[b.event_id.isin(ni)]),('COMMON_NEW',n[n.event_id.isin(bi)]),('BASELINE_ONLY',b[~b.event_id.isin(ni)]),('NEW_ONLY',n[~n.event_id.isin(bi)]),('NEW_WITH_AB_MARKET_EVENT',n[n.AB_event_id.notna()]),('NEW_NO_AB_MARKET_EVENT',n[n.AB_event_id.isna()])]:co.append(dict(cohort=name,**stat(g)))
pd.DataFrame(co).to_csv(D/'EVENT_COHORTS.csv',index=False)
src=[D/'INITIAL_AND_FULL_ROUNDS.csv',O/'economic/DECISIONS.csv']
P=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';p=P/'COMMON_K_COMPARISON.parquet';src.append(p)
sec=pd.read_parquet(p)[['day','sector','M3_candidate']];sec.day=pd.to_datetime(sec.day)
rr=pd.read_parquet(P/'RIGHT3.parquet');kk=pd.read_parquet(P/'KNOWN3.parquet');src.extend([P/'RIGHT3.parquet',P/'KNOWN3.parquet'])
n=n.copy();n['day']=pd.to_datetime(n.signal_day);n=n.merge(sec,on=['day','sector'],how='left',validate='many_to_one')
n['stock_M3']=[1 if d in kk.index and sid in kk and kk.at[d,sid] and rr.at[d,sid] else 0 if d in kk.index and sid in kk and kk.at[d,sid] else -1 for d,sid in zip(n.day,n.sid)]
n['M3_state']=['S'+str(int(s) if pd.notna(s) else -1)+'_M'+str(m) for s,m in zip(n.M3_candidate,n.stock_M3)]
metrics=[]
for (hasAB,state),g in n.groupby([n.AB_event_id.notna(),'M3_state']):
 metrics.append(dict(has_AB_event=hasAB,state=state,**stat(g)))
pd.DataFrame(metrics).to_csv(D/'DESCRIPTIVE_ENTRY_M3_STATE.csv',index=False)
n[['round_id','event_id','day','sid','entry_role','source_mask','M3_candidate','stock_M3','M3_state']].to_csv(D/'ENTRY_M3_STATE_DETAIL.csv',index=False)
displaced=attrs[attrs.disposition.eq('SAME_CLOSE_NOT_TOP2')]
taildetail=tails.merge(attrs,on=['baseline_event_id','sid'],suffixes=('','_base'),validate='one_to_one')
taildetail.to_csv(D/'BASELINE_44_TAIL_DISPOSITION.csv',index=False)
blocked=attrs[attrs.disposition.eq('BLOCKED_UNKNOWN')].merge(n[['round_id','status','signal_day','entry_day','status_day','entry_role','source_mask']],left_on='new_blocking_round_id',right_on='round_id',how='left',validate='many_to_one')
blocked.to_csv(D/'AB_BLOCKED_BY_UNKNOWN_DETAIL.csv',index=False)
cpd=nd[nd.selected].merge(n[n.entry_role.eq('MOBILE_CP')],on='round_id',suffixes=('_decision',''))
cpd['I_close_rejected_before_CP']=cpd.role_checks.map(lambda c:any(x['role']=='I_CORE' for x in json.loads(c)))
cpstats=[dict(I_close_rejected_before_CP=bool(k),**stat(g)) for k,g in cpd.groupby('I_close_rejected_before_CP')]
pd.DataFrame(cpstats).to_csv(D/'CP_INITIAL_FUNCTION.csv',index=False)
cpd[['round_id','sid','name','signal_day','I_close_rejected_before_CP','role_checks','status','initial_net','initial_return','initial_evidence_usable']].to_csv(D/'CP_INITIAL_FUNCTION_DETAIL.csv',index=False)
period=[]
for arm,g in z.groupby('arm'):
 gg=g.copy();gg['quarter']=pd.to_datetime(gg.signal_day).dt.to_period('Q').astype(str)
 for q,h in gg.groupby('quarter'):period.append(dict(arm=arm,quarter=q,**stat(h)))
pd.DataFrame(period).to_csv(D/'DESCRIPTIVE_CLOSED_QUARTERS.csv',index=False)
# Confirmed-fill unknown bounds are only label uncertainty arithmetic, not a strategy or return bound.
bounds=[]
for arm,g in z.groupby('arm'):
 f=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];c=f[f.initial_evidence_usable];wins=int(c.initial_net.gt(0).sum());unresolved=len(f)-len(c)
 bounds.append(dict(arm=arm,confirmed_fills=len(f),evidence_closed=len(c),wins=wins,unresolved_filled=unresolved,all_unresolved_lose=wins/len(f),all_unresolved_win=(wins+unresolved)/len(f),no_causal_or_economic_bound=True))
summary=dict(cohorts=co,displaced_same_close=len(displaced),displaced_with_non_AB_selected=int(displaced.new_selected_non_AB_same_day.gt(0).sum()),unknown_blocked_AB=len(blocked),unknown_blocking_causes=blocked.status.value_counts().to_dict(),tail_no_overlap=taildetail[taildetail.classification.eq('NO_CONFIRMED_OVERLAP')][['sid','name','baseline_initial_return','disposition']].to_dict('records'),confirmed_fill_label_bounds=bounds)
(D/'MECHANISM_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n')
(D/'MECHANISM_SOURCE_HASHES.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in src},indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
