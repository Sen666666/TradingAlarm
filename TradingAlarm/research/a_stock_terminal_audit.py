"""Reproduce terminal execution evidence without inventing fills or recoveries."""
import json
import numpy as np
import pandas as pd
from build_stock_features import ROOT


def main():
    out = ROOT / 'results/a-stock-zero-range-stress'
    stress = pd.read_parquet(out / 'campaigns.parquet')
    base = pd.read_parquet(ROOT / 'results/a-stock-campaign-signals/campaigns.parquet')
    select = lambda d: d[(d.symbol == '600898.SH') & (d.entry_date == '2024-09-09')].iloc[0]
    original, held = select(base), select(stress)
    features = pd.read_parquet(ROOT / 'data/stock-features/ths-retired-features.parquet',
                               filters=[('symbol', '==', '600898.SH')]).set_index('date')
    signal = features.loc[pd.Timestamp('2024-12-24')]
    assert bool(signal.exit_signal) and signal.signal_close > held.stop
    raw = pd.DataFrame(json.loads((ROOT / 'data/ths-raw/USHD600898.json').read_text())['bars'])
    terminal = raw[raw.date.ge(original.exit_date)].copy()
    assert len(terminal) == 12 and terminal.date.iloc[-1] == held.mark_date
    assert np.isclose(terminal.high, terminal.low, rtol=1e-10, atol=1e-10).all()
    assert terminal.volume.gt(0).all()
    terminal.to_csv(out / '600898-terminal-bars.csv', index=False)
    record = dict(symbol='600898.SH', entry_date=held.entry_date,
        exit_signal_date='2024-12-24', exit_reason='two closes below SMA200; initial stop not yet breached',
        baseline_exit_date=original.exit_date, last_observed_mark=held.mark_date,
        final_zero_range_sessions=len(terminal), baseline_R15=float(original.R_cost15),
        unexited_mark_R15=float(held.R_cost15),
        zero_recovery_scenario_R15=float(-held.entry_price * 1.0015 / held.risk_distance),
        classification='compulsory_delisting_terminal_recovery_unmodeled',
        source='https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-01-27/600898_20250127_U7P1.pdf',
        source_publication='2025-01-27', delisting_date='2025-02-10',
        evidence='Issuer confirms no delisting consolidation trading period. No holder proceeds or post-delisting transfer execution established.',
        interpretation='Positive daily volume does not establish an individual order fill. No-fill is an execution scenario; last mark and zero recovery are valuations, not realized proceeds. Announcement is retrospective evidence only.')
    (out / '600898-terminal-audit.json').write_text(json.dumps(record, indent=2))
    # Include every unresolved holding; do not selectively drop the new losing case.
    known = stress[stress.status.ne('terminal_unknown')]
    unknown = stress[stress.status.eq('terminal_unknown')].copy()
    scenarios = []
    for cost in (15, 30):
        zero = -unknown.entry_price * (1 + cost / 10000) / unknown.risk_distance
        for fraction in (0, .5, 1):
            value = fraction * unknown.exit_price
            r = (value - unknown.entry_price * (1 + cost / 10000)) / unknown.risk_distance
            scenarios.append(dict(cost_bps=cost, fraction_of_stale_mark=fraction,
                unresolved_count=len(unknown), total_count=len(stress),
                all_campaign_mean_R=float((known[f'R_cost{cost}'].sum() + r.sum()) / len(stress)),
                unresolved_sum_R=float(r.sum())))
        cutoff_summary = json.loads((out / 'cutoffs/summary.json').read_text())
        latest = max(x['cutoff'] for x in cutoff_summary)
        expected = next(x['zero_terminal_sensitivity_mean_R'] for x in cutoff_summary
                        if x['cutoff'] == latest and x['cost_bps'] == cost)
        assert np.isclose((known[f'R_cost{cost}'].sum() + zero.sum()) / len(stress), expected, atol=1e-12)
    (out / 'terminal-sensitivity.json').write_text(json.dumps(dict(
        interpretation='Hypothetical terminal valuations of ALL six stale holdings, not fills, recovery bounds or account returns. No disposal fees assumed. Zero is stress, not a claim all suspended assets are worthless.',
        scenarios=scenarios), indent=2))
    classification_path = ROOT / 'results/a-stock-fill-audit/stale-classification.json'
    classification = json.loads(classification_path.read_text())
    classification['records'] = [r for r in classification['records'] if r['symbol'] != record['symbol']]
    classification['records'].append(record)
    classification_path.write_text(json.dumps(classification, indent=2))
    print(json.dumps(dict(case=record, scenarios=scenarios), indent=2))


if __name__ == '__main__':
    main()
