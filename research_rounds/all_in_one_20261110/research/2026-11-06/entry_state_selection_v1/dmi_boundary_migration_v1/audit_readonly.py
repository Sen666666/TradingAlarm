import warnings
warnings.filterwarnings('ignore',category=FutureWarning)
import json,hashlib,math,sys
from pathlib import Path
import numpy as np,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/dmi_boundary_migration_v1')
c=pd.read_parquet(O/'FEATURES.parquet');picks=pd.read_parquet(O/'SEALED_PICKS.parquet');moves=pd.read_parquet(O/'RANK_MOVES.parquet')
source=pd.read_csv(O/'SOURCE_AUDIT.csv')
meta=[]
for x in source.itertuples():
 p=pd.read_parquet(x.source).loc[:'2026-05-15']
 ok=np.isfinite(p[['open','high','low','close']]).all(axis=1)&p[['open','high','low','close']].gt(0).all(axis=1)&p.high.ge(p[['open','high','low','close']].max(axis=1))&p.low.le(p[['open','high','low','close']].min(axis=1))&p.segment_id.notna()
 for k in ['price_eligible','observed_bar','is_observed_bar']:ok &= p[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:ok &= ~p[k].fillna(True).astype(bool)
 p=p.loc[ok]
 bad=(p.groupby('segment_id')[['source_kind','source_path']].nunique(dropna=False)>1).any(axis=1)
 if bad.any() or p[['source_kind','source_path']].isna().any().any():meta.append(dict(sid=x.sid,bad_segments=int(bad.sum())))
assert not meta,meta[:5]
unknown=set(c.loc[~c.common_known,'row'])
assert len(unknown)==290
for (day,sector),g in c.groupby(['day','sector']):
 base=g.sort_values(['original_priority_rank','sid'])
 for method in ['DMI','CLOSE']:
  mm=moves[moves.method.eq(method)&moves.row.isin(g.row)].set_index('row')
  for i,row in enumerate(base.row):
   if row in unknown:assert mm.loc[row,'sector_rank']==i+1
# Independent iterative implementation on sampled raw prefixes.
samples=c.sample(60,random_state=20261106)
extra=c[~c.common_known].head(5)
samples=pd.concat([samples,extra]).drop_duplicates('row')
mp={x.sid:x.source for x in source.itertuples()}
diffs=[]
for rr in samples.itertuples():
 p=pd.read_parquet(mp[rr.sid]);common=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)['dates']);common=common[(common>='2013-01-01')&(common<=rr.day)]
 p=p.reindex(common)
 last=None;segment=None;count=0;seed=[];state=None;value=None
 for x in p.itertuples():
  vals=[x.open,x.high,x.low,x.close]
  ok=all(np.isfinite(vals)) and min(vals)>0 and x.high>=max(vals) and x.low<=min(vals) and pd.notna(x.segment_id)
  ok=ok and all(getattr(x,k) is not None and pd.notna(getattr(x,k)) and bool(getattr(x,k)) for k in ['price_eligible','observed_bar','is_observed_bar'])
  ok=ok and all(pd.notna(getattr(x,k)) and not bool(getattr(x,k)) for k in ['source_invalid','synthetic_event_bar'])
  if not ok or segment!=x.segment_id:
   last=None;segment=x.segment_id;count=0;seed=[];state=None;value=None
  if not ok:continue
  if last is not None:
   u=x.high-last.high;d=last.low-x.low;ch=x.close-last.close
   v=np.array([u if u>d and u>0 else 0,d if d>u and d>0 else 0,max(ch,0),max(-ch,0)],dtype=float);count+=1
   if count<=14:
    seed.append(v)
    if count==14:state=np.mean(seed,axis=0)
   else:state=(13*state+v)/14
   if count>=14:
    a,b,g,l=state;value=np.array([(a-b)/(a+b) if a+b else 0,(g-l)/(g+l) if g+l else 0])
  last=x
 expected=np.array([rr.d,rr.dclose])
 if value is None:assert np.isnan(expected).all()
 else:
  assert np.isfinite(expected).all();diffs.append(float(np.max(np.abs(value-expected))))
assert max(diffs)<1e-12
lab=pd.read_parquet(O.parent/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet')
merged=c[['sid','day']].merge(lab,on=['sid','day'],how='left',validate='one_to_one')
assert merged[['complete5','complete20','complete60']].notna().all().all()
for h in [5,20,60]:
 g=merged[merged['complete'+str(h)]]
 assert np.isfinite(g[['ret'+str(h),'mae'+str(h),'mfe'+str(h)]]).all().all()
out=dict(all_valid_source_metadata_stable_within_segment=True,stocks=len(source),independent_prefix_samples=len(samples),max_d_error=max(diffs),unknown_slots_verified=len(unknown),all_labels_coverage=True)
print(json.dumps(out))
