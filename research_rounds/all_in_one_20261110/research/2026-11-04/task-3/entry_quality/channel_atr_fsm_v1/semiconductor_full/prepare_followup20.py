"""Data-availability bound for fixed raw CP anchors, not a protection simulation."""
from pathlib import Path
import json,hashlib,csv
import pandas as pd
O=Path(__file__).resolve().parent
idx=json.loads((O/'COVERAGE126_INPUT_INDEX.json').read_text());rows=[]
for r in idx:
 if r['status']!='SOURCE_COMPLETE_COVERAGE_CHECKED':continue
 p=pd.read_parquet(r['source_paths']['price']).loc[:'2026-06-30'];cp=pd.read_parquet(r['source_paths']['CP1']).loc['2025-01-01':'2026-06-30']
 valid=(p.high.notna()&p.low.notna()&p.close.notna()&p.high.gt(0)&p.low.gt(0)&p.close.gt(0)&p.price_eligible.eq(True)&p.observed_bar.eq(True)&p.synthetic_event_bar.eq(False)&p.source_invalid.eq(False)&p.high.ge(p.low)&p.high.ge(p.close)&p.close.ge(p.low))
 vv=p.loc[valid]
 for t,c in cp.loc[cp.receipt.eq(True)].iterrows():
  f=vv.loc[vv.index>t];n=len(f)
  rows.append(dict(sid=r['sid'],anchor_day=str(t.date()),available_following_real_observations=n,has_20th_real_observation=n>=20,twentieth_observation_day=None if n<20 else str(f.index[19].date()),has_observation_after_20=n>20,first_following_observation_day=None if n==0 else str(f.index[0].date()),source_last_at_fixed_cutoff=r['full_price_last_by_cutoff'],scope='Coverage-only availability; no entry/protection/survival/price feasibility inferred.'))
assert len(rows)==2901
summary=dict(status='DATA_AVAILABILITY_BOUND_ONLY',raw_CP_anchors=len(rows),has_20th=sum(r['has_20th_real_observation'] for r in rows),fewer_than20=sum(not r['has_20th_real_observation'] for r in rows),exactly20=sum(r['available_following_real_observations']==20 for r in rows),has_after20=sum(r['has_observation_after_20'] for r in rows),no_following_observation=sum(r['available_following_real_observations']==0 for r in rows),not_eligible_survival_denominator='Entry validity and either policy survival are not modeled; these are upper bounds only.',source_index_sha256=hashlib.sha256((O/'COVERAGE126_INPUT_INDEX.json').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),new_FSM_or_protection_runs=0,new_accounts=0,new_quantities=0,new_returns=0)
(O/'RAW_CP_FOLLOWUP20_AVAILABILITY.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');(O/'FOLLOWUP20_AVAILABILITY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (O/'RAW_CP_FOLLOWUP20_AVAILABILITY.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False))
