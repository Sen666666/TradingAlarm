# V4 冻结稿审查

**主逻辑通过静态审查。** 本件按 SIGNAL_FREEZE_V4 的已选语义审，不再把 reservation/fill 方案作为当前阻碍。尚未审 V4 实现或新 CP* 数值。

- once 是一次唯一 permission/request-event 成功发行；发行后资金拒绝、零成交、跳空取消都不返还。这可在纯信号层定义，但不保证一次有效成交试仓，可能耗尽未成交机会、漏掉连续赢家。
- 每个原 up 一份信用；down 关闭旧信用。CP 市场 receipt、账户防重放、up_once 三本账分开。重放不再次发行；同 receipt 不做两张 probe/add。
- HELD 且 mature 时 ADD 优先，并结清未用 probe；否则 UNUSED 才能 CP_PROBE。FLAT 不借 mature 无限重入。试探 purpose 保持原 mobile/add 的 CP 保护语义，不借旧 CORE 宽持有线。
- CP* 用原公式、新 V3 I_hold/P 上下文，不用 I_expand；down 的 kernel reset 不清已持层 floor。旧 floor 先检，未触发才 max 新保护；旧 pending exit 不被新 generation 擦除。CP* 是新输入版本，旧 CP 只对照。
- 固定 HELD/FLAT 是互斥的条件真值分支，不是交易账户。不能把发出 PROBE 自动改成有仓，也不能用旧实际成交反馈新信用。

实现/输出应把以下既有边界显式记录：

1. 两个 branch 的 seen_CP/up_once 也按全 source 前缀初始化后截展示，不在 97 日起点重发历史信用。
2. HELD 的假设包含本日旧保护/结构/ACT检查已通过，而不只是 pending 列表为空；无持仓账无法实算该假设。已知锁阻止、未知 context 不冒作 FLAT/安全状态。
3. 公平对照覆盖旧 CP ∪ 新 CP* ∪ 原 CORE/其它 intent，不能只列新输出；新 CP* 不借旧 canonical ID 冒名。
4. 原 J 的旧 I off 是全股优先退出。未来若将 CORE 维持旧 I、MOBILE 接 V3 P/新结构退出，需要明确拆分接线；若照搬全股旧 I，又可能让新 START 的 CP_PROBE立即受旧 I off 退出。当前不建账，应明确该接口尚未验证，而非泛称所有原持有/退出路径不变。

这些是条件、来源和能力边界，不新增价格门、数量、资金参数或冷却。冻结对照可以继续；不能据此宣称完整新持仓算法或正期望已成立。本审查未运行候选、CP 或账户模型。
