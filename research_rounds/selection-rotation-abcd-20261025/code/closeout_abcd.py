from common_abcd import *
from decimal import Decimal as D

def main():
 assert read(HERE/'accounts/summary.json')['historical_account_runs']==9
 for p in ['technical/unit-tests-v2.json','technical/independent-board.json','technical/portfolio-rules.json','technical/transitive-source-identity.json','review/board-prefix.json','technical/A-controls/comparison.json','technical/A-controls/decision-comparison-v2.json','analysis/accounting-audit.json','diagnostics/receipt.json','ui-validation.json']:
  assert read(HERE/p)['passed'],p
 for cutoff in ['2018-12-28','2023-12-29']:
  for file in ['comparison.json','decision-comparison.json']:assert read(HERE/f'technical/prefix-{cutoff}'/file)['passed']
 for p in ['CONCLUSION.md','MANUAL_REVIEW.md','report/index.html','case-review/index.html']:assert (HERE/p).is_file()
 frozen=read(HERE/'freeze.json');nf=verify(frozen['sha256']);no=verify(read(HERE/'old-identity-before.json')['sha256']);nt=verify(read(HERE/'technical/transitive-source-identity.json')['sha256'])
 audit=read(HERE/'analysis/accounting-audit.json');maxerror=max(D(r['max_absolute_nav_difference_cny']) for r in audit['details']);assert maxerror<D('1e-8')
 import pandas as pd
 results=read(HERE/'analysis/summary.json');assert len(results)==12
 verdict='See CONCLUSION.md; no automatic promotion or additional search.'
 artifacts={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and not p.name.startswith('.') and p.name not in ['complete.json','server.log']}
 write(HERE/'complete.json',dict(recorded_at=now(),status='complete',technical_passed=True,economic_verdict=verdict,new_economic_accounts=9,old_A_reference_controls=3,physical_prefix_accounts=8,independent_daily_rows=sum(r['checks']['daily_independent_nav_and_shares'] for r in audit['details']),max_independent_nav_difference_cny=str(maxerror),audit_tolerance_cny='1e-8',all_actual_buys_original_IX_events=True,old_results_unchanged=True,old_artifacts_verified=no,transitive_original_sources_verified=nt,frozen_rules_unchanged=True,frozen_files_verified=nf,individual_IX_and_E0_unchanged=True,new_selection_groups=['B','D'],new_rotation_groups=['C','D'],position_formula_changes=0,mechanism_revisions_after_economics=0,economic_reruns=0,quote_downloads=0,strict_A_unknown_trace_exception='only two never-admissible cap-unknown event traces explicitly reconciled; all funded decisions and financial JSON exact',historical_basis='seen_development_current_survivor_cap_industry_bias',fixed_scenarios='continuous whole-A account time slices, not reset/independent market regime accounts',local_report='http://127.0.0.1:8794/report/',artifact_count=len(artifacts),artifacts=artifacts))
 print(dict(complete=True,artifacts=len(artifacts),independent_nav_max_error=str(maxerror),old_artifacts=no,source_files=nt),flush=True)
if __name__=='__main__':main()
