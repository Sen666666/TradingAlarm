"""Correct reference-domain labels, preserve first diagnostic output unchanged, and report conservative wide coverage."""
from pathlib import Path
import json,hashlib,collections
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'m3_ab_shared_probe_v1/daily_gap_inventory_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def csv(n,t):
 with (O/n).open('x') as f:t.to_csv(f,index=False)
r=json.loads((O/'RESULT.json').read_text())
events=pd.read_csv(O/'CANDIDATE_EVENT_STATIC_CHECKS.csv')
eligible=events[~events.static_close_check.isin(['I_INELIGIBLE','PVR_UNKNOWN'])]
# No fixed-budget PASS filter is used for the authoritative broad inventory or public evidence search.
ren={'in_potential_domain':'original_fixed_budget_pass_reference_domain','potential_domain':'original_fixed_budget_pass_reference_domain','potential_missing_sessions':'original_fixed_budget_reference_missing_sessions','potential_stock_days':'original_fixed_budget_reference_stock_days','potential_missing_rows':'original_fixed_budget_reference_missing_rows'}
for n in ['STOCK_UNIVERSE','MISSING_ROW_RUNS','DAILY_ISSUES','FACTOR_LINEAGE_TRANSITIONS','OFFICIAL_SEARCH_QUEUE','ACTUAL_RESPONSIBILITY_ISSUES','ACTUAL_RESPONSIBILITY_TRANSITIONS']:
 t=pd.read_csv(O/(n+'.csv'),low_memory=False).rename(columns=ren)
 if 'priority' in t:
  uncovered=t.registry_covered_sessions.lt(t.missing_common_sessions)
  t.loc[uncovered & t.priority.isin(['P3_POTENTIAL_UNCOVERED','P4_BROAD_ONLY_OR_ALREADY_COVERED']),'priority']='P3_WIDE_DOMAIN_UNCOVERED'
  t.loc[~uncovered,'priority']='P4_EXISTING_REGISTRY_COVERED'
  t=t.sort_values(['priority','sid','gap_start'])
 if n=='STOCK_UNIVERSE':
  first=eligible.groupby('sid').next_common_open.min()
  t['first_I_PVR_eligible_next_open']=t.sid.map(first)
  t['has_I_PVR_eligible_event']=t.sid.isin(set(eligible.sid))
 csv(n+'_V2.csv',t)
