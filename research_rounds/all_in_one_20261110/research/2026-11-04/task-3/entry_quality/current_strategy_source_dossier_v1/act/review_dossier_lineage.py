"""Static file/text provenance only. Does not import any strategy module."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def read(p):
    return Path(p).read_text()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def load(p):
    return json.loads(read(p))


checks = []
sources = {}


def verify(p, expected, context):
    actual = sha(p)
    assert actual == expected, (context, str(p), expected, actual)
    sources[str(Path(p).resolve())] = actual
    checks.append(dict(context=context, path=str(p), exact=True))


# Confirm every cited source identity. Hashing a stored book is not reading its
# financial fields, executing a model, or rechecking the owner's arithmetic.
a = load(ROOT / 'act/SOURCE_SHA256.json')
for p, h in a['source_sha256'].items():
    verify(p, h, 'ACT source identity')
verify(ROOT / 'act/EVIDENCE.md', a['evidence_sha256'], 'ACT evidence')

e = load(ROOT / 'e0_i/SOURCE_SHA256.json')
e_doc = read(ROOT / 'e0_i/EVIDENCE.md')
e_count = 0
for p, r in e['source_files'].items():
    verify(p, r['sha256'], 'E0/I source identity')
    lines = read(p).splitlines()
    assert len(lines) == r['lines']
    for lo, hi in r['excerpt_ranges']:
        exact = '\n'.join(f'{i:4d} {lines[i-1]}' for i in range(lo, hi + 1))
        assert exact in e_doc, ('E0/I excerpt', p, lo, hi)
        e_count += 1
for p, h in e['manifest_sha256'].items():
    verify(p, h, 'E0/I frozen provenance manifest')
verify(e['evidence']['path'], e['evidence']['sha256'], 'E0/I evidence')
for r in e['exact_existing_identity_bindings']:
    assert r['exact'] is True and r['expected_sha256'] == r['actual_sha256']
    verify(r['path'], r['expected_sha256'], r['binding'])
assert e_count == e['excerpt_count']

c = load(ROOT / 'cp_pvr/SOURCE_SHA256.json')
for p, h in c.items():
    verify(p, h, 'CP/PVR source identity')
c_doc = read(ROOT / 'cp_pvr/EVIDENCE.md')
c_index = load(ROOT / 'cp_pvr/EXCERPT_INDEX.json')['excerpts']
for r in c_index:
    exact = '\n'.join(read(r['path']).splitlines()[r['first_line']-1:r['last_line']])
    assert exact in c_doc, ('CP/PVR excerpt', r)

pos = load(ROOT / 'position_execution/SOURCE_SHA256.json')
by_alias = {r['alias']: r for r in pos['source_files']}
for r in pos['source_files'] + pos['effective_texts'] + [pos['evidence']]:
    verify(r['path'], r['sha256'], 'Position/execution source identity')
    assert Path(r['path']).stat().st_size == r['bytes']

# Read only AST literals; never evaluate imports, calls, compile, or exec from P.
p_source = read(by_alias['P']['path'])
constants = {}
for node in ast.parse(p_source).body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        name = getattr(node.targets[0], 'id', '')
        if name in {'MG', 'PG', 'PN', 'RG', 'RN'}:
            constants[name] = ast.literal_eval(node.value)
model = read(by_alias['MODEL']['path'])
route = read(by_alias['ROUTE']['path'])
assert model.count(constants['MG']) == model.count(constants['PG']) == 1
assert route.count(constants['RG']) == 1
derived_model = model.replace(constants['MG'], '').replace(constants['PG'], constants['PN'])
derived_route = route.replace(constants['RG'], constants['RN'])
assert derived_model == read(ROOT / 'position_execution/EFFECTIVE_NO60_MODEL_SOURCE.txt')
assert derived_route == read(ROOT / 'position_execution/EFFECTIVE_NO60_ROUTE_SOURCE.txt')

pv = load(ROOT / 'cp_pvr/PVR_RUNTIME_CACHE_LINEAGE.json')
origin = pv['origin_score_function']
original_lines = read(origin['path']).splitlines(keepends=True)
original_function = ''.join(original_lines[origin['first_line']-1:origin['last_line']])
assert original_function == read(origin['verbatim_extracted_copy'])
verify(origin['verbatim_extracted_copy'], origin['extracted_function_sha256'], 'PVR original formula text')
for r in pv['active_runtime_bindings']:
    verify(r['active_manifest_path'], r['manifest_sha256'], 'Current PVR manifest: ' + r['window'])
    verify(r['completed_baseline_run_metadata'], r['run_metadata_sha256'], 'Completed baseline metadata: ' + r['window'])
    manifest = load(r['active_manifest_path'])
    assert r['formula_sha256'] == origin['extracted_function_sha256']
    assert r['formula_sha256'] in json.dumps(manifest)
    metadata = load(r['completed_baseline_run_metadata'])
    assert metadata['arm'] == 'BASELINE' and metadata['window'] == r['window']
    for p, exact in r['current_loader_and_adapter_bytes_match_recorded_run'].items():
        assert exact is True and metadata['source_freeze'][p] == sha(p)
    sample = r['sample_cached_file']
    verify(sample['path'], sample['bytes_sha256'], 'PVR single cache identity, not numerical values')
    assert sample['manifest_output_sha256'] == sample['bytes_sha256']
    assert r['runtime_evaluates_score_function'] is False

y = load(ROOT / 'yingxin_chain/SOURCE_MANIFEST.json')
for p, h in y['source_sha256'].items():
    verify(p, h, 'Yingxin input identity; no financial recomputation')
for p, h in load(ROOT / 'yingxin_chain/DELIVERABLE_SHA256.json').items():
    verify(ROOT / 'yingxin_chain' / p, h, 'Yingxin stored deliverable identity')
assert load(ROOT / 'yingxin_chain/VALIDATION.json')['status'].startswith('PASS')

first = load(ROOT / 'READ_FIRST_SOURCE_SHA256.json')
first_doc = read(ROOT / 'READ_FIRST.md')
for r in first:
    verify(r['path'], r['sha256'], 'Root read-first source identity')
    exact = '\n'.join(read(r['path']).splitlines()[r['start_line']-1:r['end_line']])
    assert exact in first_doc, ('Root read-first excerpt', r)

artifact_paths = [ROOT / 'READ_FIRST.md', ROOT / 'READ_FIRST_SOURCE_SHA256.json']
for directory in ('act', 'e0_i', 'cp_pvr', 'position_execution', 'yingxin_chain'):
    artifact_paths.append(ROOT / directory / 'EVIDENCE.md')
    artifact_paths.extend(p for p in (ROOT / directory).glob('*.json') if p.name not in {
        'DOSSIER_LINEAGE_REVIEW.json', 'DOSSIER_LINEAGE_REVIEW_SHA256.json'})

result = {
    'status': 'PASS_CURRENT_NO60_STATIC_SOURCE_LINEAGE_ONLY',
    'scope': 'Current archived BASELINE No60, 2022_2024 and strong. Static source, literal AST/text, manifest and file-byte identities only.',
    'remaining_blocks': [],
    'source_identity_checks': len(checks),
    'unique_source_identities': len(sources),
    'e0_i_numbered_source_excerpts_exact': e_count,
    'cp_pvr_source_excerpts_exact': len(c_index),
    'root_read_first_source_excerpts_exact': len(first),
    'effective_no60_model_and_route_exact_by_literal_substitution': True,
    'runtime_chain': [
        'run_account(BASELINE) selects A.Runner after V.inputs, not an early/H2/ETA adapter.',
        'A.Runner -> N.Runner -> BASE.Runner -> L.PreparedRunner -> J.Runner; N.planning calls J.planning then changes pending priority.',
        'A keeps J.opening, N.planning; its route is P.ROUTES[True]. Its budget request and migrate are P.MOD.Contract functions, other budget state/methods remain inherited.',
        'PreparedRunner.run_prepared replaces risk_policy.RECOVERY with actual M.O/recovery.csv before daily events. J.planning passes ACT20_BREAK explicitly.',
        'E0/I and CP formula/trace files are cached-input producers; runtime reads cached facts/CP and canonical receipts. PVR runtime FrozenScores reads the two actual window manifests, not score() each decision.'
    ],
    'important_distinctions': [
        'Default engine RISK_MODE=CONTROL and risk_policy.override are not the current J explicit ACT20_BREAK planning path.',
        'ACT peak updates while on; paused recovery requires flat and current-day BREAK63; resume resets peak to NAV and increments episode. It is not a single immutable whole-history NAV floor.',
        'Current active RECOVERY is mainline-absolute-Q4-20261031/recovery.csv in both baseline metadata records, not the policy module default CSV.',
        'Original J route account3% and confirmed60 predicates are overridden in current No60. P.State/snapshot/plan projection helpers are not current account planning.',
        'S0 eligibility call is active; old sector rotation helpers are not the current stock ordering. H1 order is followed by PVR unique-stock slots.',
        'CORE has upstream G1_I old-floor exit through I_target=False and J all-stock I exit. Absence of a duplicate CORE direct floor comparison is not absence of a price exit.',
        'actual_buy.pvr is original H1 metadata score; frozen_intent.PVR_score and rank-policy fields hold actual priority.',
        'Yingxin chain reads original book for actual transactions; its older v2 case input is a raw original-field carrier with explicit whitelists, not new B/grant/quantity policy. This review does not re-audit its financial values.'
    ],
    'artifacts_bound': {str(p.resolve()): sha(p) for p in sorted(set(artifact_paths))},
    'source_sha256': sources,
    'checks': checks,
    'limits': [
        'No fresh runtime module import or instrumentation. Runtime attribution is static alias/class/call reading plus existing completed baseline metadata identities.',
        'No strategy functions, project, derive, score, recovery generation, account or model executed. No indicators, cache values, trading amounts, synthetic cases or outcomes recomputed.',
        'Source/cache provenance is not a historical point-in-time input certification. No claim of economic effectiveness or proposed policy approval.',
        'The quoted chain financial extraction remains its owner\'s original-source evidence; this independent review confirms lineage and byte identities only.'
    ],
    'new_strategy_imports': 0,
    'new_model_calls': 0,
    'new_accounts': 0,
    'new_backtests': 0,
    'new_parameter_searches': 0,
    'new_price_path_simulations': 0,
    'reviewer_source_sha256': sha(__file__)
}
(OUT / 'DOSSIER_LINEAGE_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('status', 'source_identity_checks', 'unique_source_identities', 'e0_i_numbered_source_excerpts_exact', 'cp_pvr_source_excerpts_exact', 'root_read_first_source_excerpts_exact', 'remaining_blocks')}, ensure_ascii=False))
