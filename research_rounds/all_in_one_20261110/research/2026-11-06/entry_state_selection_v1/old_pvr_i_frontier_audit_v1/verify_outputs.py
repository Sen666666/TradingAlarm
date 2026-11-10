"""Second independent, vectorized read-only classification / sum checks."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
f=pd.read_csv(O/'ALL_PVR_ROUNDS.csv');g=pd.read_csv(O/'GROUPED_OUTCOMES.csv');s=json.load(open(O/'SOURCE_SHA256.json'));checked=0
for p,row in s.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==row['sha256'],p;checked+=1
sources=pd.read_csv(O/'ORIGINAL_SOURCE_QA.csv').set_index('sid');vb=[]
for sid,z in f.groupby('sid'):
 q=pd.read_parquet(sources.at[sid,'facts_path']).loc[:'2026-05-15'];c=pd.read_parquet(sources.at[sid,'CP1_path']).reindex(q.index)
 on=q.i_target.gt(0);start=on&(~on.shift(fill_value=False)|q.segment_id.ne(q.segment_id.shift()));gp=start.cumsum();known_start=q.i_target.shift().eq(0)&q.segment_id.eq(q.segment_id.shift());known=known_start.where(start).ffill().fillna(False).astype(bool)&on
 ib=q.i_buy.fillna(False).astype(int).where(on,0).groupby(gp).cumsum();cp=c.receipt.fillna(False).astype(int).where(on,0).groupby(gp).cumsum()
 ds=pd.DatetimeIndex(z.signal_day);assert on.reindex(ds).all();assert known.reindex(ds).all();assert np.array_equal(ib.reindex(ds).to_numpy(),z.market_i_buy_ordinal.to_numpy());assert np.array_equal(cp.reindex(ds).to_numpy(),z.market_cp_ordinal.to_numpy());assert c.ready.reindex(ds).all()
 vb.append(dict(sid=sid,rounds=len(z),I_cp_ordinal_vectorized_exact=True,cp_ready_at_all_entries=True))
expected=f.sort_values(['entry_at','first_layer']).groupby('i_key').cumcount()+1
assert np.array_equal(expected.sort_index().to_numpy(),f.actual_round_ordinal_in_i.to_numpy())
for window,z in g.groupby('window'):
 allrow=z[z.dimension.eq('ALL')].iloc[0]
 for dimension,h in z[~z.dimension.eq('ALL')].groupby('dimension'):
  assert h.n.sum()==allrow.n,(window,dimension,'n');assert h.closed_n.sum()==allrow.closed_n;assert abs(h.closed_proxy_pnl_cny.sum()-allrow.closed_proxy_pnl_cny)<1e-7,(window,dimension,'pnl')
quality=[]
for name,lo,hi in [('2022_full','2022-01-01','2022-12-31'),('2024_full','2024-01-01','2024-12-31'),('2024_Sep_Dec','2024-09-01','2024-12-31')]:
 z=f[f.entry_day.between(lo,hi)]
 for flag in [False,True]:
  h=z[z.held_source_absent_days.gt(0).eq(flag)]
  quality.append(dict(window=name,original_held_facts_have_gap=flag,n=len(h),closed_n=h.closed.sum(),closed_proxy_pnl_cny=h.loc[h.closed,'round_pnl'].sum(),signal_source_unknown_n=h.market_i_buy_class.eq('UNKNOWN').sum(),financial_NET80_certified_n=0,held_fact_gap_is_not_proof_of_unknown_ledger_mark=True))
pd.DataFrame(quality).to_csv(O/'QUALITY_BUCKETS.csv',index=False)
pd.DataFrame(vb).to_csv(O/'VECTORIZED_SIGNAL_QA.csv',index=False)
r=dict(status='PASS_SECOND_INDEPENDENT_CLASSIFICATION_AND_SUM_REVIEW',source_hashes_rechecked=checked,all_source_bytes_unchanged=True,all_2693_I_and_CP_ordinals_vectorized_exact=True,actual_round_ordinals_exact=True,all_entry_CP_ready=True,all_group_partitions_reconcile=True,first_reason_counts=f.first_reason.value_counts().to_dict(),split_layer_allocation_rows=15,actual_split_events=14,warning='SUMMARY_QA split_events=15 means layer allocation rows; actual distinct split events are 14. All financial_status values intentionally remain OLD_PROXY_ONLY_NOT_NET80_CERTIFIED.')
with (O/'SECOND_PASS_QA.json').open('x')as h:json.dump(r,h,ensure_ascii=False,indent=2)
with (O/'FINAL_OUTPUT_SHA256.json').open('x')as h:json.dump({p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()},h,indent=2)
print(json.dumps(r,ensure_ascii=False));print(pd.DataFrame(quality).to_string(index=False));print(f[(f.entry_day>='2024-09-01')&(f.entry_day<='2024-12-31')&(f.actual_round_ordinal_in_i>1)][['sid','signal_day','entry_day','i_start_day','market_i_buy_ordinal','market_cp_ordinal','actual_round_ordinal_in_i','first_kind','first_reason','closed_day','round_pnl','previous_round_closed_day']].head(6).to_string(index=False))
