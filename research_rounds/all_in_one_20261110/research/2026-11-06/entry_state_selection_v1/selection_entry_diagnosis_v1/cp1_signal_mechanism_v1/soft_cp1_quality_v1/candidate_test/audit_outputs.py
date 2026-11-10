from pathlib import Path
import importlib.util,json,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen',O/'run_candidate_test.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
B=mod.B;start=time.monotonic()
inputs=[B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'FIXED_NATIVE_PRICE_LABELS.parquet',B/'SEALED_SAME_K_SELECTIONS.parquet',B/'ROOT_EPISODE_COVERAGE.csv',O/'CANDIDATE_Q.parquet',O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',O/'SELECTED_WITH_FIXED_LABELS.parquet',O/'FULL_QUEUE_ORDERS.parquet',O/'ROOT_EPISODES.csv',O/'run_candidate_test.py',Path(__file__)]
hashes={str(p):mod.sha(p) for p in inputs}
seal=json.loads((O/'RANK_SEAL.json').read_text());assert seal['selections_sha256']==mod.sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet');assert seal['score_sha256']==mod.sha(O/'CANDIDATE_Q.parquet')
sc=pd.read_parquet(O/'CANDIDATE_Q.parquet');sel=pd.read_parquet(O/'SELECTED_WITH_FIXED_LABELS.parquet');sealed=pd.read_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet');labels=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet')
assert len(sc)==103766 and len(sel)==len(sealed)==55980
key=['account','day','strategy','selected_rank','sid']
pd.testing.assert_frame_equal(sel[key].sort_values(key).reset_index(drop=True),sealed[key].sort_values(key).reset_index(drop=True))
old=pd.read_parquet(B/'SEALED_SAME_K_SELECTIONS.parquet');old=old[old.strategy=='ORIGINAL_PVR'];cols=['account','day','selected_rank','sid','CP1_id']
pd.testing.assert_frame_equal(sealed[sealed.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True),old[cols].sort_values(cols[:3]).reset_index(drop=True),check_dtype=False)
ep=pd.read_csv(O/'ROOT_EPISODES.csv',keep_default_na=False);olde=pd.read_csv(B/'ROOT_EPISODE_COVERAGE.csv',keep_default_na=False);ek=['account','sid','epoch'];cols=ek+['birth_day','year','complete60','big60','candidate_events','early_candidate_events','ORIGINAL_PVR_early_capture']
pd.testing.assert_frame_equal(ep[cols].sort_values(ek).reset_index(drop=True),olde[cols].sort_values(ek).reset_index(drop=True),check_dtype=False)
assert sel.groupby(['account','day','strategy']).size().unstack().nunique(axis=1).eq(1).all()
mov=pd.read_parquet(O/'FULL_QUEUE_ORDERS.parquet');expected={(a,d):g.sort_values('Q_rank').sid.tolist() for (a,d),g in mov.groupby(['account','day'])}
poison=sc.merge(labels,on=['sid','day'],validate='many_to_one')
for col in labels.columns:
 if col not in ['sid','day']:poison[col]=-999999 if pd.api.types.is_numeric_dtype(poison[col]) else 'POISON'
for (a,d),g in poison.groupby(['account','day']):
 base,alt=mod.orders(g);assert g.loc[alt,'sid'].tolist()==expected[(a,d)]
 # Unreplaceable source-score slots must remain exact, not merely top-K membership.
 pos={i:j for j,i in enumerate(alt)}
 assert all(pos[i]==j for j,i in enumerate(base) if not g.at[i,'slot_replaceable'])
queue=pd.read_csv(O/'QUEUE_COUNTS.csv');cases=pd.read_csv(O.parent/'SIGNAL_SUMMARY.csv').rename(columns={'signal_day':'day'})
cart=pd.concat([cases[['sid','day','case_kind','original_round_pnl']].assign(account=a) for a in ['PVR','E31']],ignore_index=True)
case=cart.merge(mov,on=['account','day','sid'],how='left',validate='one_to_one').merge(queue[['account','day','N']],on=['account','day'],how='left',validate='many_to_one')
case['in_original_candidate_domain']=case.original_rank.notna()
case['effect']=np.where(~case.in_original_candidate_domain,'not_in_this_account_original_domain',np.where(case.original_selected & ~case.Q_selected,'removed',np.where(~case.original_selected & case.Q_selected,'added',np.where(case.Q_selected,'both_selected','neither_selected'))))
case.to_csv(O/'FIXED_CASE_QUEUE_EFFECTS.csv',index=False)
ue=[]
for (a,y),g in ep.groupby(['account','year']):
 z=g[g.epoch.eq('None')];b=z[z.big60]
 ue.append(dict(account=a,year=int(y),missing_epoch_roots=len(z),complete60=int(z.complete60.sum()),big60=len(b),base_captured=int(b.ORIGINAL_PVR_early_capture.sum()),Q_captured=int(b.CONTINUOUS_Q_early_capture.sum()),lost=int(b.lost.sum()),added=int(b.added.sum())))
pd.DataFrame(ue).to_csv(O/'UNKNOWN_EPOCH_ROOT_DIAGNOSTIC.csv',index=False)
# All summary files use the same sealed membership. No decision can use these post-hoc checks.
assert all(mod.sha(p)==h for p,h in hashes.items())
coverage=json.loads((O/'SCORE_COVERAGE.json').read_text())
summary=dict(status='COMPLETED_FROZEN_Q_OFFLINE_CANDIDATE_TEST_NOT_ACCOUNT_NOT_OOS',candidate_rows=len(sc),selected_per_strategy=len(sel)//2,baseline_exact_match=True,roots_exact_original_match=True,future_label_mutation_all_queues_unchanged=True,poisoned_queues=len(expected),all_equal_K=True,unknown_slots_unchanged=True,full_cache_prefix_checks=coverage['prefix_checks'],Q_unknown=coverage['unknown'],original_PVR_unknown=coverage['original_PVR_unknown'],short_warm=coverage['finite_short_warm'],unknown_epoch_candidates=int(sc.epoch.eq('None').sum()),unknown_epoch_roots=int(ep.epoch.eq('None').sum()),account_runs=0,original_indicator_runs=0,parameter_scans=0,ranking_experiment_passes=1,finish_checks_seconds=time.monotonic()-start,source_unchanged=True)
(O/'EVALUATION_SOURCE_HASHES.json').write_text(json.dumps(hashes,indent=2));(O/'SUMMARY.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary));print(case[['account','sid','day','N','K','original_rank','Q_rank','original_selected','Q_selected','effect']].to_string(index=False))
