# Independent final audit: limited first-day PASS

Implementation SHA256: 755547e59cce871762523167bf21006033260291d6f0e613876d5c063aa5bc02

## Provenance

This record archives the completed independent read-only audit report relayed by the supervising task. The author of this archival record did not repeat that audit, rerun any account, or recalculate the reported financial checks. Only the implementation file hash was checked again before and after this documentation update.

## Reported verification

- Checkpoint contains **421 candidate intents across 294 unique candidate stocks**. “294 candidates” means 294 stocks, not 294 intents.
- Normal execution and restored execution with future HLCV perturbation have the same complete mutable-state payload hash.
- Both checkpoint binaries, metadata and provenance hash checks passed.
- All 44 run-freeze entries were rehashed, including 40 original sources.
- Four original trades/journal fills were independently used to reconstruct fees, cash, NAV and each admission constraint.
- Dated fee components were separately calculated without calling LR.protection_risk. The maximum difference across four fee-inclusive protection-risk results was 2e−24.
- Reported buy gross: 30,584.2845. Fees: 22.712826 rounded. Closing NAV: 1,198,447.002674 rounded. Every fill used probe; there were no promotions.

## Exact scope limitation

PASS applies only to the existing unified-probe Jan4–5 2022 first-day engineering check. This history contains no actual profitable-held-position promotion, corporate-action/equity event, or T+1 sell path. It therefore does not historically validate those mechanisms; their evidence remains the applicable source/synthetic checks. PASS does not include M3/breadth gating, a full-window economic run, returns, drawdown, or strategy success.

The original failed first_day_check attempt remains preserved. No implementation, failed-attempt artifact or first-day data was changed by this archival action. Full-window work remains paused pending the separate breadth contract.

## Verbatim completed review report

旧统一probe首日最终只读独审完成，限定范围 PASS，源码755547未变。恢复后独核：checkpoint421条候选意向/294只股票；正常与恢复+未来扰动记录同payload hash；两checkpoint本体、metadata、provenance hash一致；44项运行freeze全重hash通过（其中40旧源）。从原4笔trades/journal重建费用/现金/NAV及各次限额通过，另不用LR函数按dated fee分项手算4笔双边保护风险，最大差2e−24。买款30584.2845、费用22.712826、NAV1198447.002674，全probe、无晋升。注意“294候选”应称294只候选股，非294意向。PASS不含真实持仓盈利晋升/权益事件/T+1卖出路径的历史验证（本首日无这些事件），不含M3或全期收益；这些仅源码/合成范围。请将此明确审查记录转给builder封存，原失败保持。
