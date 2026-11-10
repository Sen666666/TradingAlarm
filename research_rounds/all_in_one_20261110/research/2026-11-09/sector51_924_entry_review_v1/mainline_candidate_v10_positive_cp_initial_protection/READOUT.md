# M10 build ready for independent review

Status: 85 synthetic/static checks PASS. No M10 historical strategy execution. No historical approval file generated. Isolated M7 single-factor INITIAL protection; M9 is not inherited or stacked. engine.run remains disabled. All economic code and contract hashes are recorded in CONTRACT_FREEZE.json and SYNTHETIC_QA.json.

## Implemented contract

A same-day newly created, valid, unconsumed, unbroken post-actual-buy CP may establish or raise an INITIAL lot's independent adjusted-coordinate stop only when both exact round CLOSE net and hypothetical whole-round CP liquidation net are strictly positive. Record the actual then-current cashflows, dividend, quantities, source and factor. Only rising floors are adopted. Older unadopted receipts cannot be retrieved later. Consumption or replacement of a buy ticket does not erase an already established INITIAL price constraint. Existing I, trial, ADD and EXPANSION-SEED logic and account ifloor remain unchanged.

CLOSE tests the prior line before running the inherited close receipt/protection path. The ordinary end-of-CLOSE transfer-planning hook then admits new protection. OPEN may use only a line adopted before that OPEN's day; a prior lock or current real gap below the line exits using actual OPEN with inherited slippage and fee. No CP-price fills or backward use of same-day receipt.

## Execution audit

M7 originally combines all eligible I/CP lots per stock into one order and does not apply sell_floor to original exits. M10 preserves those original quantities and account-I precedence, adds only legally sellable INITIAL quantities, and issues one combined order/fee. A new increment cannot reduce or round an original protection order. Per-lot reasons and actual quantity mapping are explicit; mixed orders retain CP_LAYER_EXIT and account exits retain their original reason. M10-only order reason is POSITIVE_CP_INITIAL_PROTECTION. Unsellable/T+1/partial new remainders remain locked.

Review identified a pre-existing INITIAL lot exit colliding with a new M10 lock. Fixed before history: preserve m10_baseline_exit independently; never classify it as only new quantity because a M10 lock also exists. Regression includes 150-share original quantity under a 100-share incremental rule, and T+1 persistence. Original pre-QA freeze metadata is retained in CONTRACT_FREEZE_PRE_QA_V1.json; final freeze explains the non-hypothesis corrections.

Economic-identity controls with no adopted protection compare cash, remaining holdings, realized cashflow, fees and existing order fields with direct M7.exit_open for no-exit, I, CP-close, CP-open and T+1 cases. All pass. Unchanged inherited method identities and byte-identical atomic loop are checked. Baseline dependency hashes remain unchanged.

## Diagnostic audit

net_at_CP is hypothetical whole-round liquidation at one candidate CP and one inherited sell fee. It is the adoption gate, not a promise that all holdings actually receive that stop.

Layered-floor pressure instead uses each actual lot's effective floor: ADD own floor, INITIAL max(I, adopted stop), EXPANSION-SEED I. It applies modeled slippage and a separate minimum sell commission to each lot, explicitly shown row by row. This is a static separated-exit pressure convention, not claimed simultaneous realizability or future execution. Positive CP-net can coexist with negative actual layered-floor pressure; a synthetic example expressly verifies this distinction.

HOLDINGS and CAPITAL_LOTS retain existing columns and add baseline_I_signal, effective_protection_signal, seed_cp_floor, seed_cp_id and lock evidence. Legacy SEED protection_signal still denotes the baseline I, so downstream analysis must use effective_protection_signal for actual M10 protection. Tests compare effective exported signals with actual execution behavior and between HOLDINGS/CAPITAL_LOTS. INITIAL_CP_PROTECTION.json exports remaining state with immutable adoption evidence; CANDIDATES and ORDERS preserve admission/rejection/exit history even after a lot is sold.

## Validation boundaries

85 checks include positive/zero/negative gate boundaries, exact CP-net/dividend/fee formula, same-day buy and later CLOSE receipt, missing/old/consumed/invalid/source-mismatched/breached receipt rejection, independent latch after consumption, lower replacement retention/higher replacement raise, no weakening after loss, new-round isolation, stock1/sectorfalse intact-structure retention, true gap/equality OPEN fills, rebound after CLOSE lock, old-line-before-new-receipt ordering, actual inherited CLOSE receipt path, I precedence, mixed reasons/single fee, legal partial and odd full-liquidation quantities, T+1, zero quantity, adjusted coordinate/factor handling, source fail-closed, no-lookahead reads, real atomic sale/adoption rollback, missing OPEN preflight, native export/hash and historical entrypoint disablement.

Some synthetic CLOSE integrations stub only unrelated ticket refresh, corporate pay registration, transfer planning and attribution to isolate the actual inherited price-protection/receipt path. This is not historical/facts-loader QA or full production certification. No new actual-data examples or outcome searches were performed to tune this rule. The parent predeclared evaluation is outside this build.

Research risks remain: delayed enablement when CP-net is nonpositive, sensitivity to whole-round holdings/cashflows, normal pullback exits, gap losses, and difference between the hypothetical CP gate and actual layered protection. No guaranteed breakeven, profit lock or proven performance improvement is claimed.
