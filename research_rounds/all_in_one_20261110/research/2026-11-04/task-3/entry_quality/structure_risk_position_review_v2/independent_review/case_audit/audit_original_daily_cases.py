"""Read-only independent checks of two saved original timelines; no replacement policy."""
from pathlib import Path
from decimal import Decimal as D
import csv, gzip, hashlib, json, math
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CASES = ROOT / 'structure_risk_position_review_v2/cases'
SOURCE, CHECKS, RISK_ROWS, FINDINGS, CARRIED_SOURCE_DAYS = {}, [], [], [], []
Z = D(0)

def sha(p):
    p = Path(p); h = hashlib.sha256(p.read_bytes()).hexdigest(); SOURCE[str(p)] = h; return h

def read(p):
    p = Path(p); sha(p)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f:
        return [json.loads(line) for line in f] if '.jsonl' in p.name else json.load(f)

def check(name, condition):
    CHECKS.append({'name': name, 'pass': bool(condition)})
    assert condition, name

def equal_money(name, a, b):
    # Sources use Decimal precision28; arithmetic reorder can round below 1e-20 CNY.
    check(name, abs(D(str(a)) - D(str(b))) <= D('1e-20'))

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, pd.Timestamp): return str(x)
    if hasattr(x, 'item'): x = x.item()
    return None if isinstance(x, float) and not math.isfinite(x) else x

manifest = read(CASES / 'SOURCE_MANIFEST.json')
for output_name in ['READOUT.txt', 'KEY_DATES_FOR_REVIEW.json', 'INDEX_AND_VALIDATION.json']:
    sha(CASES / output_name)
for p, expected in manifest['sources'].items():
    check('author source bytes unchanged: ' + p, sha(p) == expected)
