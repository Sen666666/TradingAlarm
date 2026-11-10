# G1 continuation 与真实卖后再买：独立预审

本轮只读原源码、原日志及既有统计；不运行账户、模型或候选路径。后续数值核查范围待 owner 产物稳定后补收据。

- 统计互斥档建议为 `UNREADY_OR_NONFINITE`、`grade<0`、`grade=0`、`grade=1`、`grade>=2`；不得把 `<2` 全称为冷。若实际出现其它非整数，则显式单列，不向整数档取整。
- 原生 `policies_g1.py:18–19` 的 warm 是 ready 且 grade>=2，cold 是 ready 且 (grade<=−2 或 acute_down)。因此统计的“负 grade”与原生 cold 不是同义，−1 不能直接称为原生 cold。
- 新增成交的主解释变量取该笔 frozen intent 对应的 decision CLOSE；另列实际 fill 前一市场 CLOSE、延迟天数及日期是否相同。不得用 fill 当天收盘，也不得把延迟单前一日 grade 冒充发单 grade。
- 2022–24 连续账和 strong 账户的 2026H1 新 fills 分开；2025 开仓带入 2026 的持仓另表。卖出/应收与持有期边界需明确，不得将跨年持仓的全生命净值贡献当为 2026H1 阶段财富。
- 候选条件必须由决策时已完成的同股 MOBILE sell receipt 和当时原实际持仓/intent 判定。未来终局卖出、未来亏损、尚 pending 的请求不能用来认定“此前已卖”。同一 receipt 的多个 parts 不是多次独立卖出。
- “此前卖出”究竟包括部分卖出、是否要求同一结构、是否自账户起点累计，必须在统计前明确；跨窗口需回看 strong 2025 的真实历史，不能把 2026 起点视为无历史。没有原字段证明时报告 UNKNOWN，不凭字符串层号推断。
- **必须先冻结记忆范围**：太保原连续账早有 639/MOBILE，2022-09-01 买、2022-09-30 已平，旧 stock_structure 为 `601601.SH|0|2022-08-11`。1904/1914/1931 属新 `601601.SH|0|2024-08-19`。所以 2024-09-18 之前“尚未卖出”仅对当前这组层/当前结构成立；若按同股全历史曾卖定义，该日会被标记。父要求该日主筛选不挡，必须明确是当前机会/结构内的定义，不能拿 2024 片段冒充 2022–24 连续历史。1904 假设 9/10 卖出才会使当前结构内另一条假设路径满足先卖条件，不能把该假设嫁接为原路径事实。
- 原路径按筛选标记的金额仅为被触及的原贡献。删去该笔会改变持仓、现金、配额、ACT 与后续资格；不能将这些金额叫候选节省、收益或独立可相加的因果贡献。

已亲读原码：

1. `policies_g1.py:8,18–33`：G1_I use_x=False；暖约束机会/i_buy，冷本身不直接关闭既有 I。
2. `joint_v3.py:218,244–251`：event 与 continuing 分开；continuing 用 market_buyable 替换 buy_allowed。MOBILE 需 fresh CP 加 continuing；另有 ACT、exit pending、buy pending 障碍。
3. 原太保事实与源码的既有独审见 `taibao_1904_reentry_local_v1/review/REVIEW_RECEIPT.json`，本次不把假设退出当真实成交。

尚未审：本轮最终统计、全部新 fills 的日期/grade join、真实历史卖后再买计数、聚合贡献。等待 owner 稳定产物后做有限复核。
