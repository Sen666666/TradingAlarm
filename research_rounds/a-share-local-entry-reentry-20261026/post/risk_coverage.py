"""Post-result description only. No signal, account, or parameter changes."""
from pathlib import Path
import csv, json, hashlib

HERE = Path(__file__).resolve().parents[1]

def rows(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))

def main():
    summary = rows(HERE / 'analysis-v1/summary.csv')
    campaigns = rows(HERE / 'analysis-v1/campaigns.csv')
    result = []
    for r in summary:
        if r['policy'] != 'LER':
            continue
        trades = [c for c in campaigns if c['account'] == r['account']]
        losses = [c for c in trades if c['closed'] == 'True' and float(c['net_pnl']) < 0]
        risks = sorted(float(c['initial_price_risk_cny']) / float(c['buy_gross'])
                       for c in trades if int(c['buy_fills']) == 1 and float(c['initial_price_risk_cny']) > 0)
        def quantile(q):
            x = (len(risks) - 1) * q
            lo = int(x)
            hi = min(lo + 1, len(risks) - 1)
            return risks[lo] * (hi - x) + risks[hi] * (x - lo) if lo != hi else risks[lo]
        tail, loss = float(r['tail_pnl']), float(r['gross_loss'])
        result.append(dict(account=r['account'], group=r['group'], scenario=r['scenario'],
            tail_net_profit=tail, all_losing_trades_net_loss=loss,
            tail_to_all_loss=tail / loss, tail_alone_covers_all_losing_trades=tail >= loss,
            ordinary_closed_net=float(r['ordinary_pnl']), open_net=float(r['open_pnl']),
            fees_already_in_trade_pnl=True, losing_trades=len(losses),
            losses_over_nominal_1R=int(r['loss_over_1R_count']),
            initial_price_distance_p50=quantile(.5), initial_price_distance_p90=quantile(.9),
            initial_price_distance_max=max(risks)))
    target = HERE / 'review-v1/risk-coverage.csv'
    with target.open('x') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result[0]))
        writer.writeheader(); writer.writerows(result)
    receipt = dict(post_result_only=True, new_economic_runs=0, new_rules=0,
                   code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   output_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (HERE / 'review-v1/risk-coverage-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps([r for r in result if r['scenario'] == 'base'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
