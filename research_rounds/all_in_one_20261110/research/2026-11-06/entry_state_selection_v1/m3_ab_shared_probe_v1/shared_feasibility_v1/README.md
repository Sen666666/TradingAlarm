# Shared reservation feasibility, bounded scope
Current files: limits_v2.py, run_first_open_v2.py, test_limits.py. Earlier unrun v1 source drafts are retained, not authoritative.

This stage implements a Decimal reservation gate, all-archives cash/receivable/raw-OPEN snapshot, exact original source getmeta/fee/size for initial proposal, original quantity-rule decrement, explicit CLOSE quantity ceiling and frozen global PVR/sid initial queue. It only reserves; it never fills or subtracts actual cash, updates realized profit, or reports shared returns.

Every candidate exports original_single_q, before_shared_caps_q, shared_q, minimum_buy_quantity and per-quantity checks. Original selected opportunities are retained even if rejected; no third candidate is inserted.

The source-grounded shared gates now include cash retention 10%, industry nominal risk 1%, probe capital/risk, per-route industry ALL cap (probe 2%, confirmed fixed research 10%) and original stock 10%. Pool/industry gates use pending/current fee-adjusted N; cash/stock use daily planning NAV. Single-round first probe cash/risk are still 2%/.25% frozen Nd from the original dated sizing function. Confirmed ADD proposal generation is NOT implemented here.

Implemented snapshot retains all original archives cash and receivables, including old closed-round claims. Any unresolved active UNKNOWN keeps the archived quantities recorded and yields uncertified NAV, stopping new risk. Gross inventory uses raw OPEN, not HLCV or estimated liquidation fees. Known-original exit/accrual/settlement callbacks must be completed before a nonempty holdings snapshot; this module does not perform or certify those phases.

Tests are mechanical SYNTHETIC fixtures plus a separate real empty-holdings first-OPEN reservation fixture. Synthetic injected values do not certify source NAV/profit/CP. The real fixture uses original 2022 Jan5 selection and Jan6 known OPEN/dated fees; no shared fills occur.

Pending acceptance checks, explicitly NOT PASSED:
- A naturally following held OPEN, with all known exits/equity clock before the snapshot.
- Perturb same-day and future H/L/C/volume plus same-day CLOSE-only I/CP/M3 while keeping known raw OPEN and valid factor/equity metadata. Actions, reservations and OPEN profit verdicts must be unchanged.
- Actual AB ADD/profit/fresh-CP proof and common promotion snapshot, source floor/coordinate translations after equity events.
- Full cross-OPEN restoration of all unresolved order obligations, actual reserve-all/fill-all commit and post-fill/slippage reconciliation.
- Complete shared account source integration, independent audit, and shared economic validation.

Original no_budget source/fixture stage stays sealed and unchanged. 2026 remains diagnostic. NON-PIT/NET80/historical orderability UNKNOWN stay in force.
