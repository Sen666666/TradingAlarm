"""Read small saved reports only; no account/financial model or price import."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];SRC={}
def bind(p):
 p=Path(p).resolve();SRC[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'filesystem_mtime_UTC_not_run_time':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()};return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 bind(__file__)
 paths={
  'native_No60_long_OFF':ROOT/'new_price_trend_v1/analysis/long_OFF_PERIODS.json',
  'same_OFF_in_CORE_candidate':ROOT/'core_confirmed_v1/analysis/long_OFF_PERIODS.json',
  'CORE_confirmed_ON':ROOT/'core_confirmed_v1/analysis/long_ON_PERIODS.json',
  'BB20_entry_ON':ROOT/'new_price_trend_v1/analysis/long_BB20_PERIODS.json',
 }
 snaps={label:{k:v for k,v in read(p).items()if k in ['all','2022','2023']}for label,p in paths.items()}
 for y in ['2022','2023']:
  for k in ['begin_NAV','end_NAV','return_pct','max_CLOSE_DD_pct']:
   assert snaps['native_No60_long_OFF'][y][k]==snaps['same_OFF_in_CORE_candidate'][y][k]
 p=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/execution_review/account_comparison/results_v2/PERIOD_ACCOUNT_MATRIX.json');matrix_path=p
 matrix=read(p)
 selected=[dict(source_row_index=i,**r)for i,r in enumerate(matrix)if r.get('period')in['2022','2023']and r.get('arm')in['BASELINE','EARLY_EMA60']]
 save('LOCAL_VERSION_AND_TASK3_YEAR_ROWS.json',dict(local_saved_periods=snaps,task3_original_period_matrix_path=str(p),task3_original_selected_rows=selected))
 pieces=[]
 snippets={
  ROOT/'core_confirmed_v1/RESEARCH_READOUT.txt':[(1,23)],
  ROOT/'core_confirmed_v1/analysis/READOUT.txt':[(1,5)],
  ROOT/'new_price_trend_v1/RESULTS_AND_DISPOSITION.txt':[(14,38)],
  Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/execution_review/account_comparison/results_v2/READOUT.txt'):[(1,14)],
  Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/REPORT.txt'):[(64,75)],
 }
 for path,rr in snippets.items():
  p=bind(path);ls=p.read_text().splitlines()
  for a,b in rr:
   pieces.append(f'PATH {p}\nSHA256 {SRC[str(p)]["sha256"]}\nLINES {a}-{b}\n'+'\n'.join(f'{n:4d} {ls[n-1]}'for n in range(a,min(b,len(ls))+1)))
 (OUT/'VERBATIM_SMALL_REPORT_SNIPPETS.txt').write_text('\n\n'.join(pieces)+'\n')
 for p in [Path('/tmp/history_local_numeric_matches.json'),Path('/tmp/history_local_numeric_matches_expanded.json')]:
  if p.exists():save(p.name,read(p))
 save('FINDINGS_AND_SEARCH_BOUNDARY.json',dict(
  status='NO_EXACT_LOCAL_PAIR_OF_2022_ANNUAL_MINUS26_AND_2023_ANNUAL_MINUS34_IDENTIFIED',
  definite_minus26_candidate=dict(source=str(paths['CORE_confirmed_ON']),year='2022',version='CORE_confirmed_ON candidate, not original No60_OFF',return_pct='-26.146897519181937400',max_CLOSE_DD_pct='26.485750264568237400',same_path_2023_return_pct='4.452695260637119026256451500'),
  definite_near34_DD_candidate=dict(source=str(matrix_path),arm='EARLY_EMA60',year='2023',note='33.8601941% is full-path-peak maximum drawdown, not2023 return.2023 return-3.9530107546%;localDD5.9312292968%.'),
  no_claim_of_chat_quote_provenance=True,
  search_scope='task-4 local prior RESULTS/analysis PERIODS/METRICS and task-3 existing small report/readout/summary/comparison JSON/text. Numeric JSON scans <=800KB, text <=1MB. Two overlapping small-JSON selections scanned379 and215 files. Large feature JSON/parquet/financial-engine pickle not scanned.',
  sibling_research_rounds_and_ar6_owned_by_other_agent=True,
  parent_shared_near_pair='Parent separately located cumulative2022-23 No60/PVR net trading cash ratios approximately-26.1336%/-34.3547%; this local task did not establish it was the earlier chat source.',
  new_accounts=0,new_backtests=0,new_indicators=0,new_models=0))
 save('SOURCE_FILE_IDENTITIES.json',SRC)
 save('OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
if __name__=='__main__':main()
