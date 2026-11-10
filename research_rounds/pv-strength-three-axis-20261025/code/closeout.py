"""Final evidence identity/link closure only. No model or account execution."""
from pathlib import Path
from html.parser import HTMLParser
import json
from common import ROOT,REPO,OLD,read,write,sha,now

for version in ['freeze.json','freeze-v1.json']:
    f=read(ROOT/version)
    for p,v in f['sha256'].items():assert sha(REPO/p)==v,p
    for p,v in f['old_b1_files'].items():assert sha(OLD/p)==v,p
registry=read(REPO/'research_rounds/algorithm-baselines-20261024/registry.json')
for p,v in registry['sha256'].items():assert sha(REPO/p)==v,p
check=read(ROOT/'validation-v1/checks.json');assert check['technical_passed']
assert check['technical_checks']==88 and check['synthetic_paths']==17
assert check['real_B2_outputs_have_not_been_generated']
implementation=read(ROOT/'reviews/implementation/receipt.json');assert implementation['passed']
assert implementation['real_physical_prefixes']==14
for p,v in implementation['sha256'].items():assert sha(ROOT/'reviews/implementation'/p)==v,p
unit=read(ROOT/'reviews/implementation/all-fixture-unit-boundary.json')
assert unit['passed']==unit['fixtures']==17
real=read(ROOT/'figures/real-manifest.json');synthetic=read(ROOT/'figures/synthetic-manifest.json')
assert len(real['plots'])==22 and len(synthetic['plots'])==17
for f in real['plots']+synthetic['plots']:assert sha(f['path'])==f['sha256']
review=read(ROOT/'reviews/output/OUTPUT_VIEW_RECEIPT.json')
assert review['actual_view_image_count']==22 and review['all_manifest_images_viewed']
assert review['source_manifest_sha256']==sha(ROOT/'figures/real-manifest.json')
assert review['review_sha256']==sha(ROOT/'reviews/output/OUTPUT_REVIEW.md')
assert review['facts_sha256']==sha(ROOT/'reviews/output/SELECTED_OUTPUT_FACTS.csv')
synthetic_review=read(ROOT/'reviews/adversarial/SYNTHETIC_VIEW_RECEIPT.json')
assert synthetic_review['count']==17
assert synthetic_review['manifest_sha256']==sha(ROOT/'figures/synthetic-manifest.json')
for f in synthetic_review['actual_views']:
    assert sha(f['image'])==f['image_sha256']
    assert sha(f['parquet'])==f['parquet_sha256']
for sid,v in read(ROOT/'analysis/summary.json')['inputs'].items():assert sha(ROOT/'results'/(sid+'.parquet'))==v

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ['href','src'] and v and not v.startswith(('http:','https:','#','data:')):self.links.append(v)
links=Links();links.feed((ROOT/'report/index.html').read_text())
for p in links.links:
    if p!='../complete.json':assert (ROOT/'report'/p).resolve().is_file(),p

delivery=dict(recorded_at=now(),passed=True,active_version='numerical-v1',
    original_v0_failed_synthetic_preserved=True,v0_frozen_files=39,v1_frozen_files=40,
    prior_B1_unchanged=144,registered_baselines_unchanged=30,
    independent_real_rows=17605,independent_fields=49,independent_max_abs_error=implementation['max_abs_error'],
    actual_real_views=22,actual_synthetic_views=17,technical_checks=88,
    real_physical_prefixes=14,synthetic_physical_prefixes=4,old_B1_diagnostic_prefixes=6,
    all_fixture_specific_unit_transform_passed=17,
    report_static_links_checked=len(links.links),
    browser_checked=dict(url='http://127.0.0.1:8786/report/',loaded=True,
        initial_range_date='2025-07-31',initial_P21=.03,initial_retention_pct=81.93,
        decline_button_date='2026-04-01',decline_P5=.55,decline_P21=-1.25,decline_direction='down',
        failed_bounce_date='2022-08-05',retention_pct=100,span_log_pct=14.32,age=0,support_advances=0,
        method='Native CUA accessibility states, actual control clicks, screenshot visual check'),
    frozen_index_restore=dict(path='reviews/adversarial/README.md',hash=sha(ROOT/'reviews/adversarial/README.md'),
        after_output_index_preserved='reviews/adversarial/README.after-output.md',
        note='Only mutable review index links had been appended; original exact index restored and expanded copy retained.'),
    account_runs=0,market_data_downloads=0,model_formula_changes_after_real_outputs=0,
    interpretation='Evidence identity/causality only; no unified strength, economic or five-class accuracy admission')
write(ROOT/'audit/delivery.json',delivery)
artifact={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file()
          and '__pycache__' not in p.parts and 'mplconfig' not in p.parts and p.name!='complete.json'}
write(ROOT/'complete.json',dict(recorded_at=now(),status='research_delivered',
    decision='retain_three_axis_description_not_promoted_to_unified_strength_or_trading',
    goal_model_strategy_separation=True,formal_candidates=1,numerical_revisions=1,
    mechanism_parameter_revisions_after_real_output=0,account_runs=0,market_data_downloads=0,
    blank_agents=5,real_assets=7,real_figures=22,synthetic_figures=17,
    actual_review_coverage_real=22,actual_review_coverage_synthetic=17,
    actual_historical_development_only=True,composite_score_defined=False,
    prior_E0_R_R1_names_and_logic_unchanged=True,B2_internal_R_is_retention_not_registered_R_policy=True,
    unresolved=['narrow_box_small_episode_churn','countertrend_new_episode_is_not_mature_trend',
        'structure_confirmation_lag','slow_pace_can_stay_positive_on_crash','stale_PV_regions',
        'volume_gate_does_not_cover_all_declines','machine_boundary_sensitivity'],
    no_automatic_followup_queue=True,report_url='http://127.0.0.1:8786/report/',artifact_sha256=artifact))
assert (ROOT/'complete.json').is_file()
print({'passed':True,'artifacts':len(artifact),'old_B1':144,'baseline':30,'accounts':0,
       'real_views':22,'synthetic_views':17})
