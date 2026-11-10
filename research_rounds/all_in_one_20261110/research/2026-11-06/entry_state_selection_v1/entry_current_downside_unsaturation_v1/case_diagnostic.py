from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.load(open(O/'SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in seal['hashes'].items())
c=pd.read_csv(O/'FEATURES_AND_SELECTIONS.csv',dtype={'window':str},low_memory=False)
base=pd.read_csv(R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',dtype={'window':str},low_memory=False)
full=pd.read_csv(R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',dtype={'window':str},low_memory=False)
q=c.merge(base[['event_id','sid','never_profitable','core_net','net_pnl','adds','label']],on=['event_id','sid'],how='left',validate='one_to_one')
n=q[q.never_profitable.eq(True)].copy();assert n['adds'].eq(0).all() and n.net_pnl.lt(0).all()
n.to_csv(O/'ORIGINAL_NEVER_PROFITABLE_CASES.csv',index=False)
cnt=n.groupby('window').agg(N=('sid','size'),nonnegative_current=('r',lambda s:(s>=0).sum()),negative_current=('r',lambda s:(s<0).sum()),acute_down=('G_acute_down',lambda s:(s==1).sum()),changed_out=('new_selected',lambda s:(~s).sum()));cnt.to_csv(O/'TARGET_SCOPE_COUNTS.csv')
pr=json.load(open(O/'PROTOCOL.json'));ids=[(t,s) for t,a,b in pr['cases'] for s in (a,b)]+[tuple(z) for z in pr['known_counterexamples']]
cc=c[c.apply(lambda r:(r.day,r.sid) in ids,axis=1)].copy();cc=cc.merge(full[['event_id','sid','label','core_net','net_pnl','net_return_on_buy_cash','entry_day','exit_day','tail30']],on=['event_id','sid'],validate='one_to_one');cc.to_csv(O/'FIXED_CASE_SCORES_AND_SELECTIONS.csv',index=False)
# Reconstruct all retrospective same-opportunity pairs, without calling them an ex ante selection algorithm.
w=q[q.baseline_selected&q.never_profitable.eq(True)].merge(full[['event_id','sid','member_state']],on=['event_id','sid'],validate='one_to_one')
pool=c.merge(full[['event_id','sid','label','core_net','net_pnl','net_return_on_buy_cash']],on=['event_id','sid'],validate='one_to_one')
ps=[]
for _,a in w.sort_values('core_net').iterrows():
 p=pool[pool.event_id.eq(a.event_id)&pool.label.eq('W')&pool.core_net.gt(0)&pool.I_buy_today.eq(a.I_buy_today)&pool.CP1_today.eq(a.CP1_today)].copy()
 if p.empty:continue
 p['distance']=abs(p.PVR_score-a.PVR_score);b=p.sort_values(['distance','sid']).iloc[0]
 ps.append(dict(window=a.window,day=a.day,event_id=a.event_id,industry=a.industry,loss_sid=a.sid,loss_name=a['name'],loss_PVR=a.PVR_score,loss_new_score=a.new_score,loss_net=a.core_net,win_sid=b.sid,win_name=b['name'],win_PVR=b.PVR_score,win_new_score=b.new_score,win_net=b.core_net,PVR_distance=b.distance,I_buy_today=a.I_buy_today,CP1_today=a.CP1_today))
pd.DataFrame(ps).to_csv(O/'RETROSPECTIVE_SAME_EVENT_PAIRS.csv',index=False)
bound=[]
for win,g in c[c.event_type.eq('FALSE_TO_TRUE')].groupby('window'):
 orig=base[base.window.eq(win)];d=orig[orig.label.isin(['W','L'])];W=int(d.net_pnl.gt(0).sum());N=len(d);sw=int((g.baseline_selected&~g.new_selected).sum())
 bound.append(dict(window=win,original_closed=N,original_W=W,swapped_slots=sw,loose_optimistic_winrate_bound=min(1,(W+sw)/N) if N else np.nan,meaning='Loose perfect-replacement bound, not forecast and not evaluation of new labels'))
pd.DataFrame(bound).to_csv(O/'LOOSE_REPLACEMENT_BOUND.csv',index=False)
# Future results already used to pick explanatory cases; no complete outcome join or aggregate PnL for new selection.
facts=dict(stage='STOP_AFTER_SCALE_AND_CASE_DIAGNOSTIC',reason='Limited target coverage, adverse real selection changes in previously fixed winners, unbounded hypothetical tiny-scale behavior. No coefficient sweep or economic simulation.',observed_min_s=float(c[c.feature_known].s.min()),observed_min_q=float(c[c.feature_known].q.min()),observed_min_stress=float(c[c.feature_known].current_stress.min()),original_never_green_2022=233,original_never_green_2024=128,original_never_green_no_add_confirmed=True,new_total_winrate_evaluated=False,new_total_pnl_evaluated=False,full_account_runs=0,retrospective_pair_count=len(ps),source_hashes={str(p):sha(p) for p in [R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',Path(__file__)]})
(O/'DIAGNOSTIC_STOP.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2))
print(cnt.to_string());print(pd.DataFrame(bound).to_string(index=False));print('CASES',len(cc),'PAIRS',len(ps))
