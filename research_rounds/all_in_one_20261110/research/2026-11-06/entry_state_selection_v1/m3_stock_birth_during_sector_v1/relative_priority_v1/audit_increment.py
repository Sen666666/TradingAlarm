"""Postprocessing only: common events identical; attribution by actual event identity."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
r=pd.read_csv(O/'CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip')
b=r[r.arm.eq('A_UNION_B')].set_index('event_id');n=r[r.arm.eq('RELATIVE_UP_PRIORITY')].set_index('event_id');common=b.index.intersection(n.index)
cols=[c for c in b.columns if c not in ['round_id','arm']]
pd.testing.assert_frame_equal(b.loc[common,cols],n.loc[common,cols],check_exact=True,check_dtype=False)
# Actions also identical, after replacing arm-local round IDs by event IDs.
def actions(mode):
 a=pd.read_csv(O/mode/'ACTIONS.csv',float_precision='round_trip');rr=pd.read_csv(O/mode/'ROUNDS.csv');a=a.merge(rr[['round_id','event_id']],on='round_id',validate='many_to_one');a=a[a.event_id.isin(common)].drop(columns=['round_id','arm']);return a.sort_values(['event_id','day','side']).reset_index(drop=True)
pd.testing.assert_frame_equal(actions('baseline'),actions('economic'),check_dtype=False,check_exact=True)
(O/'COMMON_EVENT_QA.json').write_text(json.dumps(dict(common_events=len(common),all_round_fields_exact=True,all_action_fields_exact=True,max_economic_difference=0),indent=2)+'\n')
rows=[];replace=[];lost=[]
for mode in ['baseline','economic']:
 d=pd.read_csv(O/mode/'DECISIONS.csv');a=pd.read_csv(O/mode/'RANKING_AUDIT.csv');s=d[d.selected].merge(a[['event_id','relative_known','relative_event','original_feasible_rank']],on='event_id',validate='one_to_one')
 for w,g in s.groupby('window'):
  rows.append(dict(mode=mode,window=w,selected=len(g),fresh=int((g.relative_known.eq(True)&g.relative_event.eq(1)).sum()),relative_unknown=int(~g.relative_known.eq(True).sum()) if False else int((~g.relative_known.eq(True)).sum()),outside_own_original_top2=int(g.original_feasible_rank.gt(2).sum())))
 if mode=='baseline':bs=s
 else:ns=s
for keys,g in pd.concat([bs.assign(which='baseline'),ns.assign(which='new')]).groupby(['window','day','sector']):
 old=set(g[g.which.eq('baseline')].event_id);new=set(g[g.which.eq('new')].event_id)
 replace.append(dict(zip(['window','day','sector'],keys))|dict(old_selected=len(old),new_selected=len(new),retained=len(old&new),lost=len(old-new),added=len(new-old),lost_ids=';'.join(sorted(old-new)),added_ids=';'.join(sorted(new-old))))
for w,g in b.groupby('window'):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
 for layer,pnl,ret in [('full','net_pnl','net_return_on_buy_cash'),('core','core_net','core_return')]:
  pos=c[c[pnl].gt(0)];sets=[('ge20',c[c[ret].ge(.2)]),('ge50',c[c[ret].ge(.5)])]
  import math
  for metric in [pnl,ret]:
   z=pos.reset_index().sort_values([metric,'event_id'],ascending=[False,True]).set_index('event_id');sets += [(metric+'_top10',z.head(10)),(metric+'_top10pct',z.head(math.ceil(len(z)*.1)))]
  for label,z in sets:
   for eid,x in z[~z.index.isin(n.index)].iterrows():lost.append(dict(window=w,layer=layer,cohort=label,event_id=eid,sid=x.sid,name=x['name'],baseline_net=x[pnl],baseline_return=x[ret],status='BASELINE_TAIL_NOT_SELECTED'))
pd.DataFrame(rows).to_csv(O/'SELECTION_FRESH_COUNTS.csv',index=False);pd.DataFrame(replace).to_csv(O/'DAILY_SECTOR_REPLACEMENTS.csv',index=False);pd.DataFrame(lost).to_csv(O/'LOST_BASELINE_TAILS.csv',index=False)
# New selected events are also compared against baseline actual selected IDs.
ns.assign(new_vs_baseline_actual=~ns.event_id.isin(bs.event_id)).to_csv(O/'NEW_SELECTION_DETAIL.csv',index=False)
print('COMMON EVENT INVARIANCE PASSED',len(common))
