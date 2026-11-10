from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=pd.read_csv(O/'ALL_ORIGINAL_ROUNDS_FEATURE_SUPPORT.csv');s=pd.read_csv(O/'ALTERNATIVE_SUPPORT_NO_FIT.csv');cal=pd.read_csv(R/'selection_entry_diagnosis_v1/entry_probability_signal_v1/MARKET_CLOCK.csv',index_col=0,parse_dates=True).index
rows=[]
for H in [120,240]:
 x=a[a.signal_day.ge('2023-01-01')].copy();x['month']=x.signal_day.str[:7];x=x.merge(s[s.H.eq(H)][['month','binary_fit_possible']],on='month',validate='many_to_one');x['signal_year']=x.signal_day.str[:4].astype(int);x['matureH']=x.entry_t+H-1<len(cal);x['closedH']=x.closed&x.close_t.lt(x.entry_t+H);x['W_H']=x.closedH&x.round_pnl.gt(0)
 for year,g in x.groupby('signal_year'):
  good=g.known_for_fit&g.binary_fit_possible;mat=g.matureH
  rows.append(dict(H=H,signal_year=year,births=len(g),feature_known=int(g.known_for_fit.sum()),scorable_if_fitted=int(good.sum()),all_mature=int(mat.sum()),feature_known_mature=int((mat&g.known_for_fit).sum()),eligible_evaluation=int((good&mat).sum()),evaluation_W=int((good&mat&g.W_H).sum()),evaluation_L=int((good&mat&g.closedH&~g.W_H).sum()),evaluation_U=int((good&mat&~g.closedH).sum()),earliest=g.loc[good&mat,'signal_day'].min(),latest=g.loc[good&mat,'signal_day'].max()))
pd.DataFrame(rows).to_csv(O/'ALTERNATIVE_SIGNAL_YEAR_COVERAGE.csv',index=False)
q=pd.read_parquet(R/'cmf_pvr_component_v1/FEATURES.parquet')[['sid','day','CMF21']];z=a.merge(q,left_on=['sid','signal_day'],right_on=['sid','day'],how='inner',validate='one_to_one');assert np.allclose(z.C,z.CMF21,equal_nan=True,atol=1e-14,rtol=0)
for role,g in a.groupby('first_kind'):
 print('ROLE_UNKNOWN',role,g[~g.feature_known].unknown_reason.value_counts().to_dict())
period=[]
for label,lo,hi in [('924','2024-09-19','2024-10-08'),('2026Q1','2026-01-01','2026-03-31')]:
 g=a[a.signal_day.between(lo,hi)]
 period.append(dict(period=label,births=len(g),joint_feature_root_known=int(g.known_for_fit.sum()),mature120=int((g.entry_t+119<len(cal)).sum()),mature240=int((g.entry_t+239<len(cal)).sum()),closed_by_source_end=int(g.closed.sum()),closed_positive_by_source_end=int((g.closed&g.round_pnl.gt(0)).sum()),NO_MODEL_FIT=True))
pd.DataFrame(period).to_csv(O/'FIXED_PERIOD_SUPPORT.csv',index=False)
extra=[R/'core_stock_selection_dmi_v1/DOMAIN.parquet',R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'),Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')]
(O/'ADDITIONAL_INPUT_HASHES.json').write_text(json.dumps({str(p):sha(p)for p in extra},indent=2))
qa=dict(native_PVR_max_error=float(a.PVR_abs_error.max()),existing_CMF_matches=len(z),existing_CMF_max_error=float((z.C-z.CMF21).abs().max()),existing_CMF_missing_exact=bool(z.C.notna().equals(z.CMF21.notna())),CSV_float_roundtrip_tolerance=1e-14,all_I_root_available=bool(a.root_known.all()),matrix_H120_rank7=bool(s[s.H.eq(120)].matrix_rank.eq(7).all()),matrix_H120_max_condition=float(s[s.H.eq(120)].condition.max()),models_fit=0,new_predictions=0,accounts=0,source_hashes_unchanged=all(sha(p)==h for p,h in json.loads((O/'INPUT_HASHES.json').read_text()).items()))
(O/'FINAL_AUDIT.json').write_text(json.dumps(qa,indent=2));print('CORRECT_SIGNAL_YEAR',pd.DataFrame(rows).to_string(index=False));print('PERIODS',json.dumps(period));print('QA',json.dumps(qa))
