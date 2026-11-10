# Execution bridge v1: frozen bounded engineering API

The real-data run is pre-fixed to 2022-01-06, 2022-01-07 and 2022-01-10 OPEN, with Jan4/5 initialization and CLOSE phases through Jan10. Never extend dates to obtain an ADD, dividend or favorable outcome. Conditional OPEN fills retain the original historical proxy: observe that OPEN, size, and book OPEN +/- 5bp. This does not prove same-price executable trading after observing OPEN, limit-up/down permission or queue fills.

## API and source reuse
- derive_source_callbacks(source): AST-derived original held_open validation/exit prefix, original entry mutation, original ADD preparation block and ADD mutation. Record original and extracted definition hashes. No original file is imported unsafely, edited or globally budget-patched.
- close_phase(day): original held_close, register, certified gross-CLOSE wallet snapshot, dynamic Nd/INIT/RISK checkclose with mode/round/event/budget cache key, original I/PVR and industry top-two, then original pay_day. pay transfer preserves NAV and is available next OPEN. New shared CLOSE selections are recomputed, not replayed from fixed-1.2m selected names.
- open_phase(day): original accrue/coordinate validation; all original exits first; certified post-sell/pre-buy snapshot; prepare all same-round fresh-CP promotion evidence then commit promotions; ADD proposals in held-state order; first probes by PVR descending/sid; reserve ALL; then conditional-fill ALL; reconcile cash, per-layer quantities, receivables and pool/risk views.
- commit(order_id): unique action identity, idempotent duplicate commit, one successful ADD per original round. No external broker orders or partial-fill system is introduced.
- snapshot(phase): seed + all round cash, all round recognized receivables, known raw OPEN/CLOSE inventory. UNKNOWN with asset/order/claim responsibility blocks new risk. Initial quote UNKNOWN may be liability-free only if no fill history, inventory, claims or pending-order responsibility is proven; the stock's UNKNOWN lifecycle remains locked.
- proof: original round_id + first-fill action ID + active same-round layers/no conflicting order + last CLOSE freshly produced addpending, exact round NET80 at CLOSE and OPEN, M3 TRUE. CP identity is an audited consumption identity from original CP file hash/sid/CLOSE date/source row, not a recalculated indicator or invented native canonical receipt. (fill day, OPEN completion) precedes (same day, CLOSE), so same-day fresh CP is allowed for next OPEN.
- T+1: every requested sell layer must be from an earlier session. An illegal sell_all containing a same-day layer is rejected atomically and retains all inventory/exit responsibilities. No new automatic partial sell_all rule.
- First-probe close_q ceiling only; ADD has no invented close quantity cap and retains original OPEN remaining-risk/slot sizing.

## Required tests before fixed real execution
1. Original pending Q0 cash-coordinate wrapper and 2024 unadmitted-action ordering; original factor tolerance.
2. Source held_open versus split exits/ADD preparation/commit equivalence at a frozen original held snapshot, with identical original budget and q.
3. Phase-aware CP, positive CLOSE and OPEN NET80, negative profit, stale/replayed CP, old-round dividend isolation and one successful ADD.
4. All-sells before reservation, uniform promotion proof snapshot, fixed ADD/initial order, no third-name replacement.
5. Fill/action idempotence, per-layer T+1, no overlapping live rounds per stock, archived UNKNOWN responsibility, zero-liability initial UNKNOWN classification.
6. Dynamic CLOSE Nd/cache/top-two, source dated quantity/fees and all frozen caps.
7. Actual fixed held OPEN perturbation: same-day/future HLCV plus same-day CLOSE-only I/CP/M3 must not change that OPEN's actions, reservations or profit proofs; keep known OPEN and lawful factor/equity metadata. Compare only the target OPEN, not later days where the poisoned CLOSE would legitimately become known.
8. Exact cash = seed + all round cash; NAV = cash + gross inventory + recognized receivable; actual per-layer q = archived core/add q; all cash/q mutations have one action ID.

If the fixed three OPENs have no genuine ADD/promotion/equity event, report no real coverage and rely only on labeled source-definition synthetic or mechanically fixed source-snapshot hybrid unit tests. No full shared economic run or performance validation.
