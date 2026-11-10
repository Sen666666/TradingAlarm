from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent
p=pd.read_csv(O/'PAIRED_STOCK_DIFFERENCES.csv');c=pd.read_csv(O/'COVERAGE.csv');z=pd.read_csv(O/'ROUNDS.csv')
for arm in ['CONTROL','LOCAL','UNION']:
 q=c[c.arm.eq(arm)][['sid','window','stopped_unknown','unknown_signal_days']].rename(columns={'stopped_unknown':arm+'_path_stopped_unknown','unknown_signal_days':arm+'_flat_signal_unknown_days'});p=p.merge(q,on=['sid','window'],validate='one_to_one')
for arm in ['LOCAL','UNION']:
 p[arm+'_strict_pair_complete']=(p[arm+'_unresolved'].eq(0)&p.CONTROL_unresolved.eq(0)&~p[arm+'_path_stopped_unknown']&~p.CONTROL_path_stopped_unknown)
 p[arm+'_strict_pair_net_diff']=p[arm+'_completed_net']-p.CONTROL_completed_net
 p.loc[~p[arm+'_strict_pair_complete'],arm+'_strict_pair_net_diff']=float('nan')
p.to_csv(O/'PAIRED_STOCK_DIFFERENCES_STRICT_COVERAGE.csv',index=False)
stats=[]
for win,g in p.groupby('window'):
 q=g[g.UNION_strict_pair_complete];stats.append(dict(window=win,pairs_without_unresolved_roots_or_early_termination=len(q),excluded_pairs=len(g)-len(q),net_diff=float(q.UNION_strict_pair_net_diff.sum()),positive_pairs=int(q.UNION_strict_pair_net_diff.gt(1e-8).sum()),negative_pairs=int(q.UNION_strict_pair_net_diff.lt(-1e-8).sum()),equal_pairs=int(q.UNION_strict_pair_net_diff.abs().le(1e-8).sum()),caveat='This is not an all-known-signal sample: flat signal UNKNOWN days and static/prelisting membership remain explicitly in coverage. No outcome-based exclusion; only unresolved-path completeness.'))
(O/'STRICT_COVERAGE_REPORT.json').write_text(json.dumps(dict(reason='Initial total_comparable checked accepted inventory only. Require neither arm stopped on unresolved root, including no-buy root. Reporting only; no economic rerun. Original paired table retained.',rows=stats),indent=2)+'\n')
print(json.dumps(stats,indent=2))
print('UNION roots by origin',z.groupby(['window','arm','origin']).size().to_string())
print('planned risk exceeded',z[(z.status=='COMPLETE')&(-z.net_pnl>z.planned_risk)][['sid','window','arm','birth_day','planned_risk','net_pnl']].to_string(index=False))
