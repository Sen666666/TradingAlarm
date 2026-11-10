"""Final saved-scope/count/time audit only. No new feature, source implementation or model run."""
from pathlib import Path
from decimal import Decimal as D
import hashlib,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');T=O.parent;P=T/'ar6_native_feasibility/VOLUME_FULL_EXPORT_DESIGN'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
f=load(P/'FINAL_STOP_SCOPE_AND_TIME.json')
for p,h in f['sources'].items():assert sha(p)==h
assert f['full_workers_ever_started']==0 and not f['ACT_neutral_ever_computed']and not f['full_1799_export_authorized']
assert not(T/'ar6_native_feasibility/VOLUME_FULL_FEATURES_V1').exists()
assert not(T/'ar6_native_feasibility/VOLUME_ACT_SHARED_GATE_V1/NEUTRAL_FEATURES.parquet').exists()
times=f['recorded_compute_process_wall_seconds'];assert abs(D(str(times['three_fixtures']))+D(str(times['three_stage_including_failure']))+D(str(times['ACT_first_gate']))-D(times['subtotal_excluding_independent_F1']))<D('1e-12');assert abs(D(times['subtotal_excluding_independent_F1'])+D(str(times['independent_F1']))-D(times['total']))<D('1e-12')
S={'000001.SZ','300001.SZ','688001.SH'};B=T/'risk_constraints/ma63_information_diagnostic_v1';tails=load(B/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members'];coverage={}
for w in ['2022_2024','strong']:
 rows=load(B/(w+'_ENTRIES.json'));samples=[r for r in rows if r['sid']in S]
 coverage[w]=dict(all_actual_layer_records=len(rows),three_fixture_stock_actual_records=len(samples),original_buycost_associated=str(sum((D(r['cost'])for r in samples),D(0))),original_lifetime_net_associated=str(sum((D(r['net'])for r in samples),D(0))),fixed_original_tail_all=len(tails[w]),three_fixture_stock_fixed_tail_members=sum(r['sid']in S for r in tails[w]))
x=dict(status='CLOSED_FOUNDATION_WIRING_BRANCH_NO_AUTOMATIC_CONTINUATION',source_stop_documents_verified=True,
 actual_completed_scope=['Three fixedstock+threeindustry fullwarm mechanical REAL/NEUTRAL controls,18NEUTRAL featureprefixes; REAL cache references/PVR limitedreference exact, not fullqualitybasis.', 'Same threeindustry puremarket Stage/trace and3NEUTRAL Sep23prefixes,841neutralreceipt IDs/effective1 signatures andownE0episodes independentlyaudited; not90batch.', 'One fullroster REAL ACT gate, originalproduction CSV domain independently reproduced. Strict raw/defaultfloat failure preserved; no neutralACT or knownmultipliermaskgate completed.', 'Frozen explanationprotocol plus all3436originaldecision facts/1205SHA independentlychecked; core802 needsfreshI, mobile178withoutfreshI validoriginalcases.'],
 mechanical_sample_actual_population_intersection=coverage,
 monetary_coverage_judgment='No demonstrated reduction of the main3year loss362010.39,2022_2023loss254573.04,postOct8wholephase loss167054.32 or303newfill loss112457.60. These are originalaccount/layer amounts, not candidate avoidableloss. Threefixture intersections are originalmoney association only; not an estimate of effect on even those5filledrows. Fixedoriginalwinner83/94 coverage in thesethreestockfixtures is0/0.',
 why_closed='Elapsed wiring/preparation dominates while major-loss and fixed-winner quality coverage remains unproved. Rawinputs are present; missingevidence is not a datadownload blocker. The1e-16 CSV parser difference is not a changedalgorithm or a reason for moreengineering.',
 necessary_research_question='Which existing entry/reentry evidence genuinely distinguishes the high-exposure/ACTon repeated-failure losses from normaltrial/pullback preceding durable winners, with adequate fullmother scale and symmetric winnercounterexamples? Establish that question directly from the savedloss paths before any newboundedalgorithmtest; completing1799wiring is not a mandatory gate.',
 elapsed_scope=dict(recorded_model_check_process_wall_seconds=times,active_wall_approx=f['active_wall_approx'],note='Approx48min preparation/source/wiring/collaboration/archive wall is parentreported, not independentlyinstrumented CPU; exact components only savedprocessreceipts. Reviewer savedfile arithmetic doesnot run models.'),
 final_limits=['All full1799/controller expansion, ACTneutral continuation/v2 and longbatch are stopped, not awaitingautomaticGO.', 'Prior A/B/mobile-risk/55financial branches remainclosed. No neworder/account/realtrade/publication.', 'No overall strategy improvement or usergoalcompletion claimed; current No60 absoluteperformance rejection remains.'],
 reviewer_new_model_or_account_runs=0,inputs={str(p):sha(p)for p in [P/'FINAL_DISPOSITION_STOP.txt',P/'FINAL_STOP_SCOPE_AND_TIME.json',O/'VOLUME_ACT_SERIALIZED_CONTROL_AUDIT.json',O/'VOLUME_THREE_INDUSTRY_STAGE_AUDIT.json',O/'VOLUME_INTERPRETATION_PROTOCOL_AUDIT.json',O/'VOLUME_THREE_FIXTURE_COMPLETED_AUDIT.json',B/'2022_2024_ENTRIES.json',B/'strong_ENTRIES.json',B/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json',Path(__file__)]})
(O/'VOLUME_RESEARCH_BRANCH_STOP_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],coverage=coverage),ensure_ascii=False))
