# Bounded v2 interface review

Reviewer: `/root/review_cross_market_validation`.

The reviewer inspected v2 source and independently ran the initial 9 tests. Two permission
boundary counterexamples were found: a receipt predating the external E0 episode could
create a probe attempt, and a previously unprocessed old industry receipt could be delivered
late to create fresh probe permission.

Fixes: retain `episode_started` independently of attempt `started`; reject pre-episode
receipts; late first industry receipts are audit-only and cannot create an attempt, advance a
stage, or authorize risk. This does not disable asynchronous consumption of a genuinely
valid, frozen, current-attempt grant by a current fresh stock receipt.

The reviewer inspected both fixes and independently reran **13/13 v2 tests**, including added
fee-adjusted NAV and full-fill/cancel conservation checks. Within this bounded interface
scope no further duplicate-credit or cross-attempt occupancy-washing blocker was found.

The old 31 v1 tests are not v2 evidence. Real I eligibility, per-stock/mobile sizing,
protection/exit algorithms, legal execution timing and source generation remain outside this
review. Existing core from a failed old attempt remaining in its old probe pool is explicitly
conservative occupancy, not an accounting loss; no broader migration policy was introduced.

## Incremental probe-mobile opportunity interface

After the original 13-test review, the reviewer inspected only the new `request` role branch
and its two additional tests, then independently reran **15/15**. Probe mobile requires a
current canonical stock/attempt-bound CP1 receipt; the core epoch lock applies only to core.
Core/mobile share sector/probe constraints, and the receipt consumption set is shared across
probe and confirmed pools. Confirmed mobile continues to require a grant. No new blocking
issue was identified in this limited change. The original core-I eligibility remains a caller
precondition; these tests are not real execution or economic-effectiveness evidence.
