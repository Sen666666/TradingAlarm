# PRICE entry-generation gate: frozen event-only diagnostic

This reuses old breakout-failure and entry-qualification/holding-protection separation theory. It is not a new indicator or economic evidence. Fixed after reading named historical cases. No outcome column, return label, strategy consumer or economic runner is read or run.

Original PRICE market root, volume Q/CONFIRMED, protection S, receipts, AB priority, PVR ranking, original pending parents, fixed parent Q remainder, ADD and exits stay unchanged.
Only future new-probe-parent registration would read this gate; this diagnostic does not register anything.

For each original PRICE root born b:
- g=1 and active=true; freeze U_g=original birth prior20 High U.
- On subsequent CLOSE t, parent FAIL/UNKNOWN or invalid/source-discontinuous price retires the entry generation first. Source UNKNOWN is not false evidence or permission.
- If the entry generation is active and C_t<=U_g, retire it at t. Do not rebirth on that same CLOSE.
- If already retired before t, and C_t>max(H_(t-20)...H_(t-1)) with 21 consecutive common-calendar valid same-source OHLC bars, start g+1, freeze U_g to that rolling prior20 High, and active=true.
- While active, subsequent 20High breaks do not reset g or U_g.
- New initial permission is original fresh PRICE receipt AND active entry-generation AND original other permissions. An entry-generation birth alone creates no original PRICE receipt. No new lower-price invitation is claimed.
- Any original parent/source termination retires its generations permanently. A new original market root starts its own first generation.
- No cooldown, ATR/amount/age/stop-distance threshold or special-case exemption.

Outputs: all saved original receipts in 2022 and 2024_924, all original PRICE registered rounds, original BUY, formal common BUY, first/repeat/stock-state/volume/ticket identity intersections. Save both S_old and S_new and e0_raised. Report original-root ever-returned-to-birth-U separately from the regenerating gate; never use ever-returned as a permanent kill filter.
Causal raw source prefix begins before original root birth and includes at least 20 previous common sessions, even when the original root predates the reporting window.
Known cases: 000977 2022-01-05; 605118 2022-08-22; 605020 2022-07-15; 002174 2022-11-08; 002031 2022-06-13; 688660 2024-09-25; 600396 2024-10-28; 605488 and 002241 2024-09-30; 600126 and 605099 2024-12-11; 002126 2024-12-25; 002583 2024-09-25. 300666 2025-12-15/17 use previously established original birth only as supplemental causal cases. 2026-01-30/02-02/02-05 missing same-source bars remain UNKNOWN.
No input or old result is changed. Save artifacts only in this new diagnostic directory. Source SHA256 before/after; pure-prefix comparisons; original birth must always pass; allowed/disallowed+UNKNOWN conserve every original denominator. Gated-out original receipt must not be called an avoided losing trade.
