# C入口最终预检：停止，不运行经济臂

独立复核通过。这个C消费者不进入经济回测：候选不稀少，但没有针对性修复原A/B第一次启动被两名额排序挤掉的问题。此结论不等于否定所有C候选将来的盈利能力。

## 冻结公式与消费语义

x_t=log(股票调整收盘价/官方行业调整收盘价)，epsilon_t=x_t-x_(t-1)。
严格极点e冻结：delta_e²=(5/63) × Σ_{j=e-63}^{e-1} epsilon_j²。
原70位Decimal/区间时钟不变，无法确定严格极点或跨阈时UNKNOWN，没有新增经济阈值。

C_t要求：本窗原A/B在真实FLAT且原I/PVR/close检查通过、仅因行业两名额落选所建立的同I未消费资格仍有效；当前真实FLAT；t-1和t为连续共同日且S与M3都known true；当前真正fresh relativeUP；当前不是A/B日；原PVR已知且原close可行。A/B按原PVR先处理，C按PVR降序/sid升序只分剩余槽。

实际入场、I结束、来源/relative/I/S/M3 UNKNOWN清资格；execution UNKNOWN依原引擎锁定。UNKNOWN当日不得重新造可用C标。已知S/M3 false和PVR未知不消费标，PVR未知只阻当日C。C落选或明确NOFILL不能次日重放，但同I未来另一真正freshUP可重新邀请；BUY_PENDING阻邀，实际入场后卖出不复活旧标。

## 全窗口漏斗

顺序均为2022全年 / 2024年9至12月 / 2026上半年半导体：
- 广义persistent fresh：1101 / 1080 / 61。
- 同I曾有合法A/B名额落选：317 / 556 / 24。
- 逐日清标后有效未消费资格且基线FLAT：203 / 414 / 22。
- 原close可行：201 / 392 / 20。
- A/B仍有剩余槽：164 / 318 / 9。
- C按原PVR获影子槽：160 / 238 / 6。
- 下一共同OPEN已知条件代理：160 / 236 / 6；2024另2次明确NOFILL，无替补。

这是沿旧臂状态且从不实际执行C的影子诊断，不是ABC成交数、上界保证或胜率。重复同股影子获槽14 / 18 / 0次，真实首次C成交会改变资格及后续AB持仓。次开代理不能证明历史真实可成交。

## 对原目标的检验

2022全部固定20个提前案例中，只有国机重装命中：6月7日C信号，6月8日条件OPEN，位于原5月27日早AB被错过后、旧臂9月9日入场前。没有套用旧回合收益。
- 9例在目标间隔内没有任何新的relativeUP。
- 9例虽有新UP，但没有符合原I的合法persistent C日期。
- 秦川机床7月21日有persistent UP，但6月27日资格已在7月15日S=-1时清除。7月14日S为已知false仍保标，UNKNOWN才清标，恢复不补造。
- 1例国机重装命中。

17/20案例第一次freshUP已发生在原被挤掉的A/B同日。保持本规则时，另一个freshUP一般须经过下一轮relativeDOWN→UP；等它并非保留第一次启动证据。这是停止当前消费者的机制理由，不是收益判断。

2024固定11股整个9至12月窗口共9个persistent C候选日，这9个候选日全部没有有效未消费标，因此0个C获槽。不是说11股全窗从未造过标：这11股期间实际有4次AB落选造标，后来实际入场消耗。五个延后案例的原派生目标区间反向，不能拿其中的0作证；最终案例表这些字段标N/A，结论只用完整预先固定窗。没有为找命中重选日期。

## 成本、风险和独审

原含费24000初仓预算、含费3000计划保护风险、1200000参考NAV、dated lot/fees、双向5bp不利滑点、至信号收盘最近20个正成交量观察1%容量全部保持。next OPEN按原规则重新算手数。无共享账户或资金规则扩展。

A/B当日占满挡掉closePASS的37/201、74/392、11/20；同日原AB身份冲突为0。新C若真实更早入场，可能阻断同I后续197 / 413 / 4个独立AB事件，其中原已选61 / 123 / 0。这只是风险足迹，不是已发生的阻断或收益归因。

独审独立复核1627股495412日市场状态、20445个AB状态、2242候选、8226标记迁移、639个新close检查、613个next OPEN代理和C余槽排序，全吻合。固定7股全4595日相对时钟另行重算；613个新closePASS C日期的极点前63尺度与正向跨阈另以Decimal80复核。没有声称独立重算全部1627股时钟。28项合成是marker实现和邀请/配额规格测试，不是未来ABC集成验收。

每窗AB股票域对限定C闭合，因为窗口内合法AB落选是必要条件，窗口外资格不继承。1627并集之外82株无必要造标条件，不是漏掉符合定义的C；静态NON-PIT和历史orderability仍未解决。

## 复核入口

最终结论：STOP_DECISION.json、FINAL_QA.json、INDEPENDENT_AUDIT.json。
最终案例：FIXED_CASE_STATUS_FINAL.csv、FIXED_2024_FULL_WINDOW_STATUS.csv、TARGET_2022_CLOCK_REASONS.csv、TARGET_2022_ALL_FRESH_UP_TRACE.csv、FIXED_DAILY.csv。
全量漏斗：FUNNEL.csv、CANDIDATE_PREFLIGHT.csv、AB_SAME_DAY_SLOT_DENOMINATORS.csv、MARK_TRANSITIONS.csv。
风险分母：LATER_AB_CONFLICT_DENOMINATORS.csv和LATER_AB_CONFLICT_RISK.csv。
日级源状态：上级目录DAILY_FEATURES_0..7.parquet。
原失败日志/版本和修订seal均保留。最终FINAL_SEAL.json固定完整产物。

没有运行ABC经济臂，没有新增规则或参数扫描，研究在预检处封存。