g=pd.read_csv(O/'MISSING_ROW_RUNS_V2.csv')
d=pd.read_csv(O/'DAILY_ISSUES_V2.csv')
tr=pd.read_csv(O/'FACTOR_LINEAGE_TRANSITIONS_V2.csv')
g['exchange']=g.sid.str.rsplit('.',n=1).str[-1]
g['start_year']=g.gap_start.str[:4]
d['exchange']=d.sid.str.rsplit('.',n=1).str[-1];d['year']=d.day.str[:4]
missing=d[d.issue.eq('MISSING_ROW')].copy()
missing['actual_held']=missing.actual_core_preopen.add(missing.actual_add_preopen).gt(0)
missing['old_noshared_reference_held']=missing.old_noshared_core_preopen.add(missing.old_noshared_add_preopen).gt(0)
stats={'run_counts_by_exchange_start_year_type':g.groupby(['exchange','start_year','gap_type']).size().reset_index(name='runs').to_dict('records'),'missing_stock_days_by_exchange_year':missing.groupby(['exchange','year']).agg(missing_stock_days=('sid','size'),sids=('sid','nunique'),actual_held_days=('actual_held','sum'),original_noshared_reference_held_days=('old_noshared_reference_held','sum'),covered_existing_registry_days=('registry_covered','sum')).reset_index().to_dict('records')}
save('EXCHANGE_YEAR_COVERAGE_V2.json',stats)
authoritative={k:v for k,v in r.items() if k not in ['scope','static_pass_events','static_potential_sids','static_potential_stock_days','potential_missing_stock_days','potential_missing_run_count','potential_missing_sid_count','missing_priority_runs','limits']}
authoritative.update(scope='2022_ORIGINAL_A_B_WIDE_CANDIDATE_DOMAIN_WITH_ACTUAL_SHARED_RESPONSIBILITY_OVERLAY',authoritative_csv_suffix='_V2.csv',source_population_note='Original fixed 1709-stock current-source NON-PIT pool. The 1458 names are only its 2022 A+B event subset, not the historical all-A-share market. Future survival/membership selection bias is not repaired by halt evidence.',all_I_PVR_eligible_events=len(eligible),all_I_PVR_eligible_sids=eligible.sid.nunique(),original_fixed_budget_reference={'NAV':'1200000','INIT':'24000','RISK':'3000','PASS_events':r['static_pass_events'],'PASS_sids':r['static_potential_sids'],'PASS_reference_stock_days':r['static_potential_stock_days'],'PASS_reference_missing_stock_days':r['potential_missing_stock_days'],'minimum_lot_or_risk_reject_events':int(events.static_close_check.eq('MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE').sum()),'exclusion_authority':'NONE: shared Nd varies. All 1458 names remain in authoritative inventory and search queue.'},missing_priority_runs=g.priority.value_counts().to_dict(),missing_runs_by_exchange=g.exchange.value_counts().to_dict(),missing_runs_by_start_year=g.start_year.value_counts().to_dict(),actual_held_runs=g[g.actual_held_sessions.gt(0)][['sid','gap_start','gap_end','missing_common_sessions','registry_covered_sessions','actual_held_sessions','actual_core_start','actual_add_start','previous_valid_day','next_valid_day']].to_dict('records'),official_new_missing_sessions_to_investigate=int(len(missing)-missing.registry_covered.sum()),official_new_missing_runs_to_investigate=int(g.registry_covered_sessions.lt(g.missing_common_sessions).sum()),limits=['No economic account was replayed. All original sources and all three sealed old/new cohort ledgers are preserved.','The wide domain includes every original A/B candidate security from its first next common OPEN to follow-end. It is a conservative workload superset, not a claim that each is actually held.','The 1406-stock/9386-event subset is original fixed-budget reference only. Its rejects may become feasible at another shared Nd and do not shrink the authoritative broad domain.','I/PVR eligibility is independent of budget and is reported separately; it still does not imply selection or a funded fill.','First/last source rows are source-window facts. A leading/trailing gap is not certified as pre-IPO, permanent cessation or delisting without independent evidence.','Next observed valid bar is not by itself proof of official resumption, nor is any missing row proof of a halt.','The first scan V1 labels incorrectly called the fixed-budget reference subset potential. V1 is preserved for trace; this V2 is authoritative.','Original independent-round inventory is only a possible-responsibility reference, never the funded shared path or a PnL label.','No synthetic prices, bar forward-fills, indicator forward-fills or minute data were used.','NON-PIT selection, source availability, and historical-executability limitations remain after any evidence matching.'])
save('RESULT_V2.json',authoritative)
text='# Daily gap inventory, authoritative v2\n\nStrictly read-only source inventory. No economic replay.\n\n'
text+='Use RESULT_V2.json and the *_V2.csv files. The first diagnostic files are preserved, but their potential-domain label only means the original fixed-budget PASS reference subset. It must not be used to prune shared-account candidates.\n\n'
text+='Main scope: every 2022 original A/B event security in the original NON-PIT fixed universe, beginning at its first candidate next common OPEN and ending 2026-06-30. This is not a historical whole-A-share universe and not an actual-holdings assertion.\n\n'
text+='OFFICIAL_SEARCH_QUEUE_V2.csv contains only security, name, dates, gap shape, adjacent public-price facts, and internal responsibility priority. Do not transmit private account sizes, PnL, strategy or local paths to public search services.\n\n'
text+='STOCK_UNIVERSE_V2.csv and CANDIDATE_EVENT_STATIC_CHECKS.csv define the complete reproducible stock-day domain. DAILY_ISSUES_V2.csv lists anomalous dates only; MISSING_ROW_RUNS_V2.csv groups contiguous missing common sessions. FACTOR_LINEAGE_TRANSITIONS_V2.csv separates admitted coordinate changes from other changes, not all changes are data failures.\n\n'
text+='ACTUAL_RESPONSIBILITY_ISSUES_V2.csv reconstructs pre-OPEN quantities from sealed executed transactions only. Unknown quantities remain held as recorded; it neither repairs missing data nor pretends later prices restore an UNKNOWN path. Original no-shared positions are reference only.\n'
with (O/'READOUT_V2.md').open('x') as f:f.write(text)
save('OUTPUT_SEAL_V2.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
print(json.dumps(authoritative,ensure_ascii=False,default=str),flush=True)
