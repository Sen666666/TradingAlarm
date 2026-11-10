"""Static source/AST/hash evidence only. Never imports or runs a signal model."""
from pathlib import Path
import hashlib,json,ast
O=Path(__file__).resolve().parent;E=O.parents[1];RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
files={
 'adapter':E/'selection_qualification_closeout_v1/eligibility_source/stock_signal.py',
 'numeric':RR/'pv-participation-response-20261020/code/numeric.py',
 'eligibility':RR/'pv-participation-response-20261020/code/data_utils.py',
 'participation':RR/'pv-participation-response-20261020/code/participation.py',
 'evidence':RR/'pv-strength-b5-20261025/code/evidence.py',
 'arithmetic':RR/'pv-strength-b5-20261025/code/arithmetic.py',
 'E0policy':RR/'pv-strength-b5-20261025/code/policy.py',
 'B4':RR/'pv-strength-b4-20261025/code/model.py',
 'G1':RR/'b5-g1-20261025/code/grade.py',
 'Iproject':RR/'b5-g1-20261025/code/policies_g1.py'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
fpath=E/'full_local_signal_two_dates_v1/2026-01-15/signals/FREEZE.json';freeze=json.loads(fpath.read_text())
for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h
for p in files.values():ast.parse(p.read_text())
s=files['adapter'].read_text();assert 'assert f.segment_id.nunique()==1' in s and 'state,_=participation_frame' in s and "project(e,base,g,'G1_I')" in s
proof={str(p):{'sha256':sha(p),'bytes':p.stat().st_size}for p in files.values()};proof[str(fpath)]={'sha256':sha(fpath),'bytes':fpath.stat().st_size}
(O/'SOURCE_SHA256.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
range_spec={'adapter':[(25,55)],'B4':[(85,93),(163,178),(195,221),(223,255),(277,290),(310,336)],'evidence':[(160,166),(184,200),(227,236)],'G1':[(13,29),(44,63)],'E0policy':[(86,114),(164,180)],'Iproject':[(6,34)],'numeric':[(69,79),(90,128),(129,135)],'eligibility':[(35,58)]}
parts=['# Static source excerpts; no imports/execution\n']
for k,ranges in range_spec.items():
 p=files[k];lines=p.read_text().splitlines()
 for a,b in ranges:parts.append(f'## {k} {p}:{a}\n\n```python\n'+'\n'.join(f'{n:4d} {lines[n-1]}'for n in range(a,b+1))+'\n```\n')
(O/'SOURCE_EXCERPTS.md').write_text('\n'.join(parts))
matrix={
 'status':'PROPOSED_MINIMUM_VALIDATION_NOT_EXECUTED','selection_rule':'20-symbol roster and source origin/version frozen first; no PnL or future winner selection. Cutpoints are validation-only metadata, not historical signal inputs.',
 'layers':[
  {'id':'A','name':'all_daily_export_roundtrip','model_calls_added':0,'scope':'All returned original19 rows from each one full-prefix calculation, including pre2022 control rows until comparison; cache export/reload equals exact returned frame values and null masks. Outer calendar grid only adds missing/invalid metadata, no signal ffill.','claim':'Serialization/filter/join integrity only; not independent daily signal recomputation.'},
  {'id':'B','name':'existing_same_source_three_dates','model_calls_added':0,'scope':'All20 x 2022Jan24/2024Sep24/2026Jan15 original saved19 fields and input identity, preserving absent/unready. No original1709 different-source cache substitutions.','claim':'At most60 source-date comparisons, not 1054-day proof.'},
  {'id':'C1','name':'every_stock_warmup_cut','max_added_full_function_calls':20,'cut':'65th finite-positive C/V strength-valid observation from the same frozen origin; if fewer than65 use actual final available point and mark WARMUP_NOT_CROSSED, not passed warmup.','comparison':'Original calculate(input physically <=cut), compare every common returned19 row and null mask to one full-prefix baseline, including first64 unknown rows. Keep baseline warmup rows even if final user export starts2022.','claim':'Computation-causality sample, not historical source-vintage/PIT proof.'},
  {'id':'C2','name':'every_stock_internal_cut','max_added_full_function_calls':20,'cut':'Predeclare median-position source price observation in2022..May15 available rows, choose a point with at least one later observation; if impossible report NO_INTERIOR_CUT.','comparison':'Every common original19 row, not just end-row, exactly same values/null masks. Source/mask/first origin unchanged.','claim':'20 independent interior prefix checks; not exhaustive every-date truncation.'},
  {'id':'D','name':'bounded_real_boundary_cut_supplement','max_added_full_function_calls':8,'selection':'From baseline raw state/input metadata, first chronological real instance per required branch across frozen20; no gain/loss selection. Deduplicate C cuts.','branches':['first I entry and first grade warm promotion or blocked upgrade','old E0/I floor exit; exit+up same row only if truly observed','positive-price missing/zero/nonfinite volume and first valid successor','price-invalid or absent source row and next price-valid row','explicit source segment boundary, if present'], 'comparison':'Cut at boundary (and next valid observation when necessary), full common-prefix19 equality. If no true fixture mark NOT_EXERCISED; do not invent a PASS. Multi-segment stock_signal input must keep original rejection unless separately authorized adapter contract.','claim':'Finite edge coverage, not universal proof.'}
 ],
 'model_count_if_all_executed':{'one_full_baseline_per_stock':20,'additional_prefix_C':40,'additional_boundary_max':8,'maximum_total_original_calculate_calls':68,'current_review_actual_calls':0},
 'terminal_ledger':'Never broadcast final attrs/ledger to old daily rows. Only per-row19 is main cache. Any optional receipt uses its emitted_at index<=cut and separately retains unresolved_at_cut status; eventual resolved_outcome and final terminal are not prefix equality targets.',
 'remaining_requirement_if_claiming_every_day':'To claim exhaustive independent per-day prefix equality, test every eligible cut or supply separately reviewed formal/independent-online equivalence proof. This finite matrix does not meet that stronger empirical claim.'}
(O/'VALIDATION_MATRIX_PROPOSAL.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n')
audit={
 'status':'PASS_BOUNDED_STATIC_CAUSAL_LAYOUT_REVIEW_WITH_INPUT_DOMAIN_LIMITS','remaining_static_fatal_blocks':[],
 'model_input_domain':'current stock_signal first filters eligible_prices and asserts one remaining source segment; downstream B4/evidence/E0/project support does not widen adapter domain.',
 'static_findings':[
 'B4 vector log normalization uses first same-segment strength-valid close; diff uses preceding value, EW pace recurses from return1. No forward center/bfill in the read computation core.',
 'B4 scale/volume references slice [t-63:t]/[t-21:t]; anchors/extrema/credit update sequentially and refer to <=t positions; each scale permits at most one current confirmation.',
 'Evidence groups explicit source segments and scatters each computed row at its own index; attrs strength terminal and journals are not consumed by classify/project.',
 'G1 keeps previous_grade/prior_extreme/prior_s21; missing strength rows emit unknown without advance, segment change resets. Current return/volume is allowed only after completed close.',
 'E0 and I inspect old floor first, ratchet later, no same-close exit/reentry; current code disables decline memory. Original19 drops terminal/ledger details.',
 'Input-wide validation may reject a full frame with a later malformed/repeated source segment even if an earlier prefix was valid. Static value causality applies to accepted same-domain inputs, not all malformed suffixes.',
 'Fixed source qfq history and source/mask version must be identical: future revised historical factors can invalidate old cache and are not proved PIT by prefix tests.'
 ],
 'three_distinct_tests':['all_daily_output_roundtrip','old_same_source_three_dates','physical_prefix_subset_all_common_rows'],
 'current_test_execution':'NONE; no original model/account or prefix recomputation in this static review.',
 'claim_limits':['No empirical20-stock prefix results exist in this review.','No claim that three stored dates establish all1054 daily prefixes.','No claim of exact resume/incremental checkpoint implementation; current proposal is one full-history calculation then date lookup.','Missing/invalid/segment/exit+up branches require actual evidence or NOT_EXERCISED annotation.'],
 'all11_original_source_hashes_match_previous_freeze':True,'new_full_signal_models':0,'new_numeric_calls':0,'new_accounts':0,
 'source_index_sha256':sha(O/'SOURCE_SHA256.json'),'matrix_sha256':sha(O/'VALIDATION_MATRIX_PROPOSAL.json')}
(O/'STATIC_SOURCE_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':audit['status'],'audit_sha256':sha(O/'STATIC_SOURCE_AUDIT.json'),'matrix_sha256':sha(O/'VALIDATION_MATRIX_PROPOSAL.json'),'current_model_calls':0},ensure_ascii=False))
