from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=pd.read_csv(O/'SEMICONDUCTOR_ALL_QUEUE_CHECKS.csv');cols=['event_id','day','sid','name','queue_rank','I_valid','rank_known','close_check','close_quantity']
def freeze(x):return x[x.I_valid&x.rank_known&x.close_check.eq('PASS_CONDITIONAL_PROXY')].sort_values(['event_id','queue_rank']).groupby('event_id',sort=False).head(2)[cols]
a=freeze(d[cols].copy());poison=d.copy()
for c in poison.columns:
 if c.startswith('next_') or c in ['status','selected_v2']:poison[c]='UNAVAILABLE_FUTURE_POISON'
b=freeze(poison[cols].copy());pd.testing.assert_frame_equal(a,b)
keys=set(zip(a.event_id,a.sid));d['selected_close_frozen']=[(r.event_id,r.sid) in keys for r in d.itertuples()];d['next_pass_for_frozen_only']=d.selected_close_frozen&d.status.eq('LEGAL_CONDITIONAL_PROXY');d.to_csv(O/'CLOSE_FROZEN_ALL_CANDIDATES.csv',index=False);d[d.selected_close_frozen].to_csv(O/'CLOSE_FROZEN_SELECTED.csv',index=False)
summary=[]
for e,g in d.groupby('event_id'):
 summary.append(dict(event=e,right3=len(g),I_valid=int(g.I_valid.sum()),close_feasible=int(g.close_check.eq('PASS_CONDITIONAL_PROXY').sum()),all_next_proxy_feasible_descriptive_only=int(g.status.eq('LEGAL_CONDITIONAL_PROXY').sum()),frozen_at_close=g[g.selected_close_frozen][['sid','name','queue_rank','close_quantity','next_quantity','next_raw_open','next_check']].to_dict('records'),frozen_next_pass=int(g.next_pass_for_frozen_only.sum()),replacement_after_open_allowed=False))
(O/'CLOSE_FREEZE_AMENDMENT.json').write_text(json.dumps(dict(created_utc=str(pd.Timestamp.now(tz='UTC')),supersedes_preflight_selection_wording=True,reason='Parent clarification: freeze at most2 legal candidates using t-close information; if next-open fails do not replace at same open. Earlier two diagnostic target dates happened to select the same4 stocks, but prior prose permitted an invalid open re-selection.',selection_function_uses_only=cols,all_future_columns_poison_did_not_change_selection=True,rows=summary,fee_and_capacity_and_orderability_remain_proxy=True),ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
