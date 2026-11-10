"""Synthetic contracts, no historical outcomes or account operations."""
from pathlib import Path
import sys,json
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import experiment as e
n=220;idx=pd.bdate_range('2020-01-01',periods=n);t=np.arange(n)
p=pd.DataFrame(index=idx);p['close']=10+.005*t+.1*np.sin(t);p['open']=p.close;p['high']=20.;p['low']=5.
for k in ['open','high','low','close']:p['raw_'+k]=p[k]
p['raw_volume']=1000.+200*np.sin(t/3)+t;p['amount']=10*p.raw_volume;p['volume_factor']=1.;p['adjustment_factor']=1.
p['volume_unit']='shares';p['amount_unit']='CNY';p['source_kind']='fixture';p['source_path']='fixture.parquet';p['segment_id']=0
for k in ['price_eligible','volume_eligible','observed_bar','is_observed_bar']:p[k]=True
for k in ['source_invalid','synthetic_event_bar']:p[k]=False
z=e.calc(p);checks=[]
assert z.feature_known.iloc[84:].all() and not z.feature_known.iloc[:84].any();checks.append('exact85_price_observation_warmup')
assert (z.score_shares-z.native_PVR).abs().max()<1e-12;checks.append('constant_mean_price_A_equals_constant_times_V_reduces_to_original')
q=p.copy();q.loc[idx[120]:,'volume_factor']=2;zz=e.calc(q)
assert not zz.feature_known.iloc[120:161].any() and zz.feature_known.iloc[161:].all()
pd.testing.assert_series_equal(zz.u,z.u);checks.append('factor_change_requires42_new_consistent_volume_observations_preserves_u')
q=p.copy();q.loc[idx[120],'volume_eligible']=False;zz=e.calc(q)
assert not zz.feature_known.iloc[120:162].any() and zz.feature_known.iloc[162:].all()
pd.testing.assert_series_equal(zz.u,z.u);checks.append('one_invalid_volume_influences42_outputs_preserves_u')
q=p.copy();q.loc[idx[120],'amount_unit']='unknown';zz=e.calc(q)
assert not zz.feature_known.iloc[120:162].any() and zz.feature_known.iloc[162:].all();checks.append('unit_unknown_kept_unknown_for_full42_support')
q=p.copy();q.loc[idx[120]:,'source_kind']='new_source';zz=e.calc(q)
assert not zz.feature_known.iloc[120:204].any() and zz.feature_known.iloc[204:].all();checks.append('source_change_requires85_consistent_price_observations')
zz=e.calc(p.iloc[:137]);pd.testing.assert_frame_equal(zz,z.iloc[:137],check_exact=True);checks.append('physical_prefix_exact')
q=p.copy();q.raw_volume*=10;q.amount*=10;zz=e.calc(q)
np.testing.assert_allclose(zz.score_shares,z.score_shares,rtol=0,atol=1e-12,equal_nan=True);checks.append('constant_scale_invariance')
e.save('SYNTHETIC_QA.json',dict(status='PASS',checks=checks,code_hash=e.sha(__file__),experiment_hash=e.sha(O/'experiment.py')))
print('SYNTHETIC_PASS',len(checks))
