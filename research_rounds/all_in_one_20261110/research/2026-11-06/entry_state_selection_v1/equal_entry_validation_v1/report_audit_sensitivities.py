from pathlib import Path
import numpy as np,pandas as pd,json,hashlib
import pyarrow.parquet as pq
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/equal_entry_validation_v1')
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
d=pd.read_parquet(O/'SELECTED_SAME_PATH_LABELS.parquet');rows=[]
for sid,g in d[['sid','day','t','original_root_index']].drop_duplicates(['sid','day']).groupby('sid'):
 f=pq.read_table(D/(sid+'.parquet'),columns=['source_row_present','native__e0_ready','native__i_target']).to_pandas()
 bad=~(f.source_row_present.eq(True)&f.native__e0_ready.eq(1)&f.native__i_target.eq(1)).to_numpy()
 cum=np.r_[0,np.cumsum(bad)]
 for _,r in g.iterrows():
  t=int(r.t);root=int(r.original_root_index);b=int(cum[t+1]-cum[root])if root>=0 else None
  rows.append(dict(sid=sid,day=r.day,root_continuity_known=bool(root>=0 and b==0),unknown_or_inactive_common_rows=b))
cont=pd.DataFrame(rows);cont.to_parquet(O/'ROOT_CONTINUITY_DIAGNOSTIC.parquet',index=False)
j=d.merge(cont,on=['sid','day'],validate='many_to_one');s=[]
for h,net in [('20','net20'),('60','net60'),('I','I_net')]:
 prior=set(pd.read_csv(O/('PAIRED_DAILY_'+h+'.csv')).day)
 q=j[j.day.isin(prior)];ok=q.groupby('day').root_continuity_known.all();days=set(ok[ok].index);q=q[q.day.isin(days)]
 rr=q.groupby(['strategy','original_epoch'])[net].mean()
 b=rr.loc['BASE_PVR'];a=rr.loc['STATE_5F_15V']
 date=q.assign(w=q[net]/20).groupby(['day','strategy']).w.sum().unstack()
 s.append(dict(horizon=h,original_paired_dates=len(prior),strict_root_continuity_paired_dates=len(days),base_roots=len(b),alt_roots=len(a),base_root_net=b.mean(),alt_root_net=a.mean(),root_difference=a.mean()-b.mean(),daily_difference=(date.STATE_5F_15V-date.BASE_PVR).mean()))
pd.DataFrame(s).to_csv(O/'ROOT_CONTINUITY_SENSITIVITY.csv',index=False)
j.groupby(['year','strategy']).agg(selected=('sid','size'),continuous_known=('root_continuity_known','sum')).reset_index().to_csv(O/'ROOT_CONTINUITY_COUNTS.csv',index=False)
cov=pd.read_parquet(O/'FIXED_ENTRY_COVERAGE_BY_ROOT.parquet')
for st in ['BASE_PVR','STATE_5F_15V']:
 q=d[d.strategy.eq(st)&d.open_known&d.original_epoch.notna()].sort_values('day').drop_duplicates('original_epoch')
 cov[st+'_first_any_proxy_day']=cov.original_epoch.map(q.set_index('original_epoch').day)
 cov[st+'_first_any_proxy_age_common']=cov.original_epoch.map(q.set_index('original_epoch').original_age_common)
cov['kind']=np.where(cov.base_captured&~cov.alt_captured,'LOST_EARLY',np.where(~cov.base_captured&cov.alt_captured,'ADDED_EARLY',np.where(cov.base_captured&cov.alt_captured,'RETAINED_EARLY','NEITHER_EARLY')))
big=cov[cov.big60];out=[]
for kind,g in big.groupby('kind'):
 out.append(dict(kind=kind,N=len(g),mean_fixed_entry_ret60=g.ret60.mean(),median_fixed_entry_ret60=g.ret60.median(),mean_fixed_entry_mfe60=g.mfe60.mean(),mean_fixed_entry_mae60=g.mae60.mean(),base_selected_by_common60=int(g.BASE_PVR_first_any_proxy_age_common.le(59).sum()),alt_selected_by_common60=int(g.STATE_5F_15V_first_any_proxy_age_common.le(59).sum())))
pd.DataFrame(out).to_csv(O/'BIG_COVERAGE_SIZE_AND_LATE_SELECTION.csv',index=False)
big[big.kind.isin(['LOST_EARLY','ADDED_EARLY'])].to_csv(O/'BIG_CHANGED_WITH_LATER_SELECTION.csv',index=False)
execrows=[]
for(y,st),g in d.groupby(['year','strategy']):
 execrows.append(dict(year=int(y),strategy=st,selected=len(g),entry_gap_ltminus3=int(g.entry_gap.lt(-.03).sum()),entry_gap_ltminus5=int(g.entry_gap.lt(-.05).sum()),worst_entry_gap=g.entry_gap.min(),entry_gap_gt3=int(g.entry_gap.gt(.03).sum()),entry_gap_gt5=int(g.entry_gap.gt(.05).sum()),largest_entry_gap=g.entry_gap.max(),exit_gap_ltminus3=int(g.I_exit_gap.lt(-.03).sum()),worst_exit_gap=g.I_exit_gap.min()))
pd.DataFrame(execrows).to_csv(O/'BIDIRECTIONAL_GAP_WARNINGS.csv',index=False)
roles=d.groupby(['strategy','stratum']).size().rename('N').reset_index();roles['fraction']=roles.N/roles.groupby('strategy').N.transform('sum');roles.to_csv(O/'TOTAL_SELECTED_STATE_MIX.csv',index=False)
print('CONTINUITY');print(pd.DataFrame(s).to_string(index=False));print('OPPORTUNITY SIZE');print(pd.DataFrame(out).to_string(index=False));print('STATE MIX');print(roles.to_string(index=False))
