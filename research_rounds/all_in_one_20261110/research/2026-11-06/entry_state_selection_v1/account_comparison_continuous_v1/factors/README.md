# Continuous open-factor API

This module imports no Account or Runner and performs no trading.

Usage:
- Construct one OpenFactorTimeline(raw_frame, normalized_events, method='theoretical_ex_price', end=last_required_date) per stock.
- raw_frame accepts trade_date/date columns or a daily DatetimeIndex. Supply the complete original source prefix, including invalid/missing-close source rows. Do not filter to eligible-price rows.
- Build FactorSource({sid: timeline, ...}); factor_at(sid, day) returns Decimal(str(float(original 40-digit cumulative factor))). Dates may include midnight, open, non-trading days and missing-bar action dates.
- A timezone-aware query is converted to Asia/Shanghai. An unknown stock or date outside frozen coverage fails explicitly.
- No fallback to today's close. Current close advances only the reference for later actions.
- Retain the original close-time Facts object for planning. This API is for the separate pre-close event boundary.
- Synthetic action reference prices are accounting coordinates, not tradable opens.
- Action terms use signal_cash_per_old_share/signal_split_ratio when provided. Actual dividend/share bookkeeping must continue using original account action fields.
- Caller verifies raw/action source identity and schedules original _actions/_payments. The module assumes normalized unique same-day action terms and does not certify announcement availability.

Evidence:
- SUMMARY.json: 1709 stocks, 4,081,068 original fullfacts factor rows exactly equal; no unmatched coverage or numeric differences.
- STOCK_CHECKS.json: per-stock counts and exactness.
- ACTION_REFERENCE_AUDIT.json: 16,715 factor events, including 334 missing-raw-bar events, with prior/ex references and Decimal/float factors.
- SOURCE_SHA256.json: implementation, verification, original source and all input hashes.
- SYNTHETIC_TESTS.json: four clock cases against exact original prepare_signal AST, including consecutive missing-bar actions and per-query physical prefix/current-close perturbation.
- STATIC_ATTEMPT1.json records an empty-array dtype bug in the first verifier attempt; no account execution occurred. The corrected static pass generated the complete evidence.

Limitations:
This proves numerical compatibility and the explicit price/action dependency, not announcement point-in-time correctness, execution feasibility or universe point-in-time correctness. The all-stock observed-data perturbation changes each last close only; broader prefix/current-close edge cases are tested synthetically. No account or return series was run.
