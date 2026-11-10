# Seal authority

The authoritative final integrity reference for this directory is AUTHORITATIVE_FINAL_SHA256.json. It covers every artifact present after the distribution supplement and this authority note, except its own bytes. Verify each listed file against that SHA-256.

Historical seals are intentionally retained byte-for-byte:
- OUTPUT_SHA256.json is the initial process snapshot, superseded for current integrity checks. It is NOT a current matching seal. Its entries for SOURCE_SHA256.json, SUMMARY_QA.json and audit_old_pvr.py no longer match because the generated split counter label was corrected from an ambiguous 15 events to 15 layer allocations / 14 actual events. No economic result changed.
- FINAL_OUTPUT_SHA256.json is the corrected base-audit seal. Every file it lists still matches. It predates the distribution supplement, so it is not a complete directory seal.
- DISTRIBUTION_SUPPLEMENT_SEAL.json is the append-only distribution snapshot. Every file it covers and every original prior-artifact snapshot still matches. It predates this authority note and the final seal.

No prior seal or original-source file was rewritten during the distribution supplement. The latest seal includes the preserved historical seal files as artifacts; that does not assert that every historical seal still describes the latest versions.

Financial qualification is independent of file integrity: all outcomes remain OLD_PROXY_ONLY_NOT_NET80_CERTIFIED.
