"""Report-only aggregation of already sealed labels. Never a strategy or economic replay."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;F=O.parent/'fast_entry_equity_2022_v1'
n=pd.read_csv(O/'PERMIT_FEATURES.csv',low_memory=False);s=pd.read_csv(O/'sector_attempt_permits_2022.csv',low_memory=False);a=pd.read_csv(O/'ANCHOR_PERMITS.csv',low_memory=False)
cols=['round_id','sector_attempt_active','sector_attempt_gate_reason','sector_attempt_id','sector_attempt_number','sector_episode_attempt_number','sector_attempt_started_day','sector_episode_started_day','sector_mobile_before','sector_mobile_after','sector_close','sector_E0_episode','sector_last_failure_day','sector_last_failure_reason','sector_post_failure_wait','AB_passing_I_role','selected_role_blocked_by_failure_only'];n=n.merge(s[cols],on='round_id',validate='one_to_one');n=n.merge(a[['round_id','birth_anchor_comparison','I_birth_floor','previous_I_root_day','previous_I_birth_floor','previous_I_last_floor']],on='round_id',validate='one_to_one')
def stat(g):
 c=g[g.initial_evidence_usable];f=g[g.full_evidence_usable];filled=g.entry_status.eq('CONDITIONAL_OPEN_PROXY');wins=int(c.initial_net.gt(0).sum());unresolved=int(filled.sum())-len(c)
 return dict(permits=len(g),confirmed_fills=int(filled.sum()),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),financial_unknown_closed=int((g.initial_closed&~g.initial_evidence_usable).sum()),usable=len(c),wins=wins,win_rate=float(c.initial_net.gt(0).mean()) if len(c) else None,net=float(c.initial_net.sum()),mean_net=float(c.initial_net.mean()) if len(c) else None,tail50=int(c.initial_return.ge(.5).sum()),full_wins=int(f.net_pnl.gt(0).sum()),full_net=float(f.net_pnl.sum()),filled_unresolved=unresolved,label_low=wins/int(filled.sum()) if filled.any() else None,label_high=(wins+unresolved)/int(filled.sum()) if filled.any() else None)
res=[]
for period,g in [('ALL',n)]+list(n.groupby('quarter')):
 for label,z in g.groupby('sector_attempt_gate_reason'):res.append(dict(period=period,feature='INDUSTRY_STATE',value=label,**stat(z)))
 for label,z in g.groupby('selected_role_blocked_by_failure_only'):res.append(dict(period=period,feature='FAILURE_ONLY_SCOPE',value=str(label),**stat(z)))
 res.append(dict(period=period,feature='TOTAL',value='ALL',**stat(g)))
pd.DataFrame(res).to_csv(O/'MECHANISM_STRATA.csv',index=False)
n.to_csv(O/'MERGED_PERMIT_DIAGNOSIS.csv',index=False)
examples=[('600056.SH','2022-02-28'),('600062.SH','2022-03-17'),('603868.SH','2022-03-16'),('601872.SH','2022-03-29'),('688256.SH','2022-03-04'),('600986.SH','2022-01-12'),('300607.SZ','2022-01-11'),('601127.SH','2022-03-28'),('600153.SH','2022-01-05')]
case=n[[tuple(x) in examples for x in n[['sid','signal_day']].to_numpy()]].copy();case['case_selection']='RETROSPECTIVE_ILLUSTRATION_NOT_TRIGGER_OR_VALIDATION_SET';case.to_csv(O/'CROSS_INDUSTRY_EXAMPLES.csv',index=False)
# All potentially suspended original permissions, including their UNKNOWN cases, not a new strategy output.
fail=n[n.selected_role_blocked_by_failure_only].copy();fail.to_csv(O/'FAILURE_ONLY_ALL_CURRENT_PERMITS.csv',index=False)
# Invitation count is not trade quality. More signals per observed I root does not mean longer full I lifetime.
e=pd.read_csv(O/'QUARTER_EVENT_COUNTS.csv');e['eventQ_per_observed_epoch_in_quarter']=e.event_Q/e.eligible_I_epochs;e['permits_per_common_day']=e.permits/e.days;e.to_csv(O/'EVENT_DENSITY_READOUT.csv',index=False)
# Days held use actual conditional entry and actual initial sale, not future labels for selection.
c=n[n.initial_evidence_usable].copy();c['initial_calendar_days']=(pd.to_datetime(c.initial_exit_day)-pd.to_datetime(c.entry_day)).dt.days
c.groupby('quarter').initial_calendar_days.agg(['count','median','mean','min','max']).to_csv(O/'INITIAL_HOLD_DURATION.csv')
(O/'DIAGNOSTIC_CORRECTIONS.json').write_text(json.dumps({'no_new_economic_runs':True,'corrections_before_final':['Nullable source columns explicitly unknown; no inferred industry I/G because original industry facts contain only E0.','BLOCKED_HELD and BLOCKED_UNKNOWN read exact sealed labels, not nonexistent STOCK_NOT_FLAT.','I root unknown has priority over later-buy; G changes do not cross source discontinuity.','Current i_buy required for first/later I-buy class; prior-2022 root is a separate observed-window attribute.','Industry failure history classification stays inside same E0 episode; archived earlier display/classification files are not current results.'],'PIT_boundary':'Physical prefix checks do not establish publication-time PIT for original data or current static universe.'},ensure_ascii=False,indent=2))
print(pd.DataFrame(res).to_string(index=False))
