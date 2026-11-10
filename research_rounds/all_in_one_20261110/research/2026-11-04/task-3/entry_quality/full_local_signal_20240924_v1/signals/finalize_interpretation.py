"""Postprocess saved complete export only; never import/call signal models.

Adds the agreed knowledge guard to explanatory columns, preserving all original
E0/I/G/numeric fields and the unguarded prior helper for audit.
"""
from pathlib import Path
import hashlib,json,datetime
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ORIGINAL_FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
 assert not(HERE/'INTERPRETATION_GUARD.json').exists(),'One postprocess only'
 assert(HERE/'COMPLETION.json').exists()
 path=HERE/'ALL_SIGNALS.parquet';before=pd.read_parquet(path)
 assert len(before)==before.sid.nunique()==5517
 assert before.day.eq('2024-09-24').all()
 ends=before.prefix_end_day.dropna()
 assert ends.le('2024-09-24').all()
 exact_mask=before.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL')
 assert before.loc[exact_mask,'target_source_row_present'].eq(True).all()
 assert before.loc[exact_mask,'prefix_end_day'].eq('2024-09-24').all()
 original=before[ORIGINAL_FIELDS].copy(deep=True)
 f=before.copy()
 freeze=json.loads((HERE/'FREEZE.json').read_text())
 feature_path=HERE.parents[1]/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
 assert sha(feature_path)==freeze['source_feature_sha256']
 feature=pd.read_parquet(feature_path).query("day=='2024-09-24'").set_index('sid')
 exact_ids=f.loc[f.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL'),'sid']
 observed=f.set_index('sid').loc[exact_ids,'close'].to_numpy(float)
 reference=feature.loc[exact_ids,'current_close_qfq'].to_numpy(float)
 assert np.array_equal(observed.view(np.uint64),reference.view(np.uint64))
 missing_ids=set(f.loc[f.signal_status.eq('MISSING_TARGET_BAR'),'sid'])
 expected_missing=set(feature.loc[feature.target_row_present.eq(False)].index)
 assert missing_ids==expected_missing
 save(HERE/'FINAL_PRICE_SOURCE_CHECK.json',dict(exact_signal_close_bitexact_to_saved_same_source_feature_rows=len(exact_ids),
    missing_target_ids_equal_saved_source_observation_metadata=True,missing_target_ids=len(missing_ids),
    all5517_day_fixed=True,all_recorded_prefix_end_not_after_target=True,all_exact_prefix_end_equals_target=True,
    saved_feature_sha256=sha(feature_path),new_models=0))
 f['stock_fresh_core_signal_e0_guard_only_raw']=f.stock_fresh_core_signal
 exact=f.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL')
 e0=exact&f.e0_ready.eq(1)
 g=e0&f.g_ready.eq(True)
 hold=pd.Series(pd.NA,index=f.index,dtype='boolean');fresh=hold.copy()
 hold.loc[e0]=f.loc[e0,'i_target'].eq(1)
 fresh.loc[g]=f.loc[g,'i_target'].eq(1)&f.loc[g,'i_buy'].eq(True)
 f['stock_hold_signal']=hold;f['stock_fresh_core_signal']=fresh
 f['fresh_stock_research']=fresh
 f['fresh_signal_readiness']=np.select([~exact,exact&~f.e0_ready.eq(1),e0&~f.g_ready.eq(True)],
     ['UNKNOWN_SOURCE','UNKNOWN_E0_NOT_READY','UNKNOWN_G_NOT_READY'],default='EXACT_E0_G_READY')
 pd.testing.assert_frame_equal(f[ORIGINAL_FIELDS],original,check_exact=True)
 interpreted=HERE/'ALL_SIGNALS_INTERPRETED.parquet'
 f.to_parquet(interpreted,index=False);f.to_csv(HERE/'ALL_SIGNALS_INTERPRETED.csv',index=False)
 reread=pd.read_parquet(interpreted);pd.testing.assert_frame_equal(reread[ORIGINAL_FIELDS],original,check_exact=True)
 receipt=dict(kind='Explanatory knowledge guard only, no model recomputation',
    raw_model_fields_exact_unchanged=ORIGINAL_FIELDS,original_model_table_sha256=sha(path),
    raw_unguarded_helper='stock_fresh_core_signal_e0_guard_only_raw',
    hold_formula='exact_target AND e0_ready==1: read i_target; otherwise NA',
    fresh_formula='exact_target AND e0_ready==1 AND g_ready==True: read i_target AND i_buy; otherwise NA',
    guarded_fresh_columns=['stock_fresh_core_signal','fresh_stock_research'],
    original_i_buy_unchanged=True,unknown_counts=dict(hold=int(hold.isna().sum()),fresh=int(fresh.isna().sum())),
    known_fresh_true=int(fresh.eq(True).sum()),known_hold_true=int(hold.eq(True).sum()),
    readiness_counts=f.fresh_signal_readiness.value_counts().to_dict(),
    raw_ALL_SIGNALS_and_COMPLETION_not_modified=True,
    interpreted_signals_sha256=sha(interpreted),postprocessor_sha256=sha(__file__),new_models=0,new_accounts=0)
 save(HERE/'INTERPRETATION_GUARD.json',receipt)
 journal=[]
 for p in sorted(HERE.glob('full/*.jsonl')):
  records=[json.loads(x)for x in p.read_text().splitlines()]
  journal.append(dict(path=str(p),sha256=sha(p),records=len(records),symbols=[r['sid']for r in records]))
 save(HERE/'FULL_JOURNAL_INDEX.json',journal)
 print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
