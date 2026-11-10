# Continuous native inputs, 2022–2026-05-15

API: import continuous_inputs as C; shared, receipts, cp, states, ir, identity = C.inputs(). This installs C.N.SCORES, exposing at(sid, day), values, manifest_sha256, source_manifest_sha256. configure_scores() installs only the merged scores. No Account/Runner is instantiated or executed by this module.

Domain: exact original fixed1709 stocks /90 industries. Existing facts, CP1 inputs/outputs, industry states, original market/context, ACT and H1 are reused and truncated through2026-05-15. This does not fix original future-selected universe or daily OPEN proxy limitations.

Missing 2025H1 only: prepare_missing_h1.py invokes the unchanged frozen CP1 evidence trace over cached numerical CP1 outputs, generating9507 stock and708 industry canonical receipts. No I/CP1/stage model calculation occurs. It executes the unchanged original PVR formula on frozen full-warm signal inputs and exports117 dates for all1709 stocks, preserving9410 NA cells. This IS original-formula PVR calculation, not reuse of an existing full numeric export. It does not introduce or tune a formula.

Validation in export: all source/output hashes match frozen manifests; receipt dates equal numerical CP1 receipt=True; canonical IDs unique; trace_unknown empty; all90 industry state IDs match; all1799 trace prefixes exact at2025-03-31; all1709 original PVR history values equal the old726-date exports; all1709 PVR physical prefixes exact at2025-03-31. No accounts run.

Receipt union:2022 manifest +2023 manifest +2024 manifest +newH1 +original2025-07 onward. Duplicate dates fail; every stock and industry continuous receipt calendar must equal original CP1 receipt=True. PVR union: original2022–2024 +newH1 +original2025-07 onward, end-truncated, with identical-date original2022 overlap checked exactly. No cross-date forward fill or selective candidate filling. Missing PVR returns None.

Important provenance: merged score manifest_sha256 is the SHA256 of canonical JSON containing START, END and the three source manifest SHA256 values. It is deliberately not the old N default score-manifest identity. The main runner should include continuous_inputs.py, SOURCE_FREEZE.json, H1_MANIFEST.json and the returned identity in its source freeze. The original models and old manifests are unmodified.

Files: prepare_missing_h1.py, continuous_inputs.py, H1_MANIFEST.json, SOURCE_FREEZE.json, COMPLETION.json, receipts/*.json, scores/*.parquet, items/*.json. Existing input files are read only. Export writes only this directory, can resume completed items, and does not invoke inputs() or any financial path.
