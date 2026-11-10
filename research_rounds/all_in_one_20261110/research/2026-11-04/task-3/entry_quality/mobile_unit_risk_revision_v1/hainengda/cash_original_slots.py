"""Read original reserve slots only; no new orders, Account or portfolio replay."""
from pathlib import Path
from decimal import Decimal as D
import gzip, json, hashlib
from paper_three_entries import fee_fresh, legal_floor

O = Path(__file__).resolve().parent
PAIR = O.parents[1] / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def tm(a): return str(a.get('at') or a.get('receipt', {}).get('at') or a.get('receivable', {}).get('ex_at') or '')


def main():
    book = json.load(gzip.open(PAIR/'B.json.gz', 'rt'))
    daily = [json.loads(s) for s in gzip.open(PAIR/'daily.jsonl.gz', 'rt')]
    paper_path = O/'THREE_ENTRY_PAPER_RESULTS.json'
    paper = json.loads(paper_path.read_text())
    results = []
    for r in paper['rows']:
        at = r['original_actual_buy']['at']
        previous = max((x for x in daily if x['at'] < at), key=lambda x: x['at'])
        for k in ['order_reserved', 'settlement_locked', 'payable', 'sale_receivable']:
            assert D(previous[k]) == 0, (r['layer'], k)
        target = next(i for i, a in enumerate(book['audit']) if a['kind'] == 'reserve' and a.get('at') == at and a['sid'] == '002583.SZ')
        before = [(n, a) for n, a in enumerate(book['audit'][:target]) if previous['at'] < tm(a) <= at]
        assert {a['kind'] for _, a in before} <= {'fill', 'settle', 'reserve', 'lot_risk_funded'}
        assert all(a['receipt']['side'] == 'sell' for _, a in before if a['kind'] == 'fill')
        settled, reserves = [], []
        available = D(previous['available'])
        for n, a in before:
            if a['kind'] == 'settle':
                s = a['settlement']; assert not s['debit']
                available += D(s['cny_amount'])
                settled.append({'audit_index': n, 'settlement': s})
            elif a['kind'] == 'reserve':
                available -= D(a['gross_budget_cny']) + D(a['fee_reserved_cny'])
                reserves.append({'audit_index': n, 'original_reserve': a})
        nav = D(r['signal_NAV_frozen'])
        headroom = max(D(0), available - D('.1')*nav)
        p = D(r['p_OPEN']); rule = r['dated_quantity_OPEN']; schedule = r['dated_fee_OPEN']

        def cash(q):
            return D(q)*p + sum(fee_fresh(schedule, q, p, 'buy', r['par_value']).values(), D(0)) if q else D(0)

        q = next((n for n in range(legal_floor(int(headroom/p), rule), rule['buy_minimum']-1, -rule['buy_step']) if cash(n) <= headroom), 0)
        assert cash(q) <= headroom and cash(q+rule['buy_step']) > headroom
        risk_q = r['OPEN_cap_with_new_signal_freeze_and_stock10']
        result = {'layer': r['layer'], 'at': at, 'status': 'EXACT_ORIGINAL_OPEN_RESERVE_SLOT_CASH_NECESSARY_BOUND',
                  'original_reserve_audit_index': target, 'original_reserve': book['audit'][target],
                  'previous_CLOSE': previous['at'], 'previous_available': previous['available'],
                  'previous_zero_components': {k: previous[k] for k in ['order_reserved', 'settlement_locked', 'payable', 'sale_receivable']},
                  'actual_net_settlements_before_slot': settled, 'prior_original_reserves': reserves,
                  'available_at_original_reserve_slot': str(available), 'signal_NAV_for_original_10pct_reserve': str(nav),
                  'available_minus_10pct_signalNAV': str(headroom), 'cash_only_legal_quantity_upper': q,
                  'cost_at_cash_upper': str(cash(q)), 'cost_at_next_legal_quantity': str(cash(q+rule['buy_step'])),
                  'risk_stock_signal_local_OPEN_cap': risk_q, 'risk_cap_buycash': str(cash(risk_q)),
                  'cash_necessary_passes_risk_local_cap': cash(risk_q) <= headroom,
                  'local_cap_after_cash_necessary_only': min(q, risk_q),
                  'final_grant': 'NOT_CHECKED_STOCK_CONCURRENT_0_005_CURRENTNAV_INDUSTRY_0_01_CURRENTNAV_AND_OTHER_NATIVE_CONSTRAINTS',
                  'not_a_new_path': True, 'not_carrying_candidate_fills_between_original_slots': True}
        results.append(result)
    out = {'status': 'THREE_ORIGINAL_OPEN_SLOT_CASH_NECESSARY_BOUNDS_ONLY', 'rows': results,
           'scope': 'Actual original OPEN prefix, net settles already include sell fee; prior real reserves subtract gross+fee. Not a CLOSE cash rejection and not a final grant.',
           'source_sha256': {str(p): sha(p) for p in [paper_path, PAIR/'B.json.gz', PAIR/'daily.jsonl.gz', O/'paper_three_entries.py', Path(__file__)]},
           'new_accounts': 0, 'new_paths': 0, 'D_hardgate': False}
    (O/'ORIGINAL_OPEN_SLOT_CASH_BOUNDS.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': out['status'], 'local_caps': [r['local_cap_after_cash_necessary_only'] for r in results], 'cash_caps': [r['cash_only_legal_quantity_upper'] for r in results]}))


if __name__ == '__main__': main()
