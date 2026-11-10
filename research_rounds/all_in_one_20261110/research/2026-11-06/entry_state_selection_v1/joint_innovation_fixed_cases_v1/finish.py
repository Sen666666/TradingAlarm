"""Seal/report fixed diagnostic; connects ONLY existing labels after FEATURE_SEAL."""
from pathlib import Path
import json,hashlib,datetime,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;P=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
seal=json.loads((O/'FEATURE_SEAL.json').read_text())
for n,h in seal['files'].items():assert sha(O/n)==h,(n,'sealed feature changed')
f=pd.read_csv(O/'FIXED_CASES_PRELABEL.csv');s=pd.read_csv(O/'STARTUP_DAILY.csv');d=pd.read_csv(O/'TARGET_DAILY_PRELABEL.csv')
lp=P/'cross_window_entry_mechanism_v1/FIXED_CASE_FEATURES_WITH_EXISTING_LABELS.csv'
labels=pd.read_csv(lp)
lcols=['case_id','economic_role','label_connection','label_core_net','label_core_return','label_initial_net','label_initial_return','label_source_file','label_source_sha256']
joined=f.merge(labels[lcols],on='case_id',validate='one_to_one')
joined['existing_initial_net']=np.where(joined.role.str.startswith('AB'),joined.label_core_net,joined.label_initial_net)
joined['existing_initial_return']=np.where(joined.role.str.startswith('AB'),joined.label_core_return,joined.label_initial_return)
assert joined.existing_initial_net.notna().sum()==19
assert joined.loc[joined.role.str.startswith('INPUT_ONLY'),'existing_initial_net'].isna().all()
joined.to_csv(O/'FIXED_CASES_WITH_EXISTING_LABELS.csv',index=False)
save('LABEL_CONNECTION.json',dict(after_feature_seal=True,feature_seal_sha256=sha(O/'FEATURE_SEAL.json'),
 source=str(lp),source_sha256=sha(lp),labels_connected=19,input_only_without_labels=6,
 role_contract='AB uses corrected core layer, FAST uses original initial layer. Not new lifecycle or full-round success estimate.'))
# Exact rational check for descriptive known-only record dates, independently of the floating record output.
rational=[]
mem=pd.read_parquet(O/'MEMBER_FEATURES.parquet')
with np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False) as hh:
 cal=pd.DatetimeIndex(hh['dates'])
for sid,g in d.groupby('sid'):
 # The full63 reference may extend beyond target-daily. Use member feature panel to reconstruct.
 sec=g.sector.iloc[0];m=mem[mem.sector.eq(sec)&~mem.sid.eq(sid)]
 pv=m.pivot(index='day',columns='sid',values='jplus').sort_index()
 known=pv.ge(0);v=pv.clip(lower=0).astype('int64');K=known.sum(axis=1);S=v.sum(axis=1);T=(v*v).sum(axis=1)
 num=(S*S-T).astype('int64');den=(63**2*K*(K-1)).astype('int64')
 pm=m.pivot(index='day',columns='sid',values='jminus').reindex(pv.index)
 vv=pm.clip(lower=0).astype('int64');sn=vv.sum(axis=1);tn=(vv*vv).sum(axis=1);nm=sn*sn-tn
 for row in g.itertuples():
  t=pd.Timestamp(row.day);ix=pv.index.get_loc(t)
  if ix<63 or den.iloc[ix]<=0 or (den.iloc[ix-63:ix]<=0).any():continue
  # Member save dates can contain separated ranges. A missing immediate common date must not be bypassed.
  # Feature output only compares the exact common-day63 reference; validate expected history length via frozen source calendar.
  ci=cal.get_loc(t);expected=cal[ci-63:ci+1]
  if not pv.index[ix-63:ix+1].equals(expected):continue
  a=int(num.iloc[ix]);b=int(den.iloc[ix])
  exact=all(a*int(dd)>int(nn)*b for nn,dd in zip(num.iloc[ix-63:ix],den.iloc[ix-63:ix])) and a>int(nm.iloc[ix])
  stored=row.J_known_event
  assert isinstance(stored,(bool,np.bool_)),(sid,t,stored,type(stored))
  assert exact==bool(stored),(sid,t,'known rational mismatch')
  rational.append((sid,str(t.date()),exact))
  # Only compute calendar once in a normal implementation; this read-only verification intentionally doesn't change features.
save('KNOWN_POINT_RATIONAL_QA.json',dict(checked_target_days=len(rational),mismatches=0,
 method='Exact integer cross-products of q/63 pair numerator and known-only K denominator; complete common63 dates checked.'))
unique_known=s[s.J_known_event.eq(True)][['sector','industry','day']].drop_duplicates()
unique_volume=s[s.J_known_only_not_price_known_only.eq(True)][['sector','industry','day']].drop_duplicates()
unique_price=s[s.PRICE_known_event.eq(True)][['sector','industry','day']].drop_duplicates()
unique_known.to_csv(O/'STARTUP_UNIQUE_KNOWN_EVENT_DAYS.csv',index=False)
unique_volume.to_csv(O/'STARTUP_UNIQUE_J_ONLY_EVENT_DAYS.csv',index=False)
summary=dict(fixed25_J_status=f.J_event_status.value_counts().to_dict(),
 fixed25_known_only_records=int(f.J_known_event.eq(True).sum()),
 startup_target_days=len(s),startup_J_status=s.J_event_status.value_counts().to_dict(),
 startup_known_only_records=int(s.J_known_event.eq(True).sum()),
 startup_unique_known_industry_days=len(unique_known),startup_unique_price_industry_days=len(unique_price),
 startup_unique_J_only_industry_days=len(unique_volume),
 startup_J_only_all_fixed_status_unknown=bool(s.loc[s.J_known_only_not_price_known_only.eq(True),'J_event_status'].eq('UNKNOWN').all()),
 startup_all_full_current_snapshot_unknown=bool(s.FULL_CURRENT_event_status.eq('UNKNOWN').all()),
 same_mask_price_K_equal=bool(d.J_plus_K.eq(d.PRICE_plus_K).all()),
 J_participant_subset_of_price=True,
 natural_price_K_differences=int(d.PRICE_plus_K.ne(d.PRICE_NATURAL_plus_K).sum()),
 J_known_record_below_previous_day=int(d.J_known_record_below_previous_day.eq(True).sum()),
 J_known_consecutive_records=int(d.J_known_consecutive_record.eq(True).sum()),
 no_predictive_increment_demonstrated=True,no_gate_or_ranking_consumer=True)
save('SUMMARY.json',summary)
save('FINAL_SOURCE_HASHES.json',dict(**json.loads((O/'FEATURE_SOURCE_HASHES.json').read_text()),**{str(lp):sha(lp)}))
print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
