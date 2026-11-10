# PRICE initial-entry right-breadth descriptive contract

Frozen before computing grouped outcome means. This is saved-ledger attribution only, not a new strategy, economic simulation, gate, ranking, parameter search, removed-order PnL or causal treatment-effect estimate. Existing results and named cases were already seen; no blind/out-of-sample claim.

## Population and accounting

Use original independent_channel_joint_economic_v1 A+B+PRICE/PVR baseline, all PRICE registrations: 2022 2411 (actual buy_core 2395), 2024 1210 (actual 1198). Retain no-buy and UNKNOWN. Actual purchase comes only from original ACTIONS buy_core, not non-null outcome. Original COMMON scope is original COMPARISON_REPORT_RECOVERED summary common_covered_sids, not a later gate-comparison common scope. Do not infer participation before each window.

FULL closed net and independent initial CORE/PROBE closed net come from saved price_entry_generation_dynamic_v1/report_YEAR/ALL_ROUNDS.csv arm=baseline only, with original core_independent_dated_fee_diagnostics and financial round_coverage checked rowwise. This baseline is the exact original, not the generation-gated arm. Do not recompute fees. A known financial outcome requires actual buy, financial_covered, not economic UNKNOWN/unresolved/open-censored, and non-null closed net. Report conditional known closed and financially covered closed separately, with financial-uncovered and economic-unknown counts. No missing outcome is zero.

## Known-at and independent M3

Signal T CLOSE, before next-common OPEN fill. Original canonical M3 means native G mu5 EMA (alpha=1/3, original 64-return warmup) strictly positive for three consecutive valid common sessions under the same source identity; no PVR-known restriction. Native underlying EMA can inherit prior source history; this is not the separate STRICT source-isolated variant. Use canonical_mu3_comparison_v2 RIGHT3/KNOWN3 plus WARM_PREFIX_M_R/M_K (2021-12-29/30/31) before lagging. This preserves a true 2021-12-31 observation for 2022-01-04 daily changes.

Use original FIXED_ROSTER static 1709-stock/90-sector membership, non-PIT. For each target permanently exclude itself from its fixed same-sector peers P. N=|P|, K=sum known_T, n=sum known_T*right_T, U=N-K. Known share=n/K if K>0; fixed-N share interval=[n/N,(n+U)/N]. N=0 means UNKNOWN.

New pure breadth description uses the original half-share boundary, not the original composite gate: 2*n>=N => AT_LEAST_HALF; 2*(n+U)<N => BELOW_HALF; otherwise UNKNOWN. It does not add n>=3. Do not call it strict majority. Original independent sector candidate is retained separately: n>=3 AND [(n/N>=1/3 AND original paired delta3>0) OR n/N>=1/2], with the original UNKNOWN semantics. Do not relabel delta3 as daily change. Old ENTRY_FACTS M3 fields used the M3-and-PVR-common-known subset; preserve them under OLD_COMMON_K names only.

## Daily change and uncertainty

Same fixed target-excluded peer set at T and prior common session. For peer j at endpoint s, a_js=k_js*r_js, b_js=a_js+(1-k_js). Whole-fixed-N daily-change count bounds: L=sum(a_jT-b_jprev), H=sum(b_jT-a_jprev). Ratio bounds=[L/N,H/N]. Main daily direction: L>0 POSITIVE; H<0 NEGATIVE; L=H=0 FLAT; else UNKNOWN. Missing clock/N=0 UNKNOWN. These are conservative endpoint-state bounds, not imputed unknown outcomes.

Auxiliary paired-known change uses pair_j=k_jT & k_jprev, J=sum pair, entered=sum pair*r_T*(1-r_prev), left=sum pair*(1-r_T)*r_prev, D=entered-left, paired delta=D/J, J/N coverage. If J=0 sign UNKNOWN; otherwise D>0 POSITIVE, D<0 NEGATIVE, D=0 FLAT. Paired direction describes only common-known peers, never the entire industry. Both known endpoint windows overlap and ensure the four relevant days share source identity.

Stock M3 ON/OFF/UNKNOWN uses its own independent state. Original sector E0, fast market prerequisites and four original sector facts are retained; sector E0 and four facts have no variation among actual PRICE buys, so they cannot explain within-buy quality.

## Fixed groups and cases

Primary one-variable groups: half-share state, whole-N daily direction, stock M3, original independent sector candidate. Auxiliary paired direction is distinctly labelled. Main cross: half-share x whole-N daily direction. Fixed diagnostic half-share x stock M3; lifecycle stratification uses original root birth/continuing frontier and window-local first all-strategy buy/first PRICE after AB/repeat PRICE. Only half-share and whole-N direction are separately stratified by ticket and participation, not a full combinatorial grid. Calendar month x each of those two variables is a descriptive confounding check, not a threshold or selected calendar strategy. Report samples and FULL/CORE coverage n, mean net, total net, positive-net rate, plus unknowns.

All original roots and previous actual exits are reused. New-root re-participation is not a retry and same-root initial-entry reuse is not invented. Washing out after a fall or chasing a right-side rise is not itself an error.

Fixed cases only: 浪潮2022-01-05、同方01-04、游族11-08、永和07-15、巨轮06-13、南网05-12、寒武纪03-04; 海能达2024-09-20/23/24/25、电气风电09-25、福莱与歌尔09-30、华电辽能10-28、杭钢与共创12-11、银轮12-25; 江丰2025-12-15/17与2026-01-05/15 use existing FIXED_DAILY signal facts only. No 2026 fill or return claims.

No old file, ledger, lock, authorization, parameter or production code may be changed. Outputs are confined to this new diagnosis directory. No economic consumer imports/executions.
