# Independent pre-fit review: marked observation-event tilt

Status: MATHEMATICS_AND_INPUT_PREFIX_PASS; IMPLEMENTATION_REVIEW_PENDING. This preliminary report does not authorize fitting. No real-data model fit, economic replay, parameter search, or source modification was performed. Final authorization must name the final protocol and code hashes after implementation tests.

## Mathematical result
For fixed empirical q and finite inputs the proposed observation-event likelihood is valid. A round contributes one log-normalizer per observed risk day, including its single terminal day; a known ordinary terminal contributes minus eta times its exact Y. U, M and continuing risk have sufficient statistic zero, not economic return zero. Administrative censoring contributes all observed continuation days and no terminal event. At beta zero Z=1, so all probabilities recover q. Nonnegative q, positive group risk-day exposure, and sum(q)=1 are required.

The Hessian is the sum over round/group exposures of n times Var(T) times zz-transpose, plus diag(4,4,4,16,16). It is strictly positive definite; finite empirical support and the positive ridge produce a unique finite optimum. These facts do not identify unknown financial outcomes. The q0:qU:qM ratio is fixed within age group across features. Features change ordinary amount composition and also total exit/continuation/unknown probabilities through Z.

This is a fixed-empirical-baseline working likelihood. Estimating q on the same training data and then freezing it is not a joint semiparametric MLE. It is acceptable for a predeclared predictive pilot, but baseline in-training calibration is by construction and cannot count as validation. Dependence among stock/date/root and repeated cut snapshots rules out iid precision claims.

## Independent read-only risk-prefix reconstruction
Source ACTIONS and first frozen-responsibility records were read directly for new2023, new2024JanAug and old2024, joined to the saved original signal-close PDC feature eligibility. Old2022 was excluded. Every risk member had a buy_core strictly before cut. Every sell_all prefix had exactly zero stock quantity; every nonexited prefix had positive quantity. U and sell_all were mutually exclusive. Event day exposure was inclusive, age1 was entry session, and M stopped risk at sell_all. No final ordinary filter selected risk membership.

Cut | PDC risk rounds | ordinary | U | M | held
2024-09-02 | 3477 | 2736 | 599 | 63 | 79
2024-10-08 | 4015 | 2786 | 609 | 66 | 554
2024-11-01 | 4319 | 2914 | 638 | 71 | 696
2024-12-02 | 4437 | 3178 | 648 | 86 | 525

Risk-day totals by fixed five age groups:
Sep: 17209, 42239, 47477, 8698, 135.
Oct: 18986, 43983, 48193, 8777, 135.
Nov: 21367, 51911, 50592, 8905, 135.
Dec: 21997, 54516, 60797, 9315, 160.
The oldest group has only five ordinary events at the first three cuts and six at Dec, plus eight U at each cut. This is real sparsity, not grounds to silently smooth, widen groups, or claim precision. All cuts ordinary Y ranges were [-2.87235530881202, 28.577407931152464].

## Numerical independent synthetic checks
An independently written implementation of logsumexp likelihood, analytic gradient and Hessian was checked without importing or modifying the candidate implementation. Gradient maximum absolute finite-difference discrepancy was 1.0481187473487807e-08; Hessian discrepancy was 3.668956196634099e-07. The synthetic Hessian minimum eigenvalue was 265.83258746206087. eta=0,+/-1,+/-1000,+/-1000000 remained finite and probability mass summed to one to floating-point precision. Entry/terminal ages 1,5,6,20,21,60,61,120,121 and administrative age7 gave the expected inclusive group-day counts.

Numerical finiteness is not robustness. In a synthetic support containing maximum Y about28.58, eta=1 allocated nearly all single-day mass to that largest atom. No Y clipping is necessary for numerical stability with proper logsumexp; if the candidate requires clipping to run, stop rather than change the outcome target. Finite fixed-support influence is not bounded gross-error influence. Report largest-winner tail-amount concentration and the predeclared local Hessian influence diagnostic. If the latter freezes q/scaler, label it partial influence: it omits the largest round also defining empirical baseline q and scaling.

## Clock, missingness and decoder boundaries
Financial usability proxy and source-version availability are distinct. All usable monetary marks must satisfy known_at strictly before OPEN cut; source_available_at is unverified. New labels do not establish historical PIT data. M is temporary coverage at a snapshot, not an enduring financial loss, and sold positions do not contribute later holding survival. U is first observed data responsibility freeze, not forced liquidation. FeatureUNKNOWN is not imputed and retains original membership.

The parent fixed the common scaler to original median/IQR/clip5 on currently mature ordinary PDC training rounds, followed by the original interaction scaler. This is as-of outcome-informed preprocessing, not future leakage, if only known_at<cut marks define its sample. It must not restrict the marked model full PDC risk likelihood. The preliminary protocol read at 23:18 still described all-risk scaling and must be corrected before the final hash.

H120 is a finite observation-event calibration horizon, not a forced sale. Report all five financial buckets plus U/M/S and administrative coverage. Use stable recursion. Empirical support has no probability at unseen monetary values and is not a continuous density; do not score heldout exact amounts with a density likelihood. Fixed-bin multiclass calibration is allowed, with empty-support impossibility and any reporting-only logloss floor disclosed.

Q is E[original full terminal Y | observable ordinary exit by H120] for this model. Its conditioning event changes with eta; it is not the eventual birth return nor policy value. Q>=Q0 is a fixed training-derived diagnostic mask, not an actual entry decision. Original-path selected financial labels may assess winner/loss/tail retention but are not a new account PnL. Keep featureUNKNOWN, unresolved money and nonordinary paid scenarios separate. Refit original PVR-only and five-slope binary controls on the same cut/template mature ordinary training rows and the specified common scaler; do not reuse old cross-template coefficients or tune future-month thresholds.

## Final review still required
Inspect exact frozen implementation and prefit outputs: strict clocks, physically truncated prefix equality, future poison invariance, terminal counting, no post-exit risk, q conservation, beta0 decoder identity, analytic derivatives, stable extreme-Y recursion, tail diagnostic definition, input hashes, no unauthorized fit. Then identify exact final code/protocol hashes. Formal fit may proceed only after that final PASS.

Sources: distribution_objective_feasibility_v1/EXTENDED_CURRENT_STATUS.md; BASELINE_AUDIT.py; EXTENDED_SUPPORT_AUDIT.py; label_availability_audit.py; closed_price_supervised_pilot_support_v1/PROTOCOL.json and run_pilot.py; saved ACTIONS.csv, FROZEN_RESPONSIBILITIES.json, PRICE_LABELS.csv and EXTENDED_*_PDC_FEATURES.parquet for the three same-template cohorts.
