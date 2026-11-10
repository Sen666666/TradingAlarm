"""Thin arithmetic/source audit of the existing fixed 25 original layers. No engine imports."""
from pathlib import Path
from decimal import Decimal as D
import gzip, hashlib, json

OUT = Path(__file__).resolve().parent
TASK4 = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4')
ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3')
SOURCE = {}

def read(path):
    path = Path(path)
    data = path.read_bytes()
    SOURCE[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)

rows = read(TASK4 / 'trend_hold_v1/ALL25_PROFIT_PROGRESS_SCALE.json')
summary = read(TASK4 / 'trend_hold_v1/PROFIT_PROGRESS_COVERAGE_BOUND_SUMMARY.json')
paths = read(TASK4 / 'POST_PURCHASE_ALL25_PATHS.json')
native = read('/Users/bytedance/Documents/Codex/2026-11-04/task/loss_correction/no60_behavior_v1/PVR_NO60-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json')
chains = read(TASK4 / 'upside_state_v1/examples_semis/ALL25_SAVED_ROLE_HOLDING_CHAINS.json')
book = read(ROOT / 'entry_quality/trend_exit_controls_v1/runs/BASELINE/strong/pair/B.json.gz')
prior_sha = read(TASK4 / 'upside_state_v1/examples_semis/SOURCE_SHA256.json')
for file in ['READOUT.txt', 'SCOPE.json']:
    p = TASK4 / 'upside_state_v1/examples_semis' / file
    SOURCE[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
producer = TASK4 / 'trend_hold_v1/profit_coverage_bound.py'
SOURCE[str(producer)] = hashlib.sha256(producer.read_bytes()).hexdigest()

checks = []
def check(name, value):
    checks.append({'name': name, 'pass': bool(value)})
    assert value, name

check('all fixed source lists are unique same 25 layer IDs', len(rows) == 25 and len({r['layer'] for r in rows}) == 25 and all({r['layer'] for r in x} == {r['layer'] for r in rows} for x in [paths, native, chains]))
check('fixed 18 actual stocks; 1 core plus 24 mobile', len({r['sid'] for r in rows}) == 18 and sum(r['role'] == 'core' for r in rows) == 1 and sum(r['role'] == 'mobile' for r in rows) == 24)
check('688146 winner case excluded from strict fixed semis25', all(r['sid'] != '688146.SH' for r in rows))
pm, nm, cm = ({r['layer']: r for r in x} for x in [paths, native, chains])
buys = {t['layer']: t for t in book['trades'] if t.get('side') == 'buy'}
for r in rows:
    lid = r['layer']; p, n, c = pm[lid], nm[lid], cm[lid]
    q = D(n['actual_fill']['shares']); price = D(n['actual_fill']['price'])
    floor = D(n['actual_initial_raw_floor'])
    R = q * (price - floor)
    advance = q * D(p['actual_price']) * D(p['maximum_close_gain_during_actual_holding_pct']) / 100
    check(f'{lid}: actual native original buy exact', n['actual_fill'] == buys[lid] == c['actual_buy'])
    check(f'{lid}: original initial raw nominal R', R == D(r['initial_nominal_price_floor_R']) == D(p['initial_nominal_price_to_floor_risk']))
    check(f'{lid}: saved holding maximum folded into entry-share units', advance == D(r['maximum_quoted_close_advance_in_entry_share_units']))
    check(f'{lid}: quotient and all three descriptive flags', advance / R == D(r['maximum_quoted_close_advance_R']) and all(r[k] == v for k, v in [('any_quoted_close_above_fill', advance > 0), ('quoted_advance_at_least_1R', advance >= R), ('quoted_advance_at_least_2R', advance >= 2*R)]))
    check(f'{lid}: original net and closed/open flags not reused as inputs', r['original_lifecycle_net'] == p['net'] and r['original_closed_negative'] == p['closed_net_negative'] and r['original_open'] == bool(p['quantity']))
    check(f'{lid}: quoted progression in readout equals archived record', r == c['progress_descriptive_not_signal'])

hits = [r for r in rows if r['quoted_advance_at_least_1R']]
hit_ids = [r['layer'] for r in hits]
check('exact seven 1R layers, five stocks, all mobile', hit_ids == [674, 677, 684, 737, 1019, 1059, 1079] and len({r['sid'] for r in hits}) == 5 and all(r['role'] == 'mobile' for r in hits))
check('same exact seven also reach fixed descriptive 2R', hit_ids == [r['layer'] for r in rows if r['quoted_advance_at_least_2R']])
negative_hits = [r for r in hits if r['original_closed_negative']]
check('only original negative contact is JieJie737; I request/fill clocks preserved', [r['layer'] for r in negative_hits] == [737] and D(negative_hits[0]['original_lifecycle_net']) == D('-993.9167331026000') and all(x['reason'] == 'I_structure_exit' for x in nm[737]['exit_requests']) and nm[737]['exit_requests'][0]['at'].startswith('2026-03-03') and nm[737]['actual_sells'][0]['at'].startswith('2026-03-04'))
check('saved summary 1R/2R contact IDs and negative count agree', all(summary['groups'][k]['layer_ids'] == hit_ids and summary['groups'][k]['negative_layer_ids'] == [737] for k in ['quoted_advance_at_least_1R', 'quoted_advance_at_least_2R']))
check('net and negative denominator match saved summary', sum(D(r['original_lifecycle_net']) for r in rows) == D('-16783.5804624931475') and sum(r['original_closed_negative'] for r in rows) == 15)
check('source hashes for directly used files remain equal to author manifest', all(SOURCE[p] == sha for p, sha in prior_sha.items() if p in SOURCE))

result = {
    'status': 'PASS_WITH_EXPLICIT_DESCRIPTIVE_SCOPE',
    'checks': checks,
    'fixed_denominator': {'layers': 25, 'stocks': 18, 'core': 1, 'mobile': 24, 'original_negative_layers': 15, 'original_lifecycle_net': '-16783.5804624931475'},
    'original_1R_contacts': {'layer_ids': hit_ids, 'stocks': 5, 'original_negative_layer_ids': [737], 'original_negative_net': '-993.9167331026000', 'same_original_layers_also_reached_2R': True},
    'definition': {
        'R': 'Original initial actual q times (raw actual fill price minus frozen initial floor converted by entry-day factor), pure price nominal reference excluding buy/sell fees.',
        'numerator': 'Original comparable adjusted holding CLOSE peak relative to normalized entry fill, folded into original entry-share monetary units. Reconciled to saved original holding-max field; no new market coverage scan.',
        'clock': 'Original holding peak excludes CLOSE on sell-OPEN date per producer/source contract. This audit rechecks the saved fields and native buy/exit key; it does not cold-recompute all25 price histories.',
        'not': ['Net floating profit', 'Immediately sellable or liquidatable net PnL', 'Cash released', 'Future maximum loss guarantee', 'New candidate position quantity or account profit', 'A threshold chosen or endorsed for current v2 design']
    },
    'scope_separation': '688146.SH is absent from all25 IDs; v2 case electronic-chemicals winner cannot be inserted into this strict fixed semiconductor denominator.',
    'new_accounts': 0, 'new_models': 0, 'new_parameters': 0, 'new_coverage_runs': 0,
    'source_sha256': SOURCE,
}
result['audit_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT / 'TASK4_FIXED25_1R_DEFINITION_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'checks': len(checks), 'contacts': hit_ids, 'output': str(OUT / 'TASK4_FIXED25_1R_DEFINITION_AUDIT.json')}, ensure_ascii=False))
