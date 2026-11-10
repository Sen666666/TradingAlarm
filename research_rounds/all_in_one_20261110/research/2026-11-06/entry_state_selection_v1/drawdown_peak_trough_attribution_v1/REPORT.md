# Exact peak-to-trough attribution

This is an attribution of existing daily proxy ledgers, not a strategy backtest or evidence of tradable fills. All sources are NON-PIT and actual tradability remains UNKNOWN.

## Scope and accounting

The maximum drawdown is computed from the complete daily NAV path. Each attribution then uses only events in (its actual peak timestamp, its actual trough timestamp]. Both actual peaks happen to be the initial empty account on 2022-01-04. Neither uses a full-test closed-round cohort.

Net-cost convention: delta NAV = delta realized sale PnL (sold shares allocated buy and sell fees) + delta unrealized mark PnL (remaining cost includes unsold buy fees) + dividend accrual. Fees are already included and must not be deducted again.

Gross-cost convention: delta NAV = gross realized sale PnL + gross unrealized mark PnL + dividend accrual - all interval trading fees. Dividends are booked receivables, not verified cash payouts. Splits preserve total remaining cost and change quantities; fractional-share treatment follows the original ledger, not invented cash compensation.

## Results

### PVR
Peak 2022-01-04 15:10:00+08:00: CNY 1200000; trough 2025-04-30 15:10:00+08:00: CNY 627400.8695946009700.
Drawdown CNY -572599.1304053990300, fraction -0.4771659420044991916666666667.
Net bridge: -584270.7487976533050000000001 + -12228.6775277457250 + 23900.29592 = -572599.1304053990300.
Gross bridge: -533438.944430 + -11823.287250 + 23900.29592 - 51237.19464539903000000000002 = -572599.1304053990300.
Rounds complete by trough: 1921, net -559472.5246175544050000000000; rounds still open at trough: 67, net -13126.6057878446250.

### NOACT
Peak 2022-01-04 15:10:00+08:00: CNY 1200000; trough 2025-04-18 15:10:00+08:00: CNY 690561.5996908631160.
Drawdown CNY -509438.4003091368840, fraction -0.42453200025761407.
Net bridge: -532475.3468100501440000000000 + -9144.4417390867400 + 32181.38824 = -509438.4003091368840.
Gross bridge: -472192.309600 + -8711.171400 + 32181.38824 - 60716.30754913688399999999999 = -509438.4003091368840.
Rounds complete by trough: 2350, net -487117.0402607767440000000000; rounds still open at trough: 66, net -22321.36004836014000000000000.

## Group definitions

- position_layer=initial means the first executed layer after the stock position was flat. subsequent means a later layer in the same uninterrupted holding round. This is independently reconstructed, not inferred from kind.
- kind=core/add is the original strategy kind. An initial layer can be kind=add.
- entry_pool=probe/confirmed and role=core/mobile come from the immutable real_buy_fill journal, not end-of-test metadata that can migrate. These are birth-cohort attributions, not dynamic time spent in each pool.
- Every partition uses the same peak NAV CNY 1,200,000. Contribution fractions sum to that arm’s exact MDD. Fraction of total drawdown loss uses the same whole-interval loss within each arm; it is not a return on that group’s investment.
- Closed/open round status is determined at the trough. An open round’s contribution includes already sold sublayers, partial sales, remaining marked inventory and accrued dividends. It is not the same as the unrealized mark bucket.

## Files

MDD_PEAK_TROUGH.csv / SUMMARY.json: endpoint and both PnL conventions. GROUP_CONTRIBUTIONS.csv: conserving partitions. LAYER_CONTRIBUTIONS.csv: complete layer evidence. ROUND_STATUS_AT_TROUGH.csv: trough-specific holding rounds. INTERVAL_TRADES.csv and INTERVAL_EQUITY_EVENTS.csv: exact interval inputs. ENDPOINT_MARKS.csv: validated raw mark sources. CASH_BALANCE_BRIDGE.csv: balance-sheet change. SOURCE_SHA256.json and CHECKS.json: audit.

No original files were edited, no strategy was executed, no data fetched, no new intraday signal inferred. Source agreement proves model accounting, not actual historical settlement or market executability.
