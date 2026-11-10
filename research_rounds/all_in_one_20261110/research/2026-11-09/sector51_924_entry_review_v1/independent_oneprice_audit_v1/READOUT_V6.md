# Independent one-price audit: certified through 2024-10-10

PASS. Latest reviewed pressure book: oneprice_execution_stress_v1/facts_v6/full_20241031_once. All old outputs remain intact. No historical strategy was rerun by this auditor, and no economic rule was changed.

## Checks completed
- 66020 independent account, order, fee, inventory, reservation, T+1, equity and 50-industry reconciliation checks.
- 44775 independent signal, ticket, CP lifecycle, protection and source/output integrity checks.
- 30083 independent prefix, immutable-source and path-difference checks.
- Total: 140878 checks with zero errors for the latest book, plus 47 independently written adversarial synthetic cases. These counts overlap in scope and are not statistical confidence levels.
- 22 certified days, 1,060 actual orders, 639 buy reservations and 3,609 frozen OPEN intent rows.
- The complete 12-family stress prefix through 10/9 exactly matches v5, including all intent, reservation and no-fill logs. Fact-version economic method ASTs remain identical to v4 except the run/checkpoint wrapper.
- Full gate-disabled baseline equivalence was independently read and verified for all nine baseline families through 10/9 in v5. A gate-disabled historical comparison for 10/10 has not been run or claimed. The same frozen execution source, 47-case synthetic suite and newly reconciled v6 book cover the one-day extension.

## Verified final values
As of 10/10: cash CNY 667,875.723723458; receivable zero; market value 742,752.00; gross NAV 1,410,627.723723458; net liquidation NAV 1,408,827.1731286596; 200 stocks and 38,900 shares.

Matched baseline gross NAV is 1,410,461.74923005115. Scenario minus baseline is +165.97449340685: cash -320.02550659315 plus market value +486.00. Fees paid are 21.19999340685 lower. Eleven aggregate trade-path differences were independently confirmed. The two barred symbols' entire path contributes -20.99455290605; other symbols' funding/path changes contribute +186.9690463129. This decomposition is accounting, not a causal claim that every other symbol difference came from only one seed.

## Failure semantics and limits
Two historical no-fills exist: 603883.SH, 100-share SEED on 9/6, and 002583.SZ, 100-share SEED on 9/24. They create no actual attempt and do not retain the old ticket. Their corresponding baseline attempts have zero descendant ADDs through 10/10 only. There is no observed historical ADD/SELL no-fill in this certificate.

Independent synthetic tests cover failed-sell cash exclusion, resizing an original ADD from 2,300 to 200 shares, no recycling a failed buy reservation to the rest of the same batch, no original-rejection revival, preserved CP on ADD no-fill and consumption only on later fill, T+1, persistent partial-lot exit locks after a rebound, and full state/log rollback after an actual SELL and ADD followed by missing gate data. Freeze-intent tests confirm no gate call occurs while producing the original intent and that the actual account remains untouched.

The raw positive finite O=H=L=C rule is applied ex post only, after original intentions/reservations. It is not historical ST/limit-up certification, an auction or queue model, or a return lower bound. Gate-disabled parity and independent reconciliation do not certify actual exchange fills. There are 61 slipped proxy prices outside observed daily H/L in v6; all are labeled accounting proxies, not executable-price evidence. The current 1,692-member/current-industry universe is not PIT. The rapid market-wide rise after 9/24 was unknowable when tickets were formed. OPEN cash-reserve rules allow close cash ratios to fall below 10% as holdings appreciate.

## Stop and next extension
2024-10-11 is wholly excluded from certified outputs because 600219.SH has an unadmitted equity event in facts v6. Its blocker has no partial orders. All twelve output families contain no 10/11 row. No 10/31 completion is claimed. Subsequent fact versions need a new independent extension audit.

Detailed outputs: facts_v6/RECONCILIATION.json, CAUSALITY.json, INTEGRITY_AND_DIFFERENCES.json, INDEPENDENT_DAILY_DECOMPOSITION.json, INDEPENDENT_SYMBOL_DIFFERENCES.json and INDEPENDENT_TRADE_DIFFERENCES.json. Prior v4/v5 results and the separate synthetic fixture remain available.
