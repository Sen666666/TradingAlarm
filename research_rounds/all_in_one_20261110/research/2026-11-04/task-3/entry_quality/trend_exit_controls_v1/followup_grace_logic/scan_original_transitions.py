"""All1709 original cached I on->off transitions; no model/account calls."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,time
import numpy as np,pandas as pd

O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def clean(x):
 if pd.isna(x):return None
 return x.item() if hasattr(x,'item') else x

t0=time.monotonic();sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');assert len(sm)==1709
tot=Counter();period=defaultdict(Counter);examples=defaultdict(list);transitions=[];empty=[]
for item in sm:
 sid=item['symbol'];p=Path(item['refs']['facts']);h=sha(p);assert h==item['output_sha256'][str(p)];SRC[str(p)]=h
 f=pd.read_parquet(p,columns=['close','segment_id','i_target','i_floor','e0_target','e0_floor','e0_ready','g_ready'])
 tot['symbols']+=1;tot['observations']+=len(f)
 if f.empty:empty.append(sid);continue
 assert f.index.is_monotonic_increasing and f.index.is_unique
 c=f.close.to_numpy(dtype=float);it=f.i_target.to_numpy(dtype=float,na_value=np.nan);et=f.e0_target.to_numpy(dtype=float,na_value=np.nan)
 fi=f.i_floor.to_numpy(dtype=float);ef=f.e0_floor.to_numpy(dtype=float);sg=f.segment_id.to_numpy(dtype=float)
 prevsg=np.r_[np.nan,sg[:-1]];same=(sg==prevsg)&np.isfinite(sg);previt=np.r_[np.nan,it[:-1]];prevfloor=np.r_[np.nan,fi[:-1]]
 prior=f.groupby('segment_id',sort=False).i_floor.transform(lambda z:z.ffill().shift()).to_numpy(dtype=float)
 known=np.isfinite(prior)&(prior>0)&np.isfinite(c)&(c>0)
 on=it==1;off=it==0;transition=(previt==1)&off;cross=transition&~same;normal=transition&same
 oldknown=normal&np.isfinite(prevfloor)&(prevfloor>0)&np.isfinite(c)&(c>0)
 hard=oldknown&(c<=prevfloor);above=oldknown&(c>prevfloor)
 soft=above&(et==1)
 rawabove=off&known&(c>prior);raweon=rawabove&(et==1);raweoff=rawabove&(et==0)
 eqon=on&np.isfinite(fi)&np.isfinite(ef)&np.isclose(fi,ef,rtol=1e-12,atol=1e-12)
 masks=dict(I_on=on,I_off=off,I_target_unknown=~np.isfinite(it),E0_target_unknown=~np.isfinite(et),source_first_or_changed=~same,
  I_on_E0_off=on&(et==0),I_on_floor_equals_E0_floor=eqon,I_on_floor_differs_E0=on&np.isfinite(fi)&np.isfinite(ef)&~eqon,I_on_unknown_floor=on&~np.isfinite(fi),
  raw_Ioff_above_same_segment_prior_known_I_floor=rawabove,raw_Ioff_above_prior_floor_E0_on=raweon,raw_Ioff_above_prior_floor_E0_off=raweoff,
  Ioff_prior_floor_unknown=off&~known,all_I_on_to_off=transition,same_segment_I_on_to_off=normal,source_change_I_on_to_off=cross,
  same_segment_transition_prior_floor_known=oldknown,same_segment_transition_prior_floor_unknown=normal&~oldknown,
  same_segment_transition_floor_breached=hard,same_segment_transition_above_prior_floor=above,same_segment_transition_above_prior_floor_E0_on=soft,
  same_segment_transition_E0_off=normal&(et==0),same_segment_transition_E0_on=normal&(et==1),same_segment_transition_E0_unknown=normal&~np.isfinite(et),
  E0_not_ready=(f.e0_ready.to_numpy(dtype=float,na_value=np.nan)==0),G1_not_ready=(f.g_ready.to_numpy(dtype=float,na_value=np.nan)==0))
 for k,m in masks.items():tot[k]+=int(m.sum())
 ds=np.array([str(d.date()) for d in f.index]);scopes={'2022_2023':(ds>='2022-01-01')&(ds<='2023-12-31'),'2024':(ds>='2024-01-01')&(ds<='2024-12-31'),'strong2025_26':(ds>='2025-07-01')&(ds<='2026-06-30')}
 for scope,scope_mask in scopes.items():
  period[scope]['observations']+=int(scope_mask.sum())
  for k,m in masks.items():period[scope][k]+=int((m&scope_mask).sum())
 def record(i):
  return dict(sid=sid,day=ds[i],source_segment=clean(sg[i]),previous_observation_day=ds[i-1] if i else None,previous_source_segment=clean(prevsg[i]),previous_I_target=clean(previt[i]),current_I_target=clean(it[i]),current_E0_target=clean(et[i]),causal_close=clean(c[i]),strict_prior_observation_I_floor=clean(prevfloor[i]) if same[i] else None,same_segment_prior_known_I_floor=clean(prior[i]),off_day_I_floor_saved=clean(fi[i]),current_E0_floor=clean(ef[i]),source_boundary=not bool(same[i]),prior_floor_breached=bool(hard[i]) if normal[i] and oldknown[i] else None,above_prior_floor=bool(above[i]) if normal[i] and oldknown[i] else None,eligible_frozen_grace_necessary_conditions=bool(soft[i]),price_domain='causal adjusted source segment; old-segment numerical comparisons are not permitted')
 for i in np.flatnonzero(transition):transitions.append(record(i))
 for name,mask in [('raw_Ioff_above_prior_floor_E0_on_not_transition',raweon&~normal),('raw_Ioff_above_prior_floor_E0_off_not_transition',raweoff&~normal),('same_segment_transition_above_prior_floor',above),('source_reset_transition',cross)]:
  room=12-len(examples[name])
  if room>0:examples[name].extend(record(i) for i in np.flatnonzero(mask)[:room])

for p in [RR/'b5-g1-20261025/code/policies_g1.py',RR/'pv-strength-b5-20261025/code/policy.py',RR/'pv-strength-b5-20261025/code/arithmetic.py',W/'native-I-cache-interface-20261031/cache.py',W/'case-stock-cp1-warmup-20261031/generate.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'case-stage-ledger-20261031/v3/launch_v3.py',O.parent/'execution_review/no_soft_grace.py',O.parent/'execution_review/NO_SOFT_GRACE_WITNESS.json']:
 SRC[str(p)]=sha(p)
assert tot['same_segment_transition_above_prior_floor_E0_on']==0
save('ALL_POOL_TRANSITION_SUMMARY.json',dict(full_original_cached_warm_history=dict(tot),periods={k:dict(v) for k,v in period.items()},empty_symbols=empty,seconds=time.monotonic()-t0,new_models=0,new_accounts=0,new_native_events=0))
save('ALL_POOL_I_ON_TO_OFF_TRANSITIONS.json',transitions)
save('LOGIC_BOUNDARY_EXAMPLES.json',dict(examples))
SRC[str(__file__)]=sha(__file__);save('SOURCE_SHA256.json',SRC)
print(json.dumps(dict(counts=tot,periods=period,seconds=time.monotonic()-t0),ensure_ascii=False,indent=2))
