"""Seal stable research deliverables; no Account/Runner or financial replay."""
from pathlib import Path
from datetime import datetime, timezone
import csv, hashlib, json

ROOT = Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def read(p): return json.loads(Path(p).read_text())
def put(n,v):
    p=ROOT/n
    assert not p.exists(), ('Do not overwrite sealed root output',p)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

audit=ROOT/'independent_review'
required=[audit/'ROOT_REPORT_AND_ETA_COMPARISON_AUDIT.json',
          audit/'STRUCTURAL_FINAL_AUDIT_INDEX.json',
          audit/'PVR_ETA_2022_2024_ACCOUNT_AUDIT.json',
          audit/'PVR_ETA_strong_ACCOUNT_AUDIT.json',
          audit/'ETA_STALE_ACTION_MARK_INDEPENDENT_CHECK.json']
for p in required:
    assert p.is_file(), ('Waiting for final audit',p)
    d=read(p)
    assert str(d.get('status','')).startswith('PASS'), (p,d.get('status'))
cmp=ROOT/'eta_account_comparison/results_v1'
assert read(cmp/'VALIDATION.json')['status'].startswith('PASS')
assert len(list(csv.DictReader((cmp/'FIXED18_PERIODS_TWO_CONFIGURATIONS.csv').open())))==36
assert len(list(csv.DictReader((cmp/'TEN_DISJOINT_STAGES_TWO_CONFIGURATIONS.csv').open())))==20
for w in ('2022_2024','strong'):
    run=ROOT/'pvr_eta_v1/runs'/w
    assert read(run/'DONE.json')['completed'] and read(run/'TIMING.json')['completed']
now=datetime.now(timezone.utc).isoformat()
entries={
 'main_report':'REPORT.txt', 'original_diagnostic':'DIAGNOSTIC_REPORT.txt',
 'ten_disjoint_stages':'accounting/results_v2/STAGE_WEALTH_CAPITAL_MATRIX.csv',
 'primary_ten_plus_three_controls':'chains/COMPLETE_ORIGINAL_CHAINS.json',
 'local_execution_points_and_unknowns':'executable_bounds',
 'local_independent_review':'chains/LOCAL_BOUND_THIN_REVIEW.json',
 'scale_and_concentration':'scale_concentration/results_v3',
 'native_E0_I_CP_ACT_semantics':'state_semantics',
 'single_mechanism':'mechanism_design/PROPOSAL.md',
 'preregistration':'pvr_eta_v1/HYPOTHESIS_FREEZE.json',
 'launch_gate_at_launch':'pvr_eta_v1/EXECUTION_GATE.json',
 'new_complete_accounts':'pvr_eta_v1/runs',
 'fixed_comparisons':'eta_account_comparison/results_v1/FIXED18_PERIODS_TWO_CONFIGURATIONS.csv',
 'candidate_disjoint_stages':'eta_account_comparison/results_v1/TEN_DISJOINT_STAGES_TWO_CONFIGURATIONS.csv',
 'figure':'eta_account_comparison/results_v1/ETA_NAV_DD_FEES.png',
 'semiconductor_legacy_field_correction':'eta_account_comparison/results_v1/SEMICONDUCTOR_FIELD_SEMANTICS_SUPPLEMENT.json',
 'independent_audit_index':'independent_review/STRUCTURAL_FINAL_AUDIT_INDEX.json',
 'report_and_comparison_audit':'independent_review/ROOT_REPORT_AND_ETA_COMPARISON_AUDIT.json'}
for p in entries.values(): assert (ROOT/p).exists(),p
put('DELIVERABLE_INDEX.json',dict(status='COMPLETE_HISTORICAL_DEVELOPMENT_NO_PROMOTION',created_at_UTC=now,entries=entries,new_full_financial_paths=2,reused_baseline_full_paths=2,independent_physical_prefix_closes=14,independent_physical_prefix_not_a_full_path=True,main_period_rows=36,disjoint_stage_rows=20,primary_chains=10,attached_controls=3,local_static_differences_are_not_portfolio_profit=True,all_history_consumed_not_OOS=True,no_parameter_rescue=True,remaining_execution_blockers=[],data_limits=['Current frozen universe and sector membership are not PIT','Historical first-publication/revision vintages unverified','Native A-share tradeability/capacity proxies do not verify actual queue fills','Corporate-action paid_at/new-shares-sellable dates unknown; AR distinct from available cash'],resolved_audit_issue='Facts-only cold reader omitted original native stale-action ex-reference for300319; source-proved read-only sidecar, no account/source/tolerance mutation or financial rerun.'))
put('COMPLETION.json',dict(completed=True,created_at_UTC=now,new_full_financial_paths=2,all_required_independent_receipts={str(p.relative_to(ROOT)):sha(p) for p in required},reported_result='ETA weak endpoint+63865.451041274235CNY; strong endpoint-318377.900499170694CNY versus frozen BASE. Both drawdowns lower, no general enhancement promoted.',new_full_paths_pending=0,no_production_or_live_trading=True))
files={};total=0
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or p.name in ('FINAL_BINDING_SHA256.json','.DS_Store'): continue
    assert not p.is_symlink(),p
    total+=p.stat().st_size; files[str(p.relative_to(ROOT))]=sha(p)
put('FINAL_BINDING_SHA256.json',dict(created_at_UTC=now,status='SEALED_ALL_LOCAL_RESEARCH_REGULAR_FILES_EXCEPT_SELF_AND_CACHES',root=str(ROOT),file_count=len(files),bytes=total,sha256=files,external_frozen_provenance='Original baseline books, manifests, facts, checkpoints and source identities are referenced by already-audited SOURCE_SHA256/RUN_METADATA and nested review receipts; no frozen external evidence was rewritten.'))
print(json.dumps(dict(files=len(files),bytes=total,report_sha256=sha(ROOT/'REPORT.txt'),binding_sha256=sha(ROOT/'FINAL_BINDING_SHA256.json'))))
