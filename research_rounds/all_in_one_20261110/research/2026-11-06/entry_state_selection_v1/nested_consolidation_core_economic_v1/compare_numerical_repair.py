from pathlib import Path
import pandas as pd,numpy as np,json
O=Path(__file__).resolve().parent;A=O/'BEFORE_NATIVE_COORDINATE_REPAIR'
def read(p):return pd.read_csv(p,float_precision='round_trip')
def different(a,b):return not ((pd.isna(a) and pd.isna(b)) or a==b)
a=read(A/'ROUNDS.csv');b=read(O/'ROUNDS.csv');key=['sid','window','arm','birth_day'];a=a.set_index(key).sort_index();b=b.set_index(key).sort_index();assert a.index.equals(b.index)
changes=[]
for idx in a.index:
 delta={c:{'before':a.loc[idx,c],'after':b.loc[idx,c]} for c in a.columns if different(a.loc[idx,c],b.loc[idx,c])}
 if delta:changes.append(dict(zip(key,idx))|{'changes':delta})
assert len(changes)==4
assert all(x['sid'] in ['002174.SZ','600606.SH'] and x['arm'] in ['CONTROL','UNION'] for x in changes)
invariants=['origin','birth_S','birth_C','old20_U','local_U','incremental_early','accepted','status','quantity','entry_price','entry_day','entry_fee','planned_risk','outcome','unknown_day']
assert all(not any(c in x['changes'] for c in invariants) for x in changes)
f=read(A/'DAILY_SIGNALS.csv');g=read(O/'DAILY_SIGNALS.csv');pd.testing.assert_frame_equal(f,g[f.columns],check_exact=True)
c=read(A/'CASE_MECHANISM_ROUNDS.csv');d=read(O/'CASE_MECHANISM_ROUNDS.csv');pd.testing.assert_frame_equal(c,d[c.columns],check_exact=True)
p=read(O/'DAILY_ROOT_PATHS.csv');assert (p.failed==(p.native_close<=p.old_S_native)).all()
oldp=read(A/'DAILY_ROOT_PATHS.csv');pk=['sid','window','arm','root_day','day'];beforekeys=set(map(tuple,oldp[pk].to_numpy()));afterkeys=set(map(tuple,p[pk].to_numpy()));removed=[dict(zip(pk,x)) for x in sorted(beforekeys-afterkeys)];added=[dict(zip(pk,x)) for x in sorted(afterkeys-beforekeys)]
q=read(O/'PAIRED_STOCK_DIFFERENCES_STRICT_COVERAGE.csv');oq=read(A/'PAIRED_STOCK_DIFFERENCES_STRICT_COVERAGE.csv');assert np.allclose(q.UNION_strict_pair_net_diff,oq.UNION_strict_pair_net_diff,equal_nan=True,rtol=1e-12,atol=1e-9)
report=dict(change_count=len(changes),changed_rounds=changes,removed_path_rows=removed,added_path_rows=added,births_entries_quantities_labels_unchanged=True,all_original_feature_columns_exactly_unchanged=True,case_rounds_exactly_unchanged=True,native_close_comparison_verified_for_every_path_row=True,strict_paired_union_control_differences_unchanged=True,mechanism='No epsilon or parameter change. Native S was already authoritative in source. Removed erroneous division-to-raw float before structural comparisons.')
(O/'NUMERICAL_REPAIR_DIFF.json').write_text(json.dumps(report,indent=2,default=str)+'\n');print(json.dumps(report,indent=2,default=str))
