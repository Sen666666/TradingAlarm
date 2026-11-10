"""Final read-only summaries of saved crosses, fixed matches and metadata."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'channel_atr_fsm_v1'))
import engine

def stats(q):
    columns=['warning_MFE20','control_MFE20','warning_MAE20','control_MAE20']
    return dict(n=len(q),means={k:None if not len(q) else float(q[k].mean()) for k in columns},
        warning_first_hit=dict(Counter(q.warning_first_hit)),control_first_hit=dict(Counter(q.control_first_hit)))

def main():
    out=HERE/'metadata_v1'
    meta=pd.read_parquet(out/'REFERENCE_DAY_METADATA.parquet')
    matched=pd.read_parquet(out/'MATCHED_ENDPOINT_AND_RAWLEG_METADATA.parquet')
    cols=['analysis_window','sid','day','first_threshold_cross_in_cycle','active_cross_warning','I_cycle_age',
          'E0_down_in_prior5_complete_observations','E0_down_same_close']
    panel=pd.concat([pd.read_parquet(HERE/f'run_v1/PANEL_{i}.parquet',columns=cols) for i in range(3)],ignore_index=True)
    panel=panel.merge(meta[['analysis_window','sid','day','extra_rawleg_strict_candidate']],on=['analysis_window','sid','day'],validate='1:1')
    result={}
    for window,q in panel.groupby('analysis_window',sort=True):
        first=q.loc[q.active_cross_warning.eq(True)&q.first_threshold_cross_in_cycle.eq(True)]
        extra=q.loc[q.extra_rawleg_strict_candidate.eq(True)]
        selected=matched.loc[matched.analysis_window.eq(window)&matched.warning_strict_extra]
        same=selected.loc[selected.endpoint_status.eq('BOTH_COMPLETE_SAME_ENDPOINT')]
        both_up=same.loc[same.control_rawleg.eq(1)]
        def ages(rows,side):
            joined=rows[['analysis_window','day',side+'_sid']].rename(columns={side+'_sid':'sid'}).merge(
                q[['analysis_window','day','sid','I_cycle_age']],on=['analysis_window','day','sid'],validate='m:1')
            return None if not len(joined) else float(joined.I_cycle_age.mean())
        result[window]=dict(
            first_in_I_active_cross_n_in_saved_reference_days=len(first),
            first_in_I_strict_extra_n=int(first.extra_rawleg_strict_candidate.sum()),
            first_in_I_strict_extra_fraction=None if not len(first) else float(first.extra_rawleg_strict_candidate.mean()),
            strict_extra_total_n=len(extra),strict_extra_same_endpoint_matched_n=len(same),
            strict_extra_same_endpoint_coverage=None if not len(extra) else len(same)/len(extra),
            strict_extra_same_endpoint=stats(same),
            same_endpoint_I_cycle_age_warning=ages(same,'warning'),same_endpoint_I_cycle_age_control=ages(same,'control'),
            diagnostic_existing_pairs_control_also_raw_up=stats(both_up),
            no_rematch_or_model_run=True,
            same_rawleg_subgroup_is_metadata_diagnostic_not_a_new_preregistered_matching_algorithm=True)
    target=out/'FINAL_EXTRA_MATCHED_AND_FIRST_CYCLE.json'
    target.write_text(json.dumps(engine.clean(result),ensure_ascii=False,indent=2,allow_nan=False))
    for k,v in result.items():print(k,json.dumps(engine.clean(v),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
