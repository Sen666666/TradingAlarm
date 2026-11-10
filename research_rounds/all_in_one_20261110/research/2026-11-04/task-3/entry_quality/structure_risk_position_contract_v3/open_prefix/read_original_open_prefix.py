"""Seven original OPEN prefix arithmetic checks; no engine imports/replay."""
from pathlib import Path
from decimal import Decimal as D
import gzip, hashlib, json
import pandas as pd

O = Path(__file__).resolve().parent
EQ = O.parents[1]
BASE = EQ / 'trend_exit_controls_v1/runs/BASELINE'
MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
DAYS = {'2022_2024': ['2022-01-11', '2022-01-17', '2022-01-24', '2022-01-25'],
        'strong': ['2026-04-22', '2026-04-23', '2026-05-06']}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def js(p): return json.load(gzip.open(p, 'rt'))
def tm(x): return str(x.get('at') or x.get('receipt', {}).get('at') or x.get('receivable', {}).get('ex_at') or '')
def encode(x):
    if isinstance(x, D): return str(x)
    raise TypeError(type(x).__name__)


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = {r['symbol']: r for r in manifest}
    signals, bound = {}, {}
    results = []
    for window, days in DAYS.items():
        pair = BASE / window / 'pair'
        book = js(pair / 'B.json.gz')
        daily = [json.loads(s) for s in gzip.open(pair / 'daily.jsonl.gz', 'rt')]
        for day in days:
            pre = max((r for r in daily if r['at'][:10] < day), key=lambda r: r['at'])
            at = day + ' 09:30:00+08:00'
            first_reserve = next((n for n, a in enumerate(book['audit']) if a['kind'] == 'reserve' and tm(a) == at), None)
            cutoff = first_reserve if first_reserve is not None else len(book['audit'])
            audit = [(n, a) for n, a in enumerate(book['audit'][:cutoff]) if pre['at'] < tm(a) <= at]
            errors = []
            unknown_kinds = sorted({a['kind'] for _, a in audit} - {'fill', 'settle'})
            if unknown_kinds: errors.append({'unexplained_CA_or_cash_event_kinds': unknown_kinds})
            for k in ['order_reserved', 'settlement_locked', 'payable', 'sale_receivable']:
                if D(pre[k]) != 0: errors.append({'prior_component_not_supported': k, 'value': pre[k]})
            q0 = {s: int(q) for s, q in pre['positions'].items()}
            q = dict(q0)
            sells = []
            for n, a in audit:
                if a['kind'] != 'fill': continue
                f = a['receipt']
                if f['side'] != 'sell': errors.append({'unexpected_buy_before_prefix': n}); continue
                s = f['security_id']; q[s] -= int(f['shares'])
                assert q[s] >= 0
                sells.append({'audit_index': n, 'receipt': f, 'net_sale': D(f['gross_cny']) - D(f['fees_cny'])})
            q = {s: n for s, n in q.items() if n}
            settlements = [{'audit_index': n, **a['settlement']} for n, a in audit if a['kind'] == 'settle']
            credits = sum((D(s['cny_amount']) for s in settlements if not s['debit']), D(0))
            if any(s['debit'] for s in settlements): errors.append('unexpected_prior_debit_settlement')
            sale_net = sum((s['net_sale'] for s in sells), D(0))
            if credits != sale_net: errors.append({'sell_net_settlement_mismatch': str(credits - sale_net)})
            cash = D(pre['available']) + credits
            dividend_ar = D(pre['dividend_receivable'])
            native_before = native_after = open_after = D(0)
            rows = []
            for sid, oldq in q0.items():
                if sid not in signals:
                    rec = records[sid]
                    paths = [(Path(p), h) for p, h in rec['source_sha256'].items() if Path(p).name == 'signal.parquet']
                    assert len(paths) == 1, sid
                    path, expected = paths[0]; assert sha(path) == expected
                    signals[sid] = pd.read_parquet(path, columns=['raw_open', 'raw_close'])
                    bound[str(path)] = expected
                f = signals[sid]
                past = f.loc[:pre['at'][:10], 'raw_close'].dropna()
                if past.empty: errors.append({'missing_prior_mark': sid}); continue
                mark = D(str(past.iloc[-1])); native_before += oldq * mark
                remain = q.get(sid, 0)
                native_after += remain * mark
                op = None
                if remain:
                    if pd.Timestamp(day) not in f.index or not pd.notna(f.loc[day, 'raw_open']) or f.loc[day, 'raw_open'] <= 0:
                        errors.append({'missing_exact_OPEN_for_remaining_stock': sid})
                    else:
                        op = D(str(f.loc[day, 'raw_open'])); open_after += remain * op
                rows.append({'sid': sid, 'previous_qty': oldq, 'actual_sold_before_prefix': oldq - remain, 'prefix_qty': remain,
                             'previous_known_raw_mark': mark, 'mark_source_day': str(past.index[-1].date()), 'exact_day_raw_OPEN': op})
            if native_before != D(pre['inventory']): errors.append({'previous_inventory_source_reconciliation_gap': str(native_before - D(pre['inventory']))})
            nav_native = cash + native_after + dividend_ar
            nav_open_valued = cash + open_after + dividend_ar
            peaks = [a for a in book['audit'] if a['kind'] == 'risk_checkpoint' and tm(a) <= pre['at']]
            checkpoint = max(peaks, key=tm)
            peak = D(checkpoint['peak'])
            A_native = max(D(0), nav_native - D('.8') * peak)
            A_open = max(D(0), nav_open_valued - D('.8') * peak)
            # Native G2 is >=.36 * original-known-mark inventory because b<=Z<=M.
            lower_native = D('.36') * native_after
            lower_open = D('.36') * open_after
            result = {'window': window, 'next_OPEN': at, 'status': 'UNKNOWN' if errors else 'EXACT_ORIGINAL_PREFIX_ARITHMETIC',
                      'prefix': 'after all original actual sells and settlements; before first actual new reserve (or J307 equivalent if no new reserve)',
                      'previous_CLOSE': pre['at'], 'previous_daily_components': {k: pre[k] for k in ['available', 'order_reserved', 'settlement_locked', 'payable', 'sale_receivable', 'dividend_receivable', 'inventory', 'nav']},
                      'first_new_reserve_audit_index': first_reserve, 'original_prefix_event_indices': [n for n, _ in audit],
                      'actual_sells': sells, 'actual_settlements': settlements, 'cash_after_original_settles': cash,
                      'remaining_dividend_AR': dividend_ar, 'remaining_sale_AR': sale_net - credits, 'CA_or_other_event_kinds': unknown_kinds,
                      'previous_inventory_rebuilt': native_before, 'native_known_mark_inventory_after_sells': native_after,
                      'exact_raw_OPEN_inventory_after_sells': open_after, 'native_known_mark_NAV_prefix': nav_native,
                      'raw_OPEN_valued_NAV_prefix': nav_open_valued, 'OPEN_minus_native_mark_bridge': open_after - native_after,
                      'ACT_checkpoint': checkpoint, 'ACT_peak': peak, 'A_native_domain': A_native, 'A_OPEN_valuation_domain': A_open,
                      'G2_lower_native_mark_domain': lower_native, 'G2_lower_OPEN_valuation_domain': lower_open,
                      'native_domain_lower_exceeds_A': lower_native > A_native, 'OPEN_domain_lower_exceeds_A': lower_open > A_open,
                      'native_A_le_20pctNAV': A_native <= D('.2') * nav_native, 'OPEN_A_le_20pctNAV': A_open <= D('.2') * nav_open_valued,
                      'grant_conclusion': 'UNKNOWN' if errors else ('DENY_ZERO_ALREADY_EXISTING_G2_LOWER_EXCEEDS_A' if lower_native > A_native and lower_open > A_open else 'NOT_PROVEN_BY_LOWER_BOUND'),
                      'rows': rows, 'errors': errors}
            results.append(result)
            print(json.dumps({k: result[k] for k in ['next_OPEN', 'status', 'native_known_mark_inventory_after_sells', 'native_known_mark_NAV_prefix', 'G2_lower_native_mark_domain', 'A_native_domain', 'grant_conclusion', 'errors']}, default=encode), flush=True)
    payload = {'status': 'READ_ONLY_SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES_NO_ACCOUNT_REPLAY', 'results': results,
               'sources': {str(MANIFEST): sha(MANIFEST), **bound, **{str(BASE/w/'pair'/n): sha(BASE/w/'pair'/n) for w in DAYS for n in ['B.json.gz', 'daily.jsonl.gz']}},
               'script_sha256': sha(Path(__file__)), 'new_accounts': 0, 'model_imports_or_calls': 0, 'counterfactual_paths': 0,
               'scope': 'Original fixed-prefix arithmetic only; lower-bound rejection under frozen G2, not a complete alternate account result. Sell net settles already include sell fees; not subtracted twice. Two valuation domains explicitly bridged.'}
    (O/'SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=encode)+'\n')


if __name__ == '__main__': main()
