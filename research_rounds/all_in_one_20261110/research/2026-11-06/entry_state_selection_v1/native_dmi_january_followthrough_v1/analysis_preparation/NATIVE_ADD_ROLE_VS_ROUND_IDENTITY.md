# Native kind=add is not a holding-state test

Source: /Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py

- Lines 243–245: held is observed; core requires not held, but mobile requires a fresh stock CP1 receipt and continuing eligibility, without a held requirement.
- Line 255: role mobile is encoded as kind add and reason fresh_CP1_mobile.
- Lines 274–281: routing additionally checks active industry, valid/unconsumed CP1 evidence, and probe/confirmed budget access. These checks do not redefine round identity.
- Lines 308–322: original ranking/funding and opening execute the accepted intent; kind is retained.

Therefore a first actual BUY after zero position can have native kind add. A new 0-to-0 round and its first layer must be identified by position lifecycle/ledger replay, not by kind core. No strategy change is made.

PVR original 2024-09-24 through 2024-10-08 six-session actual BUY fills: 14 total. Mutually exclusive economic lifecycle classification is 7 new rounds and 7 BUY fills while held (all ADD). Native kind add appears on 13 fills, including 6 of the new-round first BUYs; the remaining new-round first BUY is kind core. These two classifications deliberately answer different questions.
