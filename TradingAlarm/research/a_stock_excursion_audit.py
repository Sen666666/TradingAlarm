"""Descriptive close-based excursions; never interpret hindsight peaks as fills."""
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT, grouped


def main():
    output = ROOT / 'results/a-stock-excursion-audit'
    output.mkdir(exist_ok=True)
    source = ROOT / 'results/a-stock-zero-range-stress/campaigns.parquet'
    records = pd.read_parquet(source)
    lookup = {s: g for s, g in records.groupby('symbol')}
    rows = []
    for name in ('local-features.parquet', 'ths-retired-features.parquet'):
        for symbol, frame in grouped(pq.ParquetFile(ROOT / 'data/stock-features' / name),
                                     ['symbol', 'date', 'signal_close', 'observed_bar', 'positive_volume']):
            if symbol not in lookup:
                continue
            frame = frame[frame.observed_bar & frame.positive_volume].sort_values('date')
            for r in lookup[symbol].to_dict('records'):
                # Exit fills occur at open: that day's later close is not held.
                held = frame[frame.date.ge(pd.Timestamp(r['entry_date']))]
                if r['status'] == 'closed':
                    held = held[held.date.lt(pd.Timestamp(r['exit_date']))]
                else:
                    held = held[held.date.le(pd.Timestamp(r['mark_date']))]
                path = (held.signal_close.to_numpy() - r['entry_price']) / r['risk_distance']
                peak = max(0., float(path.max())) if len(path) else 0.
                trough = min(0., float(path.min())) if len(path) else 0.
                rows.append(dict(symbol=symbol, entry_date=r['entry_date'], status=r['status'],
                    R_cost15=r['R_cost15'], R_cost30=r['R_cost30'],
                    held_observed_closes=len(path), peak_close_R=peak, trough_close_R=trough,
                    peak_to_final_R=peak-r['R_cost15']))
    result = pd.DataFrame(rows)
    assert len(result) == len(records)
    result.to_parquet(output / 'excursions.parquet', index=False)
    closed = result[result.status.eq('closed')]
    losses = closed[closed.R_cost15.lt(0)]
    winners = closed[closed.R_cost15.gt(0)]
    groups = []
    for label, subset in [('closed_losses', losses), ('closed_winners', winners),
                          ('open_at_cutoff', result[result.status.eq('open_at_cutoff')]),
                          ('terminal_unknown', result[result.status.eq('terminal_unknown')])]:
        groups.append(dict(group=label, count=len(subset), final_sum_R=float(subset.R_cost15.sum()),
            median_observed_closes=float(subset.held_observed_closes.median()),
            median_peak_close_R=float(subset.peak_close_R.median()),
            reached_1R=int(subset.peak_close_R.ge(1).sum()),
            reached_2R=int(subset.peak_close_R.ge(2).sum()),
            reached_4R=int(subset.peak_close_R.ge(4).sum())))
    summary = dict(source=str(source.relative_to(ROOT)), campaigns=len(result), groups=groups,
        limitations='Descriptive realized path, not a trading rule. Peaks are close-based, exclude exit-day close, include entry-day close. R includes synthetic price adjustment, not account returns. Earlier exits alter re-entry paths and may truncate large winners; cannot claim saved losses as strategy profit. Reused history, not a holdout.',
        decision='Use this to decide whether a causal price-only exit experiment is justified; do not optimize peak thresholds against outcomes.')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
