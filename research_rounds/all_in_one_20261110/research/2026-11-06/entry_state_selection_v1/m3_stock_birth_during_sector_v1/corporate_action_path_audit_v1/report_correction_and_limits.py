"""Reporting-only correction and raw-source cross-check; no economic rerun."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
a=pd.read_csv(O/'UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv');summary=json.loads((O/'SUMMARY.json').read_text())
factor=a[a.status.str.startswith('FACTOR')]
assert len(factor)==486 and all(bool(x) for x in factor.signal_factor_matches)
summary['factor_formula_matches']=sum(bool(x) for x in factor.signal_factor_matches)
summary['max_factor_relative_error']=float(factor.factor_relative_error.abs().max())
summary['reporting_correction']='SUMMARY.json used sum on object numpy booleans and reported 1 instead of 486. CSV, economics and original code preserved; this file corrects only reporting.'
summary['unknown_remaining_breakdown']={'held_cash_only':426,'held_share_distribution':50,'missing_raw_open':32}
save('SUMMARY_CORRECTED.json',summary)
# Recheck each action with its raw vendor row and original downloaded source hash.
raw_checks=[]
for r in factor.to_dict('records'):
 p=Path(r['raw_rights_source']);x=json.loads(p.read_text());matches=[e for e in x['records'] if str(e.get('1'))==r['status_day'].replace('-','')]
 row=dict(round_id=r['round_id'],sid=r['sid'],day=r['status_day'],raw_source=str(p),raw_source_sha256=sha(p),original_download=x.get('source_path'),expected_download_sha256=x.get('source_sha256'),row_count=len(matches),source_text_matches=any(e['471']==r['raw_action_text'] for e in matches))
 if x.get('source_path') and Path(x['source_path']).is_file():row['download_sha_matches']=sha(x['source_path'])==x['source_sha256']
 assert row['source_text_matches'] and row.get('download_sha_matches',False)
 raw_checks.append(row)
pd.DataFrame(raw_checks).to_csv(O/'RAW_ACTION_SOURCE_VERIFICATION.csv',index=False)
# Missing OPENs must stay missing: later observations do not fill earlier suspended/missing dates.
m=a[a.status.str.contains('MISSING')];p=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
d=pd.read_parquet(p,filters=[('symbol','in',m.sid.tolist()),('trade_date','>=',pd.Timestamp('2022-01-01')),('trade_date','<=',pd.Timestamp('2023-12-31'))]);out=[]
for r in m.to_dict('records'):
 f=d[d.symbol.eq(r['sid'])];day=pd.Timestamp(r['status_day']);hits=f[f.trade_date.eq(day)];aft=f[f.trade_date.gt(day)].sort_values('trade_date')
 out.append(dict(round_id=r['round_id'],sid=r['sid'],missing_day=r['status_day'],canonical_raw_exact_rows=len(hits),next_existing_raw_day=str(aft.iloc[0].trade_date.date()) if len(aft) else None,canonical_source=str(p),result='KEEP_UNKNOWN_NO_PRICE_FILL_NO_SUSPENSION_OR_DELISTING_INFERENCE'))
assert all(x['canonical_raw_exact_rows']==0 for x in out)
pd.DataFrame(out).to_csv(O/'MISSING_OPEN_CANONICAL_VERIFICATION.csv',index=False)
save('REPORT_CORRECTION_AUDIT.json',dict(economic_reruns=0,raw_action_rows_verified=len(raw_checks),raw_action_hashes_verified=len(raw_checks),factor_matches=summary['factor_formula_matches'],missing_opens_confirmed_absent=len(out),raw_canonical_sha256=sha(p),original_run_seal_hash=sha(O/'PRE_RUN_SEAL.json'),original_economic_outputs={n:sha(O/n) for n in ['BRIDGED_ROUNDS.csv','BRIDGED_ACTIONS.csv']},limitations=['Vendor rights observed in 2026 are retrospective history, not archived announcement-time snapshots. No claim of fully PIT availability.','Official historical record, pay, share-listing and fractional allocation/tax fields remain absent for unrepaired held actions.','Fixed original permits only. A full lifecycle rerun could create later permits after now-known exits.']))
print(json.dumps(summary,ensure_ascii=False,indent=2))
