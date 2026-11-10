# Bounded execution bridge: author release
Status: AUTHOR_PASS_BOUNDED_ENGINEERING_PROXY_ONLY. Independent review pending.

## Authoritative artifacts
- Engine: engine_v2.py. AST-derived callbacks: source_split_v2.py.
- Final synthetic suite: test_execution_v4.py / run_synthetic_v4.py / synthetic_attempt_04. Thirteen groups passed.
- Fixed real-source driver: run_bounded_v2.py / bounded_attempt_02. Three and only three OPENs: 2022-01-06, 2022-01-07, 2022-01-10; Jan4/5 initialization and CLOSE through Jan10.
- FINAL_STAGE_SEAL.json hashes all artifacts, including retained drafts and failed fixtures. Old drafts are not production alternatives. No original or previously sealed artifacts were edited.

## Observed engineering path
Jan4 initialization produced zero legal selected A/B tickets without converting left-truncation UNKNOWN to FALSE. Jan5 dynamic shared-NAV CLOSE selected the same 30 initial opportunities as the old first fixture. Their source-formula quantities, new initial CLOSE ceilings, and shared feasible quantities all match sealed reservation v3 individually.

Conditional proxy core fills: Jan6 four, Jan7 three, Jan10 three. Ten unique fill actions and ten live layers/rounds; zero successful ADDs, zero sells, zero rights registrations/claims/coordinate bridges in this fixed real-source path. Eight Jan10 CLOSE intentions remain pending for a later OPEN that was NOT executed. They are intentions, not live reserved orders or fills.

There was one real-source qualification migration: 000810.SZ on Jan7. Its first core fill was Jan6 OPEN; the fresh CP was Jan6 CLOSE, not a pre-entry historical CP. Whole-round NET80 was 832.3739559184 at that CLOSE and 1048.030914298 at next OPEN; O=12.98 exceeded the effective ADD line 11.2803240340766574. Migration did not change cash, quantities, cost or protection.

This stock could not ADD under the unchanged original AB risk formula: core I line remained raw 8.43. Using original ADD buy reference 12.98649, 800-share core price risk was 3648.564, initial fee 5.8256774324, and whole-core planned stop sale fee 12.3385217036. Existing planned fee-risk was 3666.728199136 > frozen round cap 3000, so remaining risk and original ADD quantity were zero. This was NOT shared cash shortage, invalid CP or an added strategy gate. See REAL_PROMOTION_NO_ADD_DIAGNOSTIC.json.

## Reconciliation and causality
Every OPEN/CLOSE reconciled archive quantities to layers, unique action identities, actual cash to seed plus all round cash, and certified NAV to cash + gross raw-price inventory + recognized receivable. Final Jan10 CLOSE accounting balances: cash 1129419.49999951285, gross inventory 72306, receivable 0, NAV 1201725.49999951285. These are engineering balances, not a return-validation claim.

Every fixed OPEN reserved all candidates before any conditional fill. First opportunities remained original industry top two; execution failures did not refill a third name. Dynamic CLOSE Nd values changed with certified shared NAV rather than reusing fixed1200000 quantities. Per-allocation cash reserve, single-stock, industry, probe capital and nominal-risk gates remain distinct from original whole-round fee-risk. POST_FILL_POOL_RISK_AUDIT.json separately reconstructs raw-OPEN pool/industry exposure; passive overages are descriptive and never trigger invented sales.

Jan7 and Jan10 held-OPEN tests poisoned same-day/future H/L/C/volume, capacity, I/CP and M3 while preserving known OPEN, factor/lineage, prior CLOSE and legal metadata. Actions, reservation quantities/fees/reasons, promotion/profit proofs and accounting were identical. Original proposal z dictionaries still carry unused raw fields; the comparison does NOT claim every raw payload byte is unchanged.

## Source equivalence and synthetic coverage
The mechanically first original Jan7 ADD was 600820.SH. Original Jan5 birth and Jan6 native entry/CLOSE form its source snapshot. Whole original held_open versus split exit / ADD prepare / ADD commit matched full state and actions exactly, including original 2300-share ADD. It is a source-snapshot hybrid unit test, not a holding in this shared wallet.

Thirteen final source-definition synthetic groups cover: post-fill same-day CP; O below/equal/above line; valid migration when original size is zero; shared cash-reserve rejection without reversing proof; ADD preflight UNKNOWN before any migration; negative/stale/old-round CP; one ADD and idempotent commit; whole-source split equivalence; per-layer T+1 atomic illegal-sell rejection and one whole-order sale fee; liability-free initial versus asset UNKNOWN; original Q0 bridge/tolerance; multi-layer record quantity and held-coordinate bridge, ex-OPEN receivable and pay-CLOSE/next-OPEN cash; old-round dividend isolation; dynamic budget cache; fresh-signal reentry; exact 2024 unadmitted-action definition/order.
The last rights case uses both core and ADD shares through the new engine's OPEN/CLOSE callbacks. All altered inputs and CP proofs are explicitly SYNTHETIC, never presented as original events.

## Restrictions and remaining coverage
- Historical conditional OPEN proxy only: observe OPEN, recompute q, then book OPEN +/-5bp. This does not prove same-opening-price execution after observing OPEN, limit-up/down permission or queue fills. No minute data was used. Leakage tests do not fix this proxy limitation.
- Not a full-period account run, strategy return validation, or proof of an optimal parameter. Confirmed industry10% and other scaling values are frozen research choices, not user-selected optimal limits.
- The real three-OPEN path contains one migration but no ADD fill, sale, rights event, reentry or UNKNOWN. Those branches have source-definition synthetic or bounded original-snapshot coverage only.
- The 2024 new execution path has only exact unadmitted-action definition/order synthetic coverage here, not a new full 2024 shared equity run. The separate original no_budget 2022/2024 regression remains independently passed.
- No broker partial fills, cancellation/late-fill system or cross-session live-order restoration is implemented. This engine commits its complete historical conditional reservation batch at the same fixed OPEN.
- Source hash/lineage and chronological consumption do not certify historical point-in-time availability or absence of later vendor revisions. M3 inputs remain the original common-known historical panels; no left-edge synthetic tickets were inserted.
- New initial UNKNOWN certification proves no fill/layer/claim/order liability for that round, while every other archive is independently retained. Asset or live-order UNKNOWN blocks all new risk and migration; known exits and recognized claims continue.
- Raw original max_inventory_reference_fraction is retained solely as the old fixed1.2m diagnostic, not shared exposure.
- A mixed real batch with successful ADD plus fresh initials, and actual exits funding that batch, is not exercised by these three dates. The ordered implementation and source tests must not be presented as broad empirical coverage.

## Traceability
synthetic_attempt_01 failed because the synthetic new-birth row incorrectly copied old-round cash. The fixture was corrected without changing the engine to conceal the error. synthetic_attempt_02 passed12; attempts03 and04 passed13, with04 strengthening the existing rights case to both layers and full callbacks.
bounded_attempt_01 failed in pollution setup because pandas rejected bool assignment into an integer field after two basic OPEN steps. run_bounded_v2 fixes only the copied test-column dtype; bounded_attempt_02 repeats the identical frozen dates and passed. Both failed outcomes remain recorded. Post-fill audits are read-only post-processing of completed artifacts, not another account run.