check('extractor source bytes match author manifest', sha(CASES / 'extract_cases.py') == manifest['script_sha256'])
spec = read(CASES / 'PROTOCOL.json')
stock_manifest_path = next(p for p in manifest['sources'] if p.endswith('/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))
stock_manifest = {r['symbol']: r for r in read(stock_manifest_path)}
annual_manifest_path = next(p for p in manifest['sources'] if p.endswith('/2022-normal-reference-20261031/inputs/MANIFEST.json'))
annual_manifest = {r['sid']: r for r in read(annual_manifest_path)}
summaries = []

for case_spec in spec['selected_cases']:
    sid, win = case_spec['sid'], case_spec['window']
    ids = set(case_spec['original_layers'])
    stem = sid.replace('.', '_')
    case = read(CASES / (stem + '_DAILY_PAPER_INPUTS.json'))
    base = ROOT / 'trend_exit_controls_v1/runs/BASELINE' / win / 'pair'
    book, native_days = read(base / 'B.json.gz'), read(base / 'daily.jsonl.gz')
    days = {r['at'][:10]: r for r in native_days}
    lm = {r['id']: r for r in book['layers']}
    buys = {r['layer']: r for r in book['trades'] if r['side'] == 'buy' and r.get('layer') in ids}
    check(sid + ': selected buy IDs exact', set(buys) == ids)
    m = stock_manifest[sid]
    fp, cp = Path(m['refs']['facts']), Path(m['refs']['CP1'])
    signal = next(Path(p) for p in m['source_sha256'] if p.endswith('/signal.parquet'))
    event = next(Path(p) for p in m['source_sha256'] if p.endswith('/events.parquet'))
    ix = Path(next(p for p in m['source_sha256'] if p.endswith('/ix-a-share-entry-20261025/signals/' + sid + '.parquet')))
    frames = {key: pd.read_parquet(path) for key, path in [('facts', fp), ('CP', cp), ('bar', signal), ('event', event), ('G1', ix)]}
    for p in [fp, cp, signal, event, ix]: sha(p)
    rp = Path(annual_manifest[sid]['output_path']) if win == '2022_2024' else Path(m['refs']['receipts'])
    receipts = {r['confirmed_day']: r for r in read(rp)}
    # Read original boolean history only, without replaying I or CP.
    roots = {}; last_on = False; last_segment = None; active_root = None
    for idx, row in frames['facts'].iterrows():
        on, segment = bool(row.i_target), row.segment_id
        if on and (not last_on or segment != last_segment): active_root = str(idx.date())
        roots[str(idx.date())] = active_root if on else None
        last_on, last_segment = on, segment
    selected = {r['native']['id']: r for r in case['selected_actual_layers']}
    for lid in ids:
        check(f'{sid}/{lid}: original native terminal and actual buy exact', selected[lid]['native'] == lm[lid] and selected[lid]['original_buy'] == buys[lid])
        check(f'{sid}/{lid}: no partial/corporate-action quantity assumption hidden', all(p['shares'] == buys[lid]['shares'] for t in book['trades'] if t['side'] == 'sell' for p in t.get('parts', []) if p['layer'] == lid) and lm[lid]['initial_qty'] == buys[lid]['shares'])
    expected_calendar = [r['at'][:10] for r in native_days if case_spec['start'] <= r['at'][:10] <= case_spec['end']]
    check(sid + ': every original native CLOSE retained', [r['day'] for r in case['days']] == expected_calendar)
    csv_rows = list(csv.DictReader((CASES / (stem + '_DAILY.csv')).open()))
    check(sid + ': CSV same complete calendar', [r['day'] for r in csv_rows] == expected_calendar)
    prior_native = {}
    raise_keys = []
    for d in native_days:
        day = d['at'][:10]
        if day < case_spec['start']:
            prior_native = {r['id']: r for r in d['layers'] if r['id'] in ids}; continue
        if day > case_spec['end']: break
        a = case['days'][expected_calendar.index(day)]
        check(sid + '/' + day + ': no future source clocks', all(v <= day for v in a['source_days'].values()))
        for frame_key, out_key in [('facts', 'original_stock_facts'), ('bar', 'original_bar'), ('G1', 'original_G1'), ('event', 'original_native_event'), ('CP', 'original_CP_cache')]:
            frame = frames[frame_key]
            if frame_key in ['CP', 'event']:
                expected_row = clean(frame.loc[pd.Timestamp(day)].to_dict()) if pd.Timestamp(day) in frame.index else {}
            else:
                idx = frame.index[frame.index <= pd.Timestamp(day)][-1]
                source_key = {'facts': 'facts', 'bar': 'price_volume', 'G1': 'G1'}[frame_key]
                check(f'{sid}/{day}: {frame_key} exact past observed clock', a['source_days'][source_key] == str(idx.date()))
                expected_row = clean(frame.loc[idx].to_dict())
            check(f'{sid}/{day}: {frame_key} saved exact causal source row', expected_row == a[out_key])
        if any(v < day for v in a['source_days'].values()):
            CARRIED_SOURCE_DAYS.append({'sid': sid, 'native_CLOSE_day': day, 'last_known_source_days': a['source_days'], 'new_CP_not_invented': not a['original_CP_cache'].get('receipt', False)})
        f, c = a['original_stock_facts'], a['original_CP_cache']
        check(sid + '/' + day + ': canonical CP receipt and I-root are causal source fields', receipts.get(day) == a['original_CP_canonical_receipt'] and roots[a['source_days']['facts']] == a['original_I_root_start'])
        if c.get('receipt', False):
            check(sid + '/' + day + ': receipt candidate/source-day tied', receipts[day]['confirmed_day'] == day and abs(D(str(receipts[day]['original_candidate'])) - D(str(c['candidate']))) < D('1e-12'))
        live = {r['id']: r for r in d['layers'] if r['id'] in ids}
        out_live = {r['layer']: r for r in a['original_live_layers']}
        check(sid + '/' + day + ': every native live selected layer retained', set(live) == set(out_live))
        check(sid + '/' + day + ': original account/pending clock exact', a['original_account']['pending_sell_sids'] == d['pending_sells'] and a['original_account']['NAV'] == d['nav'] and a['original_account']['ACT_on'] == d['on'])
        audit_today = [r for r in book['audit'] if r.get('sid') == sid and r.get('at', '')[:10] == day]
        check(sid + '/' + day + ': actual audit events exact', audit_today == a['original_audit_today'])
        same_buys = [t for t in buys.values() if t['at'][:10] == day]
        same_sells = [t for t in book['trades'] if t['side'] == 'sell' and t['security_id'] == sid and t['at'][:10] == day and any(p['layer'] in ids for p in t['parts'])]
        check(sid + '/' + day + ': original OPEN trades exact', a['original_OPEN_buys'] == same_buys and a['original_OPEN_sells'] == same_sells)
        total_mark = total_basis = total_before = total_after = total_reduction = known_ar = Z
        for lid, h in live.items():
            x = out_live[lid]; q = D(h['qty']); b = D(buys[lid]['gross_cny']) + D(buys[lid]['fees_cny'])
            check(f'{sid}/{day}/{lid}: actual native daily layer exact', x['saved_native_layer'] == h)
            check(f'{sid}/{day}/{lid}: selected live q unchanged; no pending sold treated flat', h['qty'] == buys[lid]['shares'])
            prior = prior_native.get(lid)
            old = D(str(prior.get('last_core_line', prior['floor']) if h['kind'] == 'core' else prior['floor'])) if prior else D(buys[lid]['floor'])
            post = D(str(h.get('last_core_line', h['floor']) if h['kind'] == 'core' else h['floor']))
            factor, raw = D(str(f['factor'])), D(str(f['raw_close']))
            raw_old, raw_new = old / factor, post / factor
            before, after = q * max(Z, raw - raw_old), q * max(Z, raw - raw_new)
            principal_before, principal_after = max(Z, b - q * raw_old), max(Z, b - q * raw_new)
            equal_money(f'{sid}/{day}/{lid}: fee-aware remaining actual basis', x['fee_aware_remaining_original_basis'], b)
            for k, value in [('guard_before_CLOSE_check_adjusted', old), ('guard_after_original_CLOSE_adjusted', post), ('guard_before_CLOSE_check_raw', raw_old), ('guard_after_original_CLOSE_raw', raw_new), ('native_mark_to_guard_before_check', before), ('native_mark_to_guard_after_checks', after), ('reference_principal_shortfall_to_saved_guard', principal_after), ('mark', q*raw), ('held_unreal', q*raw-b)]:
                equal_money(f'{sid}/{day}/{lid}: {k}', x[k], value)
            requests = [r for r in book['audit'] if r.get('sid') == sid and r.get('kind') == 'pilot_layer_exit' and lid in r['layers'] and r['at'] <= d['at']]
            check(f'{sid}/{day}/{lid}: original layer exit latch causal prefix', x['original_layer_exit_latched_at_CLOSE'] == bool(requests) and x['latched_requests'] == requests)
            check(f'{sid}/{day}/{lid}: no exit pending ratchet', not requests or post == old)
            if h['kind'] == 'add':
                expected = old
                if not requests and d['on'] and f['i_target'] and D(str(f['close'])) > old:
                    if f['i_floor'] is not None: expected = max(expected, D(str(f['i_floor'])))
                    if c.get('receipt', False): expected = max(expected, D(str(c['candidate'])))
                equal_money(f'{sid}/{day}/{lid}: mobile old-line-before-ratchet source formula', post, expected)
            elif h['kind'] == 'core':
                expected = D(str(f['i_floor'])) if d['on'] and f['i_target'] and f['i_floor'] is not None else old
                equal_money(f'{sid}/{day}/{lid}: CORE last-decision-known I reference', post, expected)
            advanced = post > old
            check(f'{sid}/{day}/{lid}: genuine actual guard advance flag', x['guard_true_numeric_advance'] == advanced)
            expected_sources = []
            if advanced:
                if f['i_floor'] is not None and abs(post - D(str(f['i_floor']))) <= D('1e-9') * max(D(1), abs(post)): expected_sources.append('original_I_floor')
                if c.get('receipt', False) and abs(post - D(str(c['candidate']))) <= D('1e-9') * max(D(1), abs(post)): expected_sources.append('original_CP_receipt_candidate')
                raise_keys.append((day, lid))
            check(f'{sid}/{day}/{lid}: saved guard advance source match', x['matching_same_CLOSE_raise_sources'] == expected_sources)
            reduction = before - after if advanced else Z
            equal_money(f'{sid}/{day}/{lid}: marked reference difference only', x['reference_mark_risk_reduced_by_guard_advance'], reduction)
            RISK_ROWS.append({'sid': sid, 'day': day, 'layer': lid, 'qty_original': str(q), 'old_floor_adjusted': str(old), 'new_floor_adjusted': str(post), 'raw_close': str(raw), 'raw_old_floor': str(raw_old), 'raw_new_floor': str(raw_new), 'basis_paid_buy_fee_inclusive': str(b), 'marked_reference_before': str(before), 'marked_reference_after': str(after), 'marked_reference_decrease': str(reduction), 'basis_to_floor_positive_shortfall_before': str(principal_before), 'basis_to_floor_positive_shortfall_after': str(principal_after), 'basis_to_floor_positive_shortfall_decrease': str(principal_before-principal_after), 'is_grant_or_designer_kappa': False})
            total_mark += q*raw; total_basis += b; total_before += before; total_after += after; total_reduction += reduction; known_ar += D(h['dividend'])
        for k, value in [('original_stock_mark', total_mark), ('original_stock_remaining_basis', total_basis), ('original_stock_held_unreal', total_mark-total_basis), ('original_mark_to_guard_before_CLOSE', total_before), ('original_mark_to_guard_after_CLOSE', total_after), ('true_guard_advance_reference_risk_reduction', total_reduction), ('original_selected_campaign_known_AR', known_ar)]:
            equal_money(sid + '/' + day + ': stock total ' + k, a[k], value)
        # Only cash events already executed by this CLOSE, no terminal label fills the prefix.
        actual_cash = sum((-D(t['gross_cny'])-D(t['fees_cny']) for t in buys.values() if t['at'] <= d['at']), Z)
        actual_cash += sum((D(p['net_cash']) for t in book['trades'] if t['side'] == 'sell' and t['at'] <= d['at'] for p in t['parts'] if p['layer'] in ids), Z)
        equal_money(sid + '/' + day + ': wealth uses only original prefix cash plus live mark and AR', a['original_selected_campaign_known_wealth'], actual_cash+total_mark+known_ar)
        check(sid + '/' + day + ': replacement quantity and grant explicitly UNKNOWN', all(a[k] == 'UNKNOWN' for k in ['paper_quantity', 'paper_granted_risk_budget', 'paper_unused_released_risk_balance']))
        prior_native = live
    check(sid + ': exact daily actual guard-advance list', [(r['day'], r['layer']) for r in case['true_saved_guard_advances']] == raise_keys)
    check(sid + ': case is read-only, no replacement fill', case['new_accounts'] == case['new_candidate_fills'] == 0 and case['quantity'] == 'UNKNOWN')
    equal_money(sid + ': endpoint is original wealth only', case['actual_original_net_at_case_end'], case['days'][-1]['original_selected_campaign_known_wealth'])
    if sid == '000620.SZ':
        byday = {r['day']: r for r in case['days']}
        jan27 = [r for r in byday['2022-01-27']['original_audit_today'] if r['kind'] == 'pilot_layer_exit']
        feb7 = [r for r in byday['2022-02-07']['original_audit_today'] if r['kind'] == 'pilot_layer_exit']
        check('000620: Jan27 first pending is CP mobile only, I still on', bool(byday['2022-01-27']['original_stock_facts']['i_target']) and [r['layers'] for r in jan27] == [[113], [113, 122]] and all(r['reason'] == 'CP1_add_protection' for r in jan27))
        check('000620: Jan28 remains pending; no fictitious holiday fill', sid in byday['2022-01-28']['original_account']['pending_sell_sids'] and not byday['2022-01-28']['original_OPEN_sells'])
        check('000620: Feb7 I exit extends the same stock pending target', not bool(byday['2022-02-07']['original_stock_facts']['i_target']) and [r['layers'] for r in feb7] == [[68, 113, 122]] and feb7[0]['reason'] == 'I_structure_exit')
        check('000620: Feb8 only actual final I fills of 9900 shares', len(byday['2022-02-08']['original_OPEN_sells']) == 1 and byday['2022-02-08']['original_OPEN_sells'][0]['shares'] == 9900 and all(p['reason'] == 'I_structure_exit' for p in byday['2022-02-08']['original_OPEN_sells'][0]['parts']))
        check('000620: Jan19 first mobile requests and Jan20 actual sell keep CORE', len(byday['2022-01-19']['original_CLOSE_specific_exit_requests']) == 3 and [p['layer'] for t in byday['2022-01-20']['original_OPEN_sells'] for p in t['parts']] == [69,75,78] and [r['layer'] for r in byday['2022-01-20']['original_live_layers']] == [68])
    summaries.append({'sid': sid, 'days': len(case['days']), 'original_layer_ids': sorted(ids), 'endpoint_original_wealth': case['actual_original_net_at_case_end'], 'held_at_endpoint': bool(case['days'][-1]['original_live_layers']), 'guard_advances': len(raise_keys)})

focus = [r for r in RISK_ROWS if (r['sid'], r['day'], r['layer']) in [('688146.SH', '2026-04-30', 986), ('000620.SZ', '2022-01-21', 68), ('000620.SZ', '2022-01-24', 113)]]
result = {'status': 'PASS_WITH_COST_AND_CLOCK_LIMITS', 'checks': CHECKS, 'case_summaries': summaries, 'focus_original_inventory_reference_comparisons': focus, 'carried_past_source_observations': CARRIED_SOURCE_DAYS,
 'core_finding': 'Marked-price-to-floor decrease and paid-basis-to-floor-positive-shortfall decrease are different measures; neither is approved candidate buying capacity or the designer kappa.',
 'cost_boundary': 'Basis includes original already-paid buy fees. Floor value is qty times same-day raw floor; no hypothetical sell slippage or future sell fees are deducted. Designer kappa may use gross basis excluding fees already booked in D and include future execution costs; no equivalence or candidate grant is asserted.',
 'request_reason_clock': {'000620_2022_01_27': 'Actual CP1_add_protection requests for 113/122; I_target still on. This original order stayed pending, then Feb7 I_structure_exit extended it to CORE68; Feb8 actual final sell parts labelled I. Final reason must not be backfilled to Jan27.', 'closed_label_not_signal': True},
 'scope_limits': ['Two selected original cases, no market occurrence estimate.', 'Saved future endpoint/net/peak fields are original evaluation labels; daily inputs are independently matched to exact same-day source rows.', 'No new rule, fixed staging, R ladder, candidate quantity, grant, execution, alternative portfolio or PnL.', '688146 is electronic chemicals and outside task4 strict fixed25 semiconductor denominator.'],
 'new_accounts': 0, 'new_models': 0, 'new_parameters': 0, 'new_coverage_runs': 0, 'source_sha256': SOURCE}
result['audit_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT/'TWO_ORIGINAL_DAILY_CASE_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
(OUT/'ORIGINAL_INVENTORY_REFERENCE_DIFFERENCES.json').write_text(json.dumps({'definition': result['cost_boundary'], 'rows': RISK_ROWS}, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'checks': len(CHECKS), 'cases': summaries, 'focus': focus}, ensure_ascii=False))
