"""Rebuild timing mechanisms only from the new run; no old pairing imported."""
from pathlib import Path
import pandas as pd,json
O=Path(__file__).resolve().parent;P=O/'report'
r=pd.read_csv(P/'CORE_AND_FULL_ROUNDS.csv');b=r[r.arm.eq('A_UNION_B')];f=r[r.arm.eq('RELATIVE_UP_PRIORITY')];common=set(b.event_id)&set(f.event_id);bo=b[~b.event_id.isin(common)];fo=f[~f.event_id.isin(common)]
bc=bo[bo.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];fc=fo[fo.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
p=bc.merge(fc,on=['sid','exit_day'],suffixes=('_baseline','_fresh'),validate='one_to_one');assert len(p)==81
p['timing']=pd.to_datetime(p.entry_day_fresh).lt(pd.to_datetime(p.entry_day_baseline)).map({True:'FRESH_EARLIER',False:'FRESH_LATER'});p['evidence_pair']=p.evidence_usable_closed_baseline&p.evidence_usable_closed_fresh;p['core_delta']=p.core_net_fresh-p.core_net_baseline;p['full_delta']=p.net_pnl_fresh-p.net_pnl_baseline
summary=[]
for scope,g in [('CONDITIONAL_ALL_PAIRS',p),('BOTH_EVIDENCE_USABLE',p[p.evidence_pair])]:
 for timing,h in g.groupby('timing'):summary.append(dict(scope=scope,timing=timing,pairs=len(h),core_delta=h.core_delta.sum(),full_delta=h.full_delta.sum()))
p.to_csv(P/'SAME_STOCK_EXIT_PAIRS.csv',index=False);pd.DataFrame(summary).to_csv(P/'TIMING_MECHANISM.csv',index=False)
newtail=fc[fc.core_return.ge(.5)];rows=[]
for x in newtail.to_dict('records'):
 for y in b[b.sid.eq(x['sid'])].to_dict('records'):
  if pd.isna(y.get('entry_day')):continue
  right=y['exit_day'] if pd.notna(y.get('exit_day')) else y['status_day'];overlap=max(pd.Timestamp(x['entry_day']),pd.Timestamp(y['entry_day']))<min(pd.Timestamp(x['exit_day']),pd.Timestamp(right))
  rows.append(dict(sid=x['sid'],name=x['name'],fresh_event=x['event_id'],fresh_entry=x['entry_day'],fresh_exit=x['exit_day'],fresh_core_return=x['core_return'],baseline_event=y['event_id'],baseline_entry=y['entry_day'],baseline_exit=y.get('exit_day'),baseline_status=y['status'],baseline_core_return=y.get('core_return'),overlap=overlap,same_exit=x['exit_day']==y.get('exit_day'),fresh_evidence_usable=x['evidence_usable_closed'],baseline_evidence_usable=y['evidence_usable_closed']))
pd.DataFrame(rows).to_csv(P/'NEW_TAIL_SAME_STOCK_INTERVALS.csv',index=False)
print(pd.DataFrame(summary).to_string(index=False));print(pd.DataFrame(rows).to_string(index=False))
# Disclose direct fresh promotions separately from indirect state-chain and nonfresh seats.
d=pd.read_csv(O/'dynamic/DECISIONS.csv');rk=pd.read_csv(O/'dynamic/RANKING_AUDIT.csv');db=d[d.arm.eq('A_UNION_B')].set_index('event_id');rf=rk[rk.arm.eq('RELATIVE_UP_PRIORITY')].set_index('event_id')
rows=[]
for x in fo.to_dict('records'):
 e=x['event_id'];old=db.loc[e];rank=rf.loc[e];direct=old.decision=='PASS_NOT_TOP2' and rank.relative_event==1
 rows.append(dict(event_id=e,sid=x['sid'],name=x['name'],signal_day=x['signal_day'],baseline_decision=old.decision,baseline_stock_state=old.stock_state_before,relative_known=rank.relative_known,relative_event=rank.relative_event,original_feasible_rank=rank.original_feasible_rank,new_feasible_rank=rank.new_feasible_rank,mechanism='DIRECT_FRESH_PROMOTION' if direct else 'STATE_CHAIN_OR_OTHER_SLOT',status=x['status'],core_net=x['core_net'],full_net=x['net_pnl'],core_return=x['core_return'],full_return=x['net_return_on_buy_cash'],evidence_usable_closed=x['evidence_usable_closed']))
m=pd.DataFrame(rows);m.to_csv(P/'FRESH_ONLY_MECHANISM_DETAIL.csv',index=False);summary=[]
for typ,g in m.groupby('mechanism'):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];summary.append(dict(mechanism=typ,admitted=len(g),closed=len(c),core_wins=int(c.core_net.gt(0).sum()),core_net_sum=c.core_net.sum(),full_wins=int(c.full_net.gt(0).sum()),full_net_sum=c.full_net.sum(),unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum())))
pd.DataFrame(summary).to_csv(P/'FRESH_ONLY_MECHANISM_SUMMARY.csv',index=False);print('DIRECT_VS_CHAIN',summary)
