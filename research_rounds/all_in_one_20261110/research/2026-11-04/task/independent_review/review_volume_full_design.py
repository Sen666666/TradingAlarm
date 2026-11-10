"""Only card/existing JSON metadata/source audit; no model imports or runs."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');P=O.parent/'ar6_native_feasibility/VOLUME_FULL_EXPORT_DESIGN'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
f=load(P/'SOURCE_BINDING.json');meta=load(P/'METADATA_AND_BUDGET.json');card=P/'CARD.md'
for p,h in f['sources'].items():assert sha(p)==h,('source changed',p)
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');sm=load(W/'STOCK_MANIFEST.json');im=load(W/'INDUSTRY_MANIFEST.json')
assert len(sm)==1709 and len(im)==90
ss=sum(x['full_warm_observations']for x in sm);ii=sum(x['full_warm_observations']for x in im);assert(ss,ii,ss+ii)==(meta['stock_warm_rows'],meta['industry_warm_rows'],meta['total_warm_rows'])==(4049565,364796,4414361)
assert Counter(x['status']for x in sm)==Counter(meta['stock_status']);assert Counter(x['mode']for x in sm)==Counter(meta['source_modes'])
na=[x['symbol']for x in sm if not x['full_warm_observations']];assert sorted(na)==sorted(meta['empty_stocks_preserved_as_NA'])and len(na)==22
D=O.parent/'risk_constraints/ma63_information_diagnostic_v1';tails=load(D/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members'];mothers={};tot=0
for win in ['2022_2024','strong']:
 rows=load(D/(win+'_ENTRIES.json'));assert len(rows)==meta['mother_counts'][win];assert len(tails[win])==meta['fixed_original_tail_counts'][win]
 assert len({x['layer']for x in rows})==len(rows)
 mothers[win]=dict(actual_layer_records=len(rows),unique_sids=len({x['sid']for x in rows}),unique_budget_order_ids=len({x['budget_order']for x in rows}),fixed_original_tail_records=len(tails[win]));tot+=len(rows)
assert tot==3436 and meta['stock_day_strategy_calendar_cells']==1709*968==1654312
assert meta['future_proposed_workers_max']==6 and meta['future_proposed_hard_wall_seconds']==3600
assert meta['new_feature_exports']==meta['new_model_runs']==meta['new_account_runner_objects']==0
expected=meta['real_fixture_seconds']*4414361/20296;assert expected==meta['real_serial_extrapolated_seconds'];assert expected/6==meta['real_six_ideal_seconds'];assert math.isclose(expected/6*2*1.35,meta['both_six_equal_cost_plus35pct_seconds'],rel_tol=0,abs_tol=1e-12)
x=dict(status='DESIGN_SUPPORTED_FOR_THIN_IMPLEMENTATION_ONLY_NO_FULL_EXPORT_OR_ACCOUNT_EXECUTION_AUTHORIZATION',card_SHA256=sha(card),source_SHA_checks=len(f['sources']),metadata_independently_counted=dict(stocks=1709,industries=90,total_warm_rows=4414361,complete_stocks=1687,empty_NA_stocks=22,stock_day_calendar_cells=1654312),actual_mothers=mothers,
 priority_judgment='This control can test whether predictive volume changes evidence at the main loss periods and fixed original winners, while retaining newly generated neutral opportunities. Full1799 scope is justified by complete streams and full1709 ACT breadth, not a parameter sweep. It cannot establish candidate account performance or avoided loss from old outcomes.',
 minimum_outputs=['All3436 original actual-layer decisions with original decision_at/signal_at and money only associated labels, orderid separately counted.', 'All two-arm signal streams with complete observed/known/NA/neither denominators and new/removed/earlier evidence retained; no forced nearest-neighbor identity.', 'All original fixed83/94 winner records, not only45/67 No60 matches; exactmatches/same-stock-otherrecord/misses/NA separate.'],
 source_interface_review={'assembly':'Reuses c3dbee... exact assemble and pure original dependencies; no new state machine or real I/grade/CP1 consumed as neutral upstream.', 'industry_stage':'Only original puretrace+Stage on eacharm fullwarm E0/CP1; true oldstate identity first, neutral effective m1 not observed diagnosticm, armnamespace separate. Pure AST/dependencies avoid importing legacy financial module bodies.', 'ACT':'Sharedfull1709 input layer first. Original M/prior63MAX/breadth/fast/breakout coldparity to existingreference. Neutral only known multiplier->1 and preserves unknown masks,64warm,5/8 coverage,.6/originalMAX. Original financialACT_on context never neutralcalendar.', 'PVR':'All available old8field dates plus968 frozen score days per stock; restfullwarm reference absence retained, no fabricatedoldtable.', 'empty_source':'22 declared no-observation stocks remain NA, never execute unverifiedassembleempty or fill zero.', 'physical_scope':'Reuse existing3fixture18NEUTRAL prefix receipts; no1799x18 rerun. Reader/cutoff/sharedACT minimum checks must be specified in laterexplicitgrant.'},
 implementation_readiness_gaps=['FullACT known-multiplier-preserving wrapper not implemented or validated; must pass truecontrol before expensivefullitembatch.', 'Fullreader/parallel/outputcontroller and pureindustrytrace environmental binding not implemented/source-reviewed yet.', 'No full1709newneutral signals, actualdecision join or fixedtaildiagnostic computed under thisdesign; no newstrategy economic inference.'],
 required_stops=['Any truecold mismatch: preservefailure, globalcomplete prohibited and partialneutral NOT_DIAGNOSTIC_READY; no perSID oldrealI passthrough, silentmaskfix, tolerance or universe shrink.', 'ACT identity or unknownmask mismatch: stop fullbasis, reportfirst/maxdifferences and original parsing/order scope; no originalseries substitution.', 'Budget/incompleteitems: report actualpartialscope and bottleneck under samefreeze; never extendtime/model/fixturecount automatically.'],
 cost_scope=dict(future_workers_max=6,planning_minutes=[25,40],future_hard_wall_seconds=3600,estimated_disk_GiB=[1,2],neutral_full_unit_time_unmeasured=True,estimate_not_runtime_promise=True),
 admission='Root may authorize thin implementation/source review next. This audit is not the root full-export grant, not financial eligibility, not candidate adoption, and does not unblock previously closed A/B/mobile-risk native branches.',reviewer_model_or_account_runs=0,
 inputs={str(p):sha(p)for p in [card,P/'SOURCE_BINDING.json',P/'METADATA_AND_BUDGET.json',Path(__file__)]})
(O/'VOLUME_FULL_EXPORT_DESIGN_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],sources=x['source_SHA_checks'],metadata=x['metadata_independently_counted'],mothers=mothers)))
