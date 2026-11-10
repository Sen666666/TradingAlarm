"""Independent read-only join audit. Does not load or run an economic engine."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csv(n):return pd.read_csv(O/n,float_precision='round_trip',low_memory=False)
names=['cash_unique_same_exit_decomposition.csv','EXANTE_ALL_ACTUAL_ROUNDS.csv','EXANTE_ALL_SAME_EXIT_PAIRS.csv','EXANTE_SAME_EXIT_TIMING_SUMMARY.csv','exante_pair_join.py']
before={n:sha(O/n) for n in names}
qa=json.loads((O/'EXANTE_PAIR_QA.json').read_text())
for n,h in qa['source_hashes'].items():assert sha(n)==h
p=csv(names[0]);z=csv(names[1]).set_index('round_id');a=csv(names[2]);s=csv(names[3]);assert z.index.is_unique
keys=['window','comparison','c_round_id','r_round_id']
assert not a.duplicated(keys).any() and len(a)==len(p)==1168
pd.testing.assert_frame_equal(a[p.columns].sort_values(keys).reset_index(drop=True),p.sort_values(keys).reset_index(drop=True),check_exact=False,rtol=1e-12,atol=1e-8)
features=['RM','RAW_MOM11','RAW_EXCESS_STANDARDIZED','beta_market','beta_size','beta_value','raw_vol36','raw_vol11','residual_sd','industry_beta36','normalization_component','alpha_component','market_component','size_component','value_component']
for row in a.itertuples():
    c=z.loc[row.c_round_id];r=z.loc[row.r_round_id]
    assert c.sid==r.sid==row.sid and c.exit_day==r.exit_day==row.exit_day
    assert c.event_id==row.c_event_id and r.event_id==row.r_event_id
    assert c.signal_day==row.c_signal_day and r.signal_day==row.r_signal_day
    assert c.entry_day==row.c_entry_day and r.entry_day==row.r_entry_day
    assert c.signal_day<c.entry_day and r.signal_day<r.entry_day
    assert row.same_signal_month==(c.signal_day[:7]==r.signal_day[:7])
    timing='CH3_EARLIER' if c.entry_day<r.entry_day else 'CH3_LATER' if c.entry_day>r.entry_day else 'SAME_ENTRY_DAY'
    assert row.entry_timing==timing
    assert row.both_features_known==(c.status_feature==r.status_feature=='CALENDAR_COMPUTABLE_RELEASE_UNKNOWN')
    for f in features:
        assert np.isclose(getattr(row,'c_'+f),c[f],rtol=1e-12,atol=1e-12,equal_nan=True)
        assert np.isclose(getattr(row,'r_'+f),r[f],rtol=1e-12,atol=1e-12,equal_nan=True)
        assert np.isclose(getattr(row,'delta_'+f),c[f]-r[f],rtol=1e-12,atol=1e-12,equal_nan=True)
        if row.same_signal_month:assert np.isclose(c[f],r[f],rtol=1e-12,atol=1e-12,equal_nan=True)
groups=['window','comparison','same_signal_month','entry_timing']
assert len(s)==a.groupby(groups).ngroups
for row in s.itertuples():
    mask=np.ones(len(a),dtype=bool)
    for f in groups:mask &=a[f].eq(getattr(row,f))
    g=a[mask];assert row.pairs==len(g) and row.both_features_known==g.both_features_known.sum()
    for field,source,agg in [('core_net_delta','core_delta_net','sum'),('quantity_component','core_quantity_component','sum'),('per_share_component','core_per_share_component','sum'),('mean_core_return_delta','core_delta_return','mean')]:
        assert np.isclose(getattr(row,field),getattr(g[source],agg)(),rtol=1e-12,atol=1e-8,equal_nan=True)
    for f in features:assert np.isclose(getattr(row,'mean_delta_'+f),g['delta_'+f].mean(),rtol=1e-12,atol=1e-12,equal_nan=True)
primary=a[a.comparison.eq('CH3_RM_MINUS_RAW_MOM11')]
summary={str(w):dict(pairs=len(g),same_signal_month=int(g.same_signal_month.sum()),same_month_all_monthly_features_identical=True,known_pairs=int(g.both_features_known.sum())) for w,g in primary.groupby('window')}
for n,h in before.items():assert sha(O/n)==h
out=dict(status='PASS_READ_ONLY_PAIR_FEATURE_AUDIT',pairs=len(a),same_month_pairs=int(a.same_signal_month.sum()),all_pair_identity_dates_and_preentry_clock_exact=True,all_source_columns_unchanged=True,all_15_feature_joins_and_deltas_verified=True,all_summary_groups_verified=len(s),primary_comparison=summary,new_economic_runs=0,source_hashes=before,limitations=['Matching on realized exits is post-outcome descriptive selection, not a pre-entry implementable filter.','Same-month own-stock features can be identical while dynamic eligibility and queue history produce different entry dates and quantities.','No causal beta-neutrality or out-of-sample gain is established.'])
(O/'INDEPENDENT_PAIR_FEATURE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
