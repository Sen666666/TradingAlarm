"""Read and quote original source/manifest text only; never import or execute models."""
from pathlib import Path
import ast,hashlib,json

OUT=Path(__file__).resolve().parent
R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
TASK=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
LOCAL=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4')
CP=R/'continuous-protection-lines-20261028/code/model.py'
PV=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
PV_ORIGINAL=R/'pvr-act-comparison-20261027/code/experiment.py'
SOURCE={};INDEX=[]
def sha(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def bind(p):p=Path(p);SOURCE[str(p)]=sha(p);return p
def readj(p):return json.loads(bind(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def excerpt(name,p,first,last,meaning):
 p=bind(p);lines=p.read_text().splitlines(keepends=True);assert 1<=first<=last<=len(lines)
 text=''.join(lines[first-1:last]);target=OUT/'snippets'/(name+'.py.txt');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
 INDEX.append(dict(name=name,path=str(p),first_line=first,last_line=last,source_file_sha256=SOURCE[str(p)],snippet_path=str(target),snippet_sha256=sha(target),verbatim_line_slice=True,meaning=meaning))

excerpt('CP_constants_features_calculate',CP,1,58,'Original CP1 constants, input validation, lagged numeric features and market receipt state machine. No call made.')
excerpt('CP_project_shadow_only_not_native',CP,60,72,'Original price-only absorbing shadow; not substituted for actual No60 joint MOBILE management.')
excerpt('CP_stock_input_native_frame',W/'case-stock-cp1-warmup-20261031/generate.py',5,28,'Actual reusable stock CP input: e0_valid is assigned i_target; negative original event feeds e0_down.')
excerpt('CP_stock_input_older_common_frame',R/'continuous-protection-lines-20261028/code/common.py',5,24,'Older source uses same stock e0_valid=i_target mapping and checks CNY amount.')
excerpt('CP_universe_prepare_wiring',W/'universe-cp1-inputs-20261031/prepare.py',5,45,'Manifest refs and original calculate(q) or exact old cache reuse. Quoted only; never run.')
excerpt('CP_receipt_identity_trace',W/'cp1-evidence-trace-20261031/trace.py',10,65,'Receipt ids, source/episode identity, no repeated underlying advance ids, known-day vs unknown live-publication time.')
excerpt('PVR_actual_frozen_formula',PV,1,19,'The exact actual numeric PVR used by frozen score manifests.')
excerpt('PVR_original_source_score_function',PV_ORIGINAL,24,42,'Verbatim ancestor score function from which the current formula was AST-extracted.')
excerpt('PVR_verbatim_formula_extraction_provenance',W/'pvr-current-v3-information-capital-20261101/prepare_only.py',30,43,'Source AST extraction of exact original score body; quoted only, not executed.')
excerpt('PVR_export_formula_binding',W/'pvr-slot1-native-readiness-20261101/export_scores.py',8,25,'Frozen formula filename and expected SHA.')
excerpt('PVR_export_source_and_calendar_mapping',W/'pvr-slot1-native-readiness-20261101/export_scores.py',28,90,'Actual score source from original signal.parquet; full source warming then exact-date reindex; no score recomputation here.')
excerpt('PVR_actual_cache_reader',W/'pvr-slot1-native-readiness-20261101/native_rank.py',20,45,'FrozenScores validates manifest/file SHA; exact stock/day lookup; finite values or None, no forward fill.')
excerpt('PVR_unique_stock_slot_substitution',W/'pvr-slot1-native-readiness-20261101/native_rank.py',47,91,'Only ready scores reorder already-native intents within ready-stock slots; missing scores preserve original positions.')
excerpt('PVR_native_planning_order',W/'pvr-slot1-native-readiness-20261101/native_rank.py',94,120,'Original J.planning runs to completion before PVR rank substitution; actual opening and route identity assertions.')
excerpt('No60_effective_wiring',TASK/'pvr_pool_feasibility/native_adapter.py',6,40,'No60 retains native_rank planning and joint opening while only capital-budget implementation is substituted.')
excerpt('Original_CP_I_eligibility_and_protection',W/'case-stage-ledger-20261031/v3/joint_v3.py',213,259,'Original eligibility, ACT/I and preceding-CP exit priority, layer floor update, CORE/MOBILE roles and sized pending list before PVR.')
excerpt('Trade_pvr_legacy_field_is_meta_score',R/'probe-pyramid-pilot-20261029/code/pilot.py',59,73,'Original trade field named pvr is meta[score], which native_rank leaves unchanged as original H1 compatibility score; use frozen intent.PVR_score or rank-policy.PVR for actual new PVR.')
excerpt('Original_next_OPEN_consumes_frozen_rank',W/'case-stage-ledger-20261031/v3/joint_v3.py',302,324,'Next OPEN executes exits first and then sorted frozen pending rank/core first, rechecking execution and budgets.')
excerpt('Actual_long_strong_manifest_selection',LOCAL/'new_price_trend_v1/funding/input_loader.py',12,17,'Actual long2022-24 uses extended2024 score manifest, strong2025-26 uses native default manifest.')
excerpt('Actual_account_CP_cache_loading',LOCAL/'new_price_trend_v1/funding/input_loader.py',27,52,'Original facts/CP input/output same-index and exact-column checks; receipt equality checked with frozen canonical manifests.')
excerpt('Actual_score_configure_before_full',LOCAL/'new_price_trend_v1/funding/run_entry.py',146,160,'Historical runner selects per-window score manifest. Quoted, not executed.')
excerpt('Actual_OFF_planning_delegation',LOCAL/'new_price_trend_v1/funding/entry_adapter.py',113,120,'OFF original No60 delegates native_rank planning; new BB gate is not an effective OFF rule.')
excerpt('Extended2024_score_builder_wiring',TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/prepare_data.py',7,14,'Actual long-window extended score formula and input wiring.')
excerpt('Extended2024_score_output_metadata',TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/prepare_data.py',96,111,'Original same-formula full-warm score export and per-file metadata. Quoted only.')
excerpt('Extended2024_score_manifest_metadata',TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/prepare_data.py',123,127,'2022+2023+2024 manifest construction and cutoff.')

# AST parsing verifies provenance as text only: never compile, exec or import source.
source=bind(PV_ORIGINAL).read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)and n.name=='score')
raw='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n'
formula=bind(PV).read_text()
assert raw==formula
EXPECTED='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
assert SOURCE[str(PV)]==EXPECTED
save('TEXT_PROVENANCE_CHECK.json',dict(original_score_path=str(PV_ORIGINAL),original_score_lines=[node.lineno,node.end_lineno],formula_path=str(PV),exact_text_match=True,formula_sha256=EXPECTED,method='AST parse and text equality only; no formula evaluation'))

manifest_paths={
 'strong':W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json',
 'long':TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json',
}
selected=[]
for window,p in manifest_paths.items():
 m=readj(p);assert m['formula_sha256']==EXPECTED
 keep={k:v for k,v in m.items()if k not in ['entries','fixed_stock_ids','decision_calendars']}
 keep['manifest_path']=str(p);keep['manifest_sha256']=SOURCE[str(p)];keep['decision_calendar_lengths']={k:len(v['dates']if isinstance(v,dict)else v)for k,v in m['decision_calendars'].items()};keep['fixed_id_count']=len(m['fixed_stock_ids']);keep['window_label']=window
 keep['selected_cached_entries']=[]
 for sid in ['300666.SZ','301611.SZ','603061.SH','605358.SH']:
  row=next(r for r in m['entries']if r['symbol']==sid);score=bind(p.parent/'scores'/(sid+'.parquet'));sourcepath=bind(row['source'])
  assert SOURCE[str(score)]==row['output_sha256'] and SOURCE[str(sourcepath)]==row['source_sha256']
  keep['selected_cached_entries'].append(dict(**row,score_cache_path=str(score),actual_score_cache_sha256=SOURCE[str(score)],actual_source_sha256=SOURCE[str(sourcepath)],byte_hashes_match_manifest=True,cache_not_evaluated=True))
 selected.append(keep)
save('ACTUAL_SCORE_MANIFEST_BINDINGS.json',selected)

formula_json=readj(R/'pv-rank-q1-20261027/FORMULA.json')
save('ORIGINAL_FORMULA_DECLARATION.json',dict(source_path=str(R/'pv-rank-q1-20261027/FORMULA.json'),source_sha256=SOURCE[str(R/'pv-rank-q1-20261027/FORMULA.json')],verbatim_JSON_values=formula_json,warning='Historical declaration ranking/missing rule differs from later native_slot implementation; actual native_rank is authoritative for current slot behavior.'))
freeze=readj(W/'universe-cp1-inputs-20261031/FREEZE.json')
assert freeze['source_sha256'][str(CP)]==SOURCE[str(CP)]
save('CP_MODEL_MANIFEST_BINDING.json',dict(model_path=str(CP),model_actual_sha256=SOURCE[str(CP)],expected_in_original_CP_cache_freeze=freeze['source_sha256'][str(CP)],exact_byte_hash_match=True,original_freeze=str(W/'universe-cp1-inputs-20261031/FREEZE.json'),original_freeze_sha256=SOURCE[str(W/'universe-cp1-inputs-20261031/FREEZE.json')],original_cache_window=freeze['cache_window'],no_model_called=True))
save('UNIVERSE_SNAPSHOT_SCOPE.json',dict(source_path=str(W/'universe-cp1-inputs-20261031/FREEZE.json'),source_sha256=SOURCE[str(W/'universe-cp1-inputs-20261031/FREEZE.json')],not_PIT=freeze.get('not_PIT'),stock_count=len(freeze.get('stocks',[])),industry_count=len(freeze.get('industries',[])),note='PVR numeric function does not read industry labels, but fixed universe/eligibility/budget industry mapping is not a historical PIT membership proof.'))
save('SNIPPET_INDEX.json',INDEX)
alias_parts=[]
for name,p,first,last in [
 ('1. Intent.score is the original H1 compatibility value',W/'case-stage-ledger-20261031/v3/joint_v3.py',255,255),
 ('2. PVR substitutes rank and adds PVR_score; original score is asserted unchanged',W/'pvr-slot1-native-readiness-20261101/native_rank.py',77,91),
 ('3. Trade.pvr is written from meta[score], not PVR_score',R/'probe-pyramid-pilot-20261029/code/pilot.py',59,73)]:
 p=bind(p);text=''.join(p.read_text().splitlines(keepends=True)[first-1:last])
 alias_parts.append(name+'\n'+str(p)+f':{first}-{last}\nSHA256 '+SOURCE[str(p)]+'\n'+text)
alias='最先澄清字段名：book trade.pvr并非新PVR评分，而是原intent.score/H1兼容字段。\n真正PVR看冻结intent.PVR_score、rank-policy.PVR或本账户所绑定的score缓存score列。\n以下三段是原样切片，未改任何字节；只有段间标题和路径行由本提取器添加。\n\n'+'\n'.join(alias_parts)
(OUT/'ALIAS_THREE_VERBATIM.txt').write_text(alias)
evidence_path=LOCAL/'review_924_v1/rules/OCT9_10_ACTUAL_ADMISSION_EVIDENCE.json';ev=readj(evidence_path)
wanted={'300085.SZ','300339.SZ','301236.SZ','688593.SH'}
four=[{k:r.get(k)for k in ['sid','role','score','PVR_score','PVR_ready','original_H1_rank','priority_rank']}for r in ev['signal_CLOSE']['actual_next_OPEN_filled_intents']if r['sid']in wanted]
assert len(four)==4
save('LEGACY_ALIAS_924_FOUR_SAVED_INTENTS.json',dict(scope='Only four already-saved original frozen-intent rows; no new cache/model/account calculation',source_path=str(evidence_path),source_sha256=SOURCE[str(evidence_path)],rows=four,conclusion='Four high true PVR values exist in frozen PVR_score. Historical high-PVR statement can cite these fields, never trade.pvr alone. Old report/account untouched.'))
if(OUT/'SHORT_GUIDE.txt').exists():(OUT/'READOUT.txt').write_text(alias+'\n\n'+(OUT/'SHORT_GUIDE.txt').read_text())
SOURCE[str(Path(__file__).resolve())]=sha(__file__)
save('SOURCE_SHA256.json',SOURCE)
save('SCOPE.json',dict(status='SOURCE_TEXT_AND_FROZEN_MANIFEST_EXTRACTION_COMPLETE',source_snippets=len(INDEX),new_account_or_market_instances=0,new_model_or_indicator_calls=0,new_builds=0,new_backtests=0,new_financial_replays=0,parsed_AST_only=True,cached_scores_read_as_bytes_only=True,original_source_or_caches_modified=False))
print(json.dumps(dict(snippets=len(INDEX),source_files_hashed=len(SOURCE),new_builds=0,new_indicators=0,new_accounts=0),ensure_ascii=False))
