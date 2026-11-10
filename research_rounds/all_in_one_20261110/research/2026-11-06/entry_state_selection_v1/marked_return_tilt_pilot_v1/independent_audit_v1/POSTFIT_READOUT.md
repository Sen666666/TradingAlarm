# Independent post-fit audit

## Decision

**Reproducibility and numerical checks PASS. Candidate evidence does not support promotion.** No refit, economic replay, threshold change, or model change was made. The exact frozen predictions, coefficients, baselines, scalers, source files and preparation hashes were verified unchanged.

The four fitted objectives and gradients were independently recomputed, including ridge penalties. Maximum marked gradient was 1.35885e-7, below the frozen 1e-6 criterion; minimum Hessian eigenvalues were 3680.39–3952.39. PVR-only and binary-interaction gradients also passed. Independent H120 probabilities, Q, Q0, masks, and both binary predictions matched sealed outputs. Original strict-ordinary cash was reconstructed directly from ACTIONS quantities, prices and fees, with maximum difference 1.32e-11 CNY. All monthly and pooled outcome, tail-retention and calibration tables matched.

Predictions and models were sealed before outcome reports, as required by the frozen code and confirmed by artifact chronology. Audit artifacts are POSTFIT_AUDIT.json, INDEPENDENT_OUTCOMES.csv, INDEPENDENT_TAIL_RETENTION.csv, INDEPENDENT_H120_CALIBRATION.csv and INDEPENDENT_LATE_REJECTED.csv.

## Financial subset findings

These are saved original full-round conditional-path outcomes. They are not a new strategy PnL, equal-capital comparison, or account return.

| Selection mask | Ordinary rounds | Win rate | Mean winner | Mean loser | Payoff | Original static subset net |
|---|---:|---:|---:|---:|---:|---:|
| Original all | 1032 | 43.99% | 5081.98 | -1716.85 | 2.960 | 1314878.91 |
| PVR-only | 346 | 45.09% | 5688.01 | -1999.74 | 2.844 | 507379.43 |
| Binary interaction | 616 | 45.78% | 5328.22 | -1798.23 | 2.963 | 901947.60 |
| Marked tilt | 463 | 43.41% | 5817.41 | -1978.63 | 2.940 | 650896.52 |

The marked mask retains 35/69 strict-ordinary >3R rounds and 52.97% of their net amount. It retains 53/109 original net/buy-cash>=30% rounds and 51.34% of their net amount. It rejects 253 original winners, including 34 >3R rounds carrying 552743.31 CNY. It retains 44.86% of ordinary rounds; the fact that tail amount retention is somewhat higher does not establish a useful classifier or strategy.

September shows a selected subset win rate of 77.61%, versus 65.10% in the original September subset. This is not a general improvement: the marked mask retains 201/553 September ordinary rounds but 107/120 November rounds, where its win rate is 10.28% versus original 11.67%. October also weakens and December improves some descriptive metrics. No pooled or month-specific result is an untouched OOS claim, significance test, or license to choose a different threshold.

## H120 calibration and missingness

All 1198 confirmed entries have an observable H120 state; administrative-before-H count is zero. There are 1210 registered rows, 89 featureUNKNOWN rows retained unchanged, and 1110 entered rows with known scores for calibration. UNKNOWN monetary values are not imputed as losses or zero.

Pooled eight-category Brier is 0.7885279909 for beta0 and 0.7887492829 for marked. The marked-minus-baseline difference is +0.0002212920. Reporting-floor logloss is 1.9227030041 versus 1.9237131724, a +0.0010101683 difference. These are arithmetic comparisons, not statistically established degradation. They provide no aggregate calibration improvement from the five slopes.

The observation model is substantially miscalibrated across regimes: on the common scored sample, actual >3R H120 mass is 5.32%, versus marked 1.73%; actual U is 6.49%, versus marked 17.26%; actual M is 6.13%, versus marked 1.93%; actual S is 4.05%, versus marked 0.56%. Baseline has similar errors. This is not evidence that the unobserved financial outcomes are known or ignorable.

COVERAGE.csv arm identifies the selection mask. Its mean_pred_* columns use the marked forecast within each mask, even for original/beta0/PVR/binary rows; they are not separate forecasts from those models. The true beta0 probability comparison is H120_CALIBRATION.csv.

## Tail influence and horizon boundary

The maximum training mark is 28.5774079312R, from 300972.SZ, and its exit age is 137. The fixed H120 Q does not directly include that atom. Its H120 global-max-atom probability is therefore structurally zero, not evidence of robustness. The shared beta can still be influenced by that observation.

The largest mark's local deletion direction, with q and scaler frozen, has L2 size 15.94%, 17.39%, 13.46%, and 23.10% of the corresponding fitted beta norm across the four cuts. This is a partial first-order sensitivity, not a full leave-one-out refit: changing this observation also changes empirical q, N and potentially scaling. No claim of bounded gross-error influence or full-process tail robustness follows.

Of 28 strict-ordinary original rounds exiting after age120, the marked mask rejects 17, including 12 winners. Eight late ordinary rounds exceed3R; four are rejected, carrying 69452.16 CNY of the late-tail amount. The H120 conditional target and original complete-round retention evaluation are different objects; these facts must remain visible.

## Coarse-age support mismatch

The parent requested this structural check after fitting, without changing the frozen model. The 1–5 group uses a constant daily hazard, but the actual training ordinary/M exits begin at age3 in all four cuts. Actual age1 ordinary/M count is zero, while the grouped model assigns age1 positive ordinary-plus-M mass. Beta0 ordinary mass is approximately0.390%–0.412%, with M about0.009%–0.012%; marked mean total age1 sold-state mass is approximately0.404%–0.421% across monthly prediction sets.

In particular, age1 is the initial purchase day and an age1 full liquidation is incompatible with the original T+1 execution support. This is a genuine structural approximation error caused by coarse age grouping. It does not invalidate normalization, finite conditional expectation, convexity, or the numerical audit. It does prevent interpreting this model as an exact probability model of legally executable original trading paths. H120 calibration is calibration of the coarse observation-event approximation. The frozen candidate was not repaired after seeing outcomes.

## Scope retained

This is a fixed-empirical-baseline working likelihood, not a joint semiparametric MLE. Q is conditional on ordinary observation exit byH120, not the return expectation for all births. U/M/S may be informative; U:M:S daily reference ratios are constrained by the model. Empirical amount support gives no probability to unseen monetary values. Independent FLAT cohorts, stock/root/date dependence, prior historical inspection and unverified historical source availability remain. The result is a documented negative bounded pilot, not a reason to tune this candidate in place.
