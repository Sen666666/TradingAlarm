"""Source-driven E0 confirmation coordinate; preserve the original 168 rows."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
stem = 'SUPPLEMENT_2025NOV28_SEMI_E0_ANCHOR_21'
fp = ROOT / 'feature_paths' / (stem + '.parquet')
op = ROOT / 'original_eligibility' / (stem + '.parquet')
pp = ROOT.parent / 'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'
f, o = pd.read_parquet(fp), pd.read_parquet(op)
key = ['case_id', 'date', 'sector_id_static']
assert len(f) == len(o) == 21 and not f.duplicated(key).any() and not o.duplicated(key).any()
out = f.merge(o.rename(columns={c: 'orig_' + c for c in o if c not in key}), on=key, validate='one_to_one')
assert out.relative_session.eq(out.orig_relative_session).all()
assert out.industry_static.eq(out.orig_industry_static).all()
assert out.anchor_session.eq(out.orig_anchor_date).all()
p = pd.read_parquet(pp).sort_values(['sector_id_static', 'date'])
g = p.groupby('sector_id_static', sort=False)
p['a_own'] = p.B_now - 2*p.B_lag5_ownU + g.B_lag5_ownU.shift(5)
p['a_pair'] = p.dB5_paired - g.dB5_paired.shift(5)
out = out.merge(p[['date', 'sector_id_static', 'a_own', 'a_pair', 'share5', 'share20', 'share_change_diagnostic']],
                on=['date', 'sector_id_static'], validate='one_to_one')
out['price_r1_over_prior63_s'] = out.index_r1_log / out.orig_CP__s
out['post_hoc_source_driven_supplement'] = True
out['stock_I_and_cohort_amount_aggregation_status'] = 'NOT_EXTRACTED_IN_THIS_SUPPLEMENT_NOT_ZERO'
cols = ['case_id','anchor_session','relative_session','date','industry_static','sector_id_static',
        'index_close','index_r1_log','price_r1_over_prior63_s','newhigh20','crossup20','newhigh60','crossup60',
        'Rp','p_Rp','B_now','p_B','rs_ind5','p_R5','dB5_paired','p_dB5','a_own','a_pair',
        'share5','share20','share_change_diagnostic','P_score','P_order','P_mature','P_state_mechanical_fact',
        'possible_states_before','possible_states_after','T_score','T_order','T_selected',
        'P_gap_contribution_p_Rp','P_gap_contribution_p_B','P_gap_vs_cutoff',
        'T_gap_contribution_p_R5','T_gap_contribution_p_dB5','T_gap_vs_cutoff',
        'original_H1_score','original_H1_order','orig_native_E0__e0_target',
        'orig_upstream_events__entered','orig_upstream_events__event',
        'orig_last_confirmed_low_confirmation_date','orig_last_confirmed_low_pivot_date','orig_last_confirmed_low_price_a',
        'orig_market_state__stage_name','orig_market_state__authorization_usable','orig_CP__receipt',
        'orig_industry_I_permission','post_hoc_source_driven_supplement',
        'stock_I_and_cohort_amount_aggregation_status','earliest_possible_action_session']
assert all(c in out for c in cols)
out[cols].to_csv(ROOT / 'SUPPLEMENT_E0_STRUCTURAL_ANCHOR_21.csv', index=False, encoding='utf-8-sig')
out.to_parquet(ROOT / 'SUPPLEMENT_E0_STRUCTURAL_ANCHOR_21.parquet', index=False)
audit = {'rows':len(out),'unique_keys':not out.duplicated(key).any(),'key':key,
         'primary_168_unchanged':True,'post_hoc_source_driven_not_blind':True,
         'no_new_stock_amount_or_account_read':True,
         'sources':{str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest() for x in [fp,op,pp]}}
(ROOT/'SUPPLEMENT_JOIN_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(out.loc[out.relative_session.eq(0),['date','P_order','T_order','a_own','a_pair',
                 'share_change_diagnostic','orig_native_E0__e0_target','orig_upstream_events__entered',
                 'orig_market_state__stage_name']].to_dict('records'),ensure_ascii=False,indent=2))
