"""Classify existing fills; no counterfactual or strategy parameter selection."""
import json
from bisect import bisect_right
from collections import defaultdict
from build_stock_features import ROOT


def classify(decisions, orders):
    dates = [d['date'] for d in decisions]
    buckets = defaultdict(lambda: dict(orders=0, notional=0., fees=0., buys=0., sells=0.))
    for order in orders:
        # The frozen prior-close signal belongs to the next monthly decision,
        # including fills delayed or capacity-limited across later sessions.
        i = bisect_right(dates, order['signal_date'])
        assert i < len(decisions)
        assert order['signal_date'] < dates[i] <= order['date']
        assert i == len(dates)-1 or order['date'] < dates[i+1]
        symbol = order['symbol']
        if i == 0:
            reason = 'initial_allocation'
        elif decisions[i]['scores'][symbol] != decisions[i-1]['scores'][symbol]:
            reason = 'score_changed'
        else:
            reason = 'score_unchanged'
        b = buckets[reason]
        notional = abs(order['units']) * order['raw_open']
        b['orders'] += 1
        b['notional'] += notional
        b['fees'] += order['fee']
        b['buys' if order['units'] > 0 else 'sells'] += notional
    return dict(buckets)


def main():
    out = ROOT/'results/global-multihorizon'
    results = json.loads((out/'results.json').read_text())
    rows = []
    for result in results:
        case = result['case']
        decisions = json.loads((out/f'{case}-decisions.json').read_text())
        orders = json.loads((out/f'{case}-orders.json').read_text())
        buckets = classify(decisions, orders)
        assert sum(b['orders'] for b in buckets.values()) == result['orders']
        assert abs(sum(b['fees'] for b in buckets.values())-result['fees']) < 1e-6
        total_notional = sum(b['notional'] for b in buckets.values())
        unchanged = buckets.get('score_unchanged', {})
        rows.append(dict(case=case, buckets=buckets,
                         unchanged_notional_share=unchanged.get('notional',0)/total_notional,
                         unchanged_order_share=unchanged.get('orders',0)/len(orders)))
    report = dict(cases=rows, interpretation=[
        'Classification is relative to the previous monthly decision, not daily signal changes.',
        'Score-changed trades can contain both signal and weight-restoration effects; this is not an exact causal decomposition.',
        'Score-unchanged fills can include outstanding targets; they are not automatically unnecessary.',
        'Removing trades changes later inventory, dividends, risk and subsequent orders. Fees are not a counterfactual return estimate.',
        'No parameters or baseline results changed. Existing selected-universe and provisional VNQ payment-date limitations remain.'
    ])
    (out/'turnover-audit.json').write_text(json.dumps(report, indent=2))
    for row in rows:
        if row['case'].startswith('full-'):
            print(json.dumps(row))


if __name__ == '__main__':
    main()
