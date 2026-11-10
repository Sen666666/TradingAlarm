"""Saved-field timing/algebra invariants only; no signal or account execution."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent
f=pd.read_parquet(O/'ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS.parquet')
s=pd.read_parquet(O/'STATIC_MEMBERS_ORIGINAL_STOCK_FACTS.parquet')
a=pd.read_parquet(O/'ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES.parquet')
u=pd.read_parquet(O/'STATIC_MEMBERS_ORIGINAL_STOCK_FACTS_WITH_SAVED_U.parquet')
alt=pd.read_parquet(O/'ALT_RUNTIME_I_G1_NOT_CONSUMED.parquet')
checks={'rows_168':len(f)==168,'no_duplicate_case_date':not f.duplicated(['case_id','date']).any()}
for l,r in [('native_E0__e0_target','CP_input__e0_valid'),('native_E0__e0_target','market_state__E0_valid'),('CP__receipt','market_state__receipt')]:checks[l+'='+r]=bool(f[l].astype(bool).eq(f[r].astype(bool)).all())
for l,r in [('native_E0__e0_floor','CP_input__i_floor'),('native_E0__close','CP_input__close'),('native_E0__close','market_state__close')]:checks[l+'='+r]=bool((f[l].eq(f[r])|(f[l].isna()&f[r].isna())).all())
checks['E0_down_is_confirmed_event_minus1']=bool(f.CP_input__e0_down.eq(f.upstream_events__event.eq(-1)).all())
for kind in ['low','high']:checks[kind+'_confirmation_at_or_before_T']=bool((f['last_confirmed_'+kind+'_confirmation_date'].dropna()<=f.loc[f['last_confirmed_'+kind+'_confirmation_date'].notna(),'date']).all())
checks['stock_asof_no_future']=bool(s.source_date.dropna().le(s.loc[s.source_date.notna(),'date']).all())
checks['i_buy_absent_exact_unknown_field_false_original_event']=bool(s.loc[~s.exact_date,'i_buy_exact_field'].isna().all()and s.loc[~s.exact_date,'i_buy_original_daily_event'].eq(False).all())
for c in ['g_fresh_up','g_acute_down']:
 checks[c+'_stock_never_ffill']=bool(s.loc[~s.exact_date,c].isna().all())
 checks[c+'_alternate_never_ffill']=bool(alt.loc[~alt.exact_date,c].isna().all())
for c in ['e0_ready','e0_target','i_target','i_buy_exact_field','i_buy_original_daily_event','g_ready','g_fresh_up','g_acute_down']:
 for prefix,denom in [('',a.whole_static_sector_N),('U_',a.U_N_from_saved_industry_aggregate)]:
  checks[prefix+c+'_known_unknown_denominator']=bool((a[prefix+c+'_known_N']+a[prefix+c+'_unknown_N']).eq(denom).all())
  checks[prefix+c+'_true_false_known']=bool((a[prefix+c+'_true_N']+a[prefix+c+'_false_N']).eq(a[prefix+c+'_known_N']).all())
checks['U_inside_status_known_all_168']=a.U_inside_original_E0_I_counts_status.eq('KNOWN_FROM_SAME_PASS_SAVED_U_MASK').all().item()
checks['U_mask_rows_no_missing']=bool(u.qualified_U_t.notna().all()and len(u)==len(s))
checks['industry_I_permission_NA_not_used']=bool(f.industry_I_permission.eq('N/A_NOT_USED_BY_NO60').all())
checks['market_CP_not_financial_permission']=bool(f.market_state__financial_state_owned.eq(False).all())
out={'all_passed':all(checks.values()),'checks':checks,'stock_fact_rows':len(s),'stock_no_prior_rows':int(s.source_date.isna().sum()),'stock_exact_rows':int(s.exact_date.sum()),'stock_stale_asof_rows':int((s.source_date.notna()&~s.exact_date).sum()),'stock_i_buy_field_unknown_rows':int(s.i_buy_exact_field.isna().sum()),'nonexact_asof_raw_G1_flags_NOT_today_evidence':{c:int(s.loc[~s.exact_date,c+'_asof_raw'].eq(True).sum())for c in ['g_fresh_up','g_acute_down']},'source_qualification_warning':'Not full original S0 Q; no financial permission computed'}
(O/'EXTRACTION_INVARIANTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert out['all_passed'],out
print('PASS',len(checks),'invariants')
(O/'OUTPUT_SHA256.json').write_text(json.dumps({str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'and p.suffix!='.log'},ensure_ascii=False,indent=2)+'\n')
