"""Join fixed-window evidence by canonical case/date/sector; no new signal."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
KEY = ['case_id', 'date', 'sector_id_static']
sources = {}
def read(name):
    p = ROOT / name
    sources[str(p.resolve())] = hashlib.sha256(p.read_bytes()).hexdigest()
    f = pd.read_parquet(p)
    assert f.columns.is_unique
    return f
f = pd.concat([read('feature_paths/CAUSAL_FEATURE_PATHS.parquet'),
               read('feature_paths/COUNTEREXAMPLE_EXISTING_FEATURE_PATHS.parquet')], ignore_index=True)
raw = read('burst_raw/RAW_PATHS_COMPLETE.parquet')
orig = read('original_eligibility/ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS.parquet')
stocks = read('original_eligibility/ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES.parquet')
mp = ROOT / 'burst_raw/CASE_ID_MAPPING.csv'
sources[str(mp.resolve())] = hashlib.sha256(mp.read_bytes()).hexdigest()
mapping = pd.read_csv(mp).set_index('burst_raw_case_id').feature_paths_case_id.to_dict()
raw['burst_case_id_original'] = raw.case_id
raw['case_id'] = raw.case_id.map(mapping)
assert raw.case_id.notna().all()
for name, g in [('feature', f), ('raw', raw), ('original', orig), ('stocks', stocks)]:
    assert len(g) == 168 and not g.duplicated(KEY).any(), name
    assert set(map(tuple, g[KEY].to_numpy())) == set(map(tuple, f[KEY].to_numpy())), name
    assert g.groupby('case_id').size().eq(21).all(), name

out = f.copy()
for prefix, g in [('raw_', raw), ('orig_', orig), ('stocks_', stocks)]:
    h = g.rename(columns={c: prefix + c for c in g.columns if c not in KEY})
    out = out.merge(h, on=KEY, validate='one_to_one')
    assert out.relative_session.eq(out[prefix + 'relative_session']).all()
    assert out.industry_static.eq(out[prefix + 'industry_static']).all()
assert out.anchor_session.eq(out.raw_event_anchor).all()
assert out.anchor_session.eq(out.orig_anchor_date).all()
assert out.anchor_session.eq(out.stocks_anchor_date).all()
for name in ['N_U_t', 'Nstatic', 'N_above20_t', 'N_above20_tminus5', 'B_now', 'dB5_paired', 'rs_ind5']:
    np.testing.assert_allclose(out[name], out['raw_' + name], rtol=0, atol=1e-12, equal_nan=True)
assert out.N_U_t.eq(out.stocks_U_N_from_saved_industry_aggregate).all()
for name in ['index_close', 'index_r1_log', 'prior20_high_close', 'prior60_high_close',
             'distance_to_prior20_high_log', 'distance_to_prior60_high_log',
             'newhigh20', 'newhigh60', 'crossup20', 'crossup60', 'index_segment_id']:
    if name in out:
        known = out[name].notna()
        if known.any():
            np.testing.assert_allclose(out.loc[known, name].astype(float), out.loc[known, 'raw_' + name].astype(float),
                                       rtol=0, atol=1e-12, equal_nan=True)
        out[name] = out[name].where(known, out['raw_' + name])
    else:
        out[name] = out['raw_' + name]
out = out.sort_values(['case_id', 'date']).reset_index(drop=True)
out.to_parquet(ROOT / 'ALL_JOINED_EVIDENCE.parquet', index=False)

def export(name, fields):
    assert len(fields) == len(set(fields))
    assert all(c in out for c in fields), [c for c in fields if c not in out]
    out[fields].to_csv(ROOT / name, index=False, encoding='utf-8-sig')
base = ['case_id', 'case_role', 'anchor_session', 'relative_session', 'date', 'sector_id_static', 'industry_static']
export('DAILY_CAUSAL_TABLE.csv', base + [
    'index_close', 'index_r1_log', 'prior20_high_close', 'newhigh20', 'crossup20',
    'prior60_high_close', 'newhigh60', 'crossup60', 'Rp', 'p_Rp', 'B_now', 'p_B',
    'rs_ind5', 'p_R5', 'dB5_paired', 'p_dB5', 'P_score', 'P_order', 'P_mature',
    'P_state_mechanical_fact', 'possible_states_before', 'possible_states_after',
    'T_score', 'T_order', 'T_selected', 'original_H1_score', 'original_H1_order',
    'orig_native_E0__e0_target', 'orig_market_state__stage_name', 'orig_market_state__authorization_usable',
    'orig_CP__receipt', 'orig_industry_I_permission', 'Nstatic', 'N_U_t',
    'stocks_U_i_target_known_N', 'stocks_U_i_target_true_N', 'stocks_U_i_target_unknown_N',
    'stocks_U_i_buy_original_daily_event_true_N', 'stocks_U_i_buy_exact_field_unknown_N',
    'earliest_possible_action_session'])
export('DAILY_SCORE_CUTOFF_GAPS.csv', base + [
    'P_order', 'P_score', 'P_mature', 'P_state_mechanical_fact', 'N_U_t', 'N_above20_t', 'N_above20_tminus5',
    'P_cutoff_industry', 'P_cutoff_N_U_t', 'P_cutoff_N_above20_t', 'P_cutoff_N_above20_tminus5',
    'P_cutoff_P_score', 'P_gap_contribution_p_Rp', 'P_gap_contribution_p_B', 'P_gap_vs_cutoff',
    'T_order', 'T_score', 'T_selected', 'T_cutoff_industry', 'T_cutoff_N_U_t',
    'T_cutoff_N_above20_t', 'T_cutoff_N_above20_tminus5', 'T_cutoff_T_score',
    'T_gap_contribution_p_R5', 'T_gap_contribution_p_dB5', 'T_gap_vs_cutoff'])
export('DAILY_BURST_RAW_AND_COUNTEREXAMPLES.csv', base + [
    'Nstatic', 'N_U_t', 'N_above20_t', 'N_above20_tminus5', 'B_now', 'dB5_paired',
    'raw_a_own_raw', 'raw_a_pair_raw', 'raw_Bmarket_subpool', 'raw_Bmarket_change5', 'raw_Bmarket_a_own',
    'raw_share5', 'raw_share20', 'raw_share_change_diagnostic', 'raw_log_share5_over_share20_raw',
    'raw_sector_amount_CNY_T_sameTcohort', 'raw_sector_prior21_daily_aggregate_median_CNY_sameTcohort',
    'raw_sector_amount_ratio21_sameTcohort', 'raw_pool_amount_CNY_T_sameTcohort',
    'raw_pool_prior21_daily_aggregate_median_CNY_sameTcohort', 'raw_pool_amount_ratio21_sameTcohort',
    'index_r1_log', 'raw_cp_original_s', 'raw_z1_new_r1_over_cp_prior63_s',
    'newhigh20', 'crossup20', 'newhigh60', 'crossup60',
    'orig_native_E0__e0_target', 'orig_market_state__stage_name', 'orig_CP__receipt'])
export('DAILY_ORIGINAL_E0_CP_STRUCTURE.csv', base + [
    'orig_native_E0__e0_target', 'orig_native_E0__e0_floor',
    'orig_last_confirmed_low_confirmation_date', 'orig_last_confirmed_low_pivot_date', 'orig_last_confirmed_low_price_a',
    'orig_last_confirmed_high_confirmation_date', 'orig_last_confirmed_high_pivot_date', 'orig_last_confirmed_high_price_a',
    'orig_CP__anchor', 'orig_CP__frontier', 'orig_CP_frontier_coordinate', 'orig_CP__delta_frontier', 'orig_CP__receipt', 'orig_CP__candidate',
    'orig_market_state__E0_episode', 'orig_market_state__stage_name', 'orig_market_state__authorization_usable',
    'orig_market_state__financial_state_owned', 'orig_industry_I_permission', 'orig_CP_input_i_floor_semantics',
    'stocks_whole_static_sector_N', 'stocks_i_target_known_N', 'stocks_i_target_true_N', 'stocks_i_target_unknown_N',
    'stocks_i_buy_original_daily_event_true_N', 'stocks_i_buy_exact_field_unknown_N',
    'stocks_U_N_from_saved_industry_aggregate', 'stocks_U_i_target_known_N', 'stocks_U_i_target_true_N',
    'stocks_U_i_target_unknown_N', 'stocks_U_i_buy_original_daily_event_true_N'])
main_ids = ['924_SEMI', '924_SOFTWARE', '924_COMMUNICATION', '2026JAN5_SEMI']
reading = pd.read_csv(ROOT / 'DAILY_CAUSAL_TABLE.csv', encoding='utf-8-sig')
reading[reading.case_id.isin(main_ids)].to_csv(ROOT / 'MAIN_84_DAILY_CAUSAL.csv', index=False, encoding='utf-8-sig')
reading[~reading.case_id.isin(main_ids)].to_csv(ROOT / 'AUX_AND_COUNTER_84_DAILY_CAUSAL.csv', index=False, encoding='utf-8-sig')
audit = {'rows': len(out), 'cases': out.case_id.nunique(), 'rows_per_case': out.groupby('case_id').size().to_dict(),
         'unique_date_sector_observations': len(out[['date','sector_id_static']].drop_duplicates()),
         'join_key': KEY, 'case_mapping_explicit': mapping, 'overlap_is_not_independent_sample': True,
         'all_join_sources_one_to_one': True, 'anchors_relative_sessions_and_industries_exact': True,
         'price_and_cached_numeric_overlap_checks_passed': True, 'sources': sources,
         'no_new_gate_or_threshold_or_account': True}
(ROOT / 'JOIN_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in audit.items() if k not in ['sources','case_mapping_explicit']}, ensure_ascii=False, indent=2))
