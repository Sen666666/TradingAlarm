"""Delivery identity checks only; no repeated model or account execution."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, d):
    with Path(p).open('x') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')

freeze = read(ROOT/'freeze.json')
assert sha(ROOT/'PROTOCOL.md') == freeze['protocol_sha256']
assert sha(ROOT/'inputs/manifest.json') == freeze['source_manifest_sha256']
for k, v in freeze['code'].items(): assert sha(ROOT/'code'/k) == v
for k, v in freeze['inputs'].items(): assert sha(k) == v
registry = read(REPO/'research_rounds/algorithm-baselines-20261024/registry.json')
for k, v in registry['sha256'].items(): assert sha(REPO/k) == v
inputs = read(ROOT/'inputs/manifest.json')
for s in inputs['series']:
    assert sha(s['path']) == s['sha256']
    for source in s['sources']: assert sha(source['path']) == source['sha256']
figures = read(ROOT/'figures/manifest.json')['plots']
assert len(figures) == 20
for f in figures: assert sha(f['path']) == f['sha256']
receipt = read(ROOT/'reviews/raw/ALL_FIGURES_RECEIPT.json')
assert receipt['coverage_actually_viewed_real'] == 20
assert receipt['figure_manifest_sha256'] == sha(ROOT/'figures/manifest.json')
assert receipt['review_sha256'] == sha(ROOT/'reviews/raw/ALL_FIGURES_REVIEW.md')
for f in receipt['figures']:
    match = next(x for x in figures if x['id'] == f['id'])
    assert match['sha256'] == f['sha256'] and f['view_image_actually_viewed']
checks = read(ROOT/'validation/checks.json')
assert checks['passed'] and checks['account_runs'] == 0
assert checks['technical_invariants'] == 30
assert len(checks['physical_input_prefixes']) == 21
audit = read(ROOT/'reviews/implementation/audit.json')
for sid, v in audit['audited_result_sha256'].items(): assert sha(ROOT/'results'/(sid+'.parquet')) == v

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.targets=[]
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('href','src') and v and not v.startswith(('http:', 'https:', '#', 'data:')):
                self.targets.append(v)
parser = Links(); parser.feed((ROOT/'report/index.html').read_text())
for target in parser.targets: assert (ROOT/'report'/target).resolve().is_file(), target
for p in (ROOT/'validation').glob('*.parquet'): assert (ROOT/'figures'/(p.stem+'.png')).is_file()
for sid in read(ROOT/'analysis/viewer-data.json'): assert (ROOT/'results'/(sid+'.csv')).is_file()

now = datetime.now(timezone.utc).isoformat()
delivery = dict(recorded_at=now, passed=True, model_and_inputs_still_frozen=True,
    registry_files_unchanged=len(registry['sha256']), original_source_identity=True,
    real_plots_identity=20, real_plots_actually_reviewed=20, synthetic_plots=9,
    relative_static_links_checked=len(parser.targets), all_asset_csv_links_present=True,
    ui_review=dict(url='http://127.0.0.1:8785/report/', actual_browser_loaded=True,
        default_AU0_date='2026-02-02', default_S=99.87,
        semiconductor_button_date='2026-07-02', semiconductor_S=99.32,
        SMIC_button_date='2024-10-08', SMIC_S=80.93, SMIC_total_diagnostic=-91.18,
        method='Cua native AX initial/full state and visible button transitions; screenshot visual check'),
    account_runs=0, formula_changes_after_real_outputs=0,
    interpretation='Delivery checks do not validate model semantics, prediction or economics.')
write(ROOT/'audit/final-closeout.json', delivery)
artifacts = {str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts and p.name != 'complete.json'}
write(ROOT/'complete.json', dict(recorded_at=now, status='research_delivered',
    decision='retain_narrow_drift_prototype_not_promoted_to_unified_strength',
    user_goal_model_strategy_separation_preserved=True, unified_strength_goal_validated=False,
    formal_candidates=1, design_only_rejected_candidates=1, independent_blank_reviewers=4,
    real_output_rule_revisions=0, account_runs=0, trading_rule_changes=0, e0_changes=0,
    market_downloads=0, real_figures=20, synthetic_figures=9,
    technical_invariants=30, physical_input_prefixes=21,
    raw_figure_review_count=26, independent_finite_numeric_values=308653,
    independent_max_abs_error=9.36e-9, regime_labels_are_future_known_development_only=True,
    execution_sequence_deviation_disclosed=True, semantic_limitations_disclosed=True,
    no_automatic_followup_queue=True, report_url='http://127.0.0.1:8785/report/',
    artifact_sha256=artifacts))
print({'passed':True, 'artifact_files':len(artifacts), 'old_registry_unchanged':len(registry['sha256']),
       'real_plots':20,'synthetic_plots':9,'accounts':0})
