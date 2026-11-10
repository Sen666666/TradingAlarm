from pathlib import Path
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/equal_entry_validation_v1')
q=pd.read_csv(O/'QUEUE_OVERLAP_AND_BACKFILL.csv');q['year']=q.day.str[:4].astype(int)
a=q.groupby('year').agg(dates=('day','size'),mean_intersection=('intersection','mean'),mean_added=('added','mean'),same_sets=('intersection',lambda x:int(x.eq(20).sum())),fresh_reserved=('reserved_fresh','sum'),verified_reserved=('reserved_confirmed','sum'),fallback=('fallback','sum')).reset_index();a['common_fraction']=a.mean_intersection/20
a.to_csv(O/'ANNUAL_QUEUE_OVERLAP.csv',index=False)
d=pd.read_parquet(O/'SELECTED_SAME_PATH_LABELS.parquet')
d[d.stratum.eq('FRESH_DAY0')].groupby(['strategy','kind']).agg(N=('sid','size'),median_I_age_obs=('original_age_obs','median')).reset_index().to_csv(O/'LOCAL_FIRST_DAY_TYPE_BREAKDOWN.csv',index=False)
c=pd.read_csv(O/'BIG_CHANGED_WITH_LATER_SELECTION.csv')
z=c.merge(d[d.original_age_obs.le(5)&d.open_known].sort_values('day').drop_duplicates(['strategy','original_epoch'])[['strategy','original_epoch','stratum','kind','pvr','day']],on='original_epoch',suffixes=('','_selected'))
z.groupby(['kind','strategy','stratum']).size().rename('N').reset_index().to_csv(O/'CHANGED_BIG_FIRST_SELECTION_STATE.csv',index=False)
print(a.to_string(index=False));print(z.groupby(['kind','strategy','stratum']).size().to_string())
