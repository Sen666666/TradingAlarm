# 四股原候选日期冻结

只读取原 PRIMARY、opportunities、daily 与 book，按指定完整日期范围固定案例；未读取 Efast/Eslow、新排名或未来标签，未计算评分、退出或账户。370 个原市场股票日中有 85 个原正规模 pending 独立股票日，原 PVR 全部 ready。

| 固定范围 | 原市场股票日 | 原候选日 | 原实际买入层 |
|---|---:|---:|---:|
| 000620，2022 年 1 月 | 19 | 10 | 6 |
| 300666，完整 strong | 242 | 39 | 2 |
| 300085，2024-09-12—10-31 | 29 | 16 | 1 |
| 002583，2024 年 1 月及 9—11 月 | 80 | 20 | 3 |

日期范围先保存于 `FIXED_CASE_SCOPE_BEFORE_NEW_FEATURES.json`；选日期不使用原层事后收益。原 PVR 候选位次为 `original_PVR_slot+1`，原 H1 候选位次为 `original_H1_slot+1`。numeric priority key 不是全市场 PVR 位次。本任务新排序比较范围为同日全部原合法候选，不按行业另换母体。

海能达 002583 的原候选日完整列表：

- 2024-09-23、24、25、26、30。
- 2024-10-08、09、11、14、15、16、18、21、22、23、24、25、29、31。
- 2024-11-20。

海能达 2024 年 1 月有 22 个原决策日，0 候选、0 实际买入层。原机会日志 22 日均有 `ACT_paused`；同时有 `buy_allowed:false` 21 日、`stock_up:false` 19 日、`sector_up:false` 17 日，原因可并发。

9/20 存在原 CP ID，但机会行 `roles=[]`，CORE_Q/MOBILE_Q 均 false，barriers 为 `buy_allowed:false`、`sector_up:false`，所以不在原合法 pending 母体。raw CP 影子锚不能直接获得一条原候选排名。9/27 同样无原候选，日志为 `buy_allowed:false`。

海能达三笔实际买入原信号：

| 原信号 | 层 | 原角色 | 原 PVR 候选位次 | 原代理成交 |
|---|---:|---|---:|---|
| 2024-10-14 | 1994 | CORE | 11 | 10/15，100 股，8.90445 |
| 2024-10-18 | 2017 | MOBILE | 1 | 10/21，1,100 股，12.00600 |
| 2024-10-21 | 2039 | MOBILE | 1 | 10/22，1,000 股，14.00700 |

上述为原账保存的日线代理成交，不证明实盘可实现。海能达 10/16、18、21—25 原 PVR 均为候选第 1；10/29 第 2，10/31 第 3。

其它实际信号也完整保留：000620 为 2022-01-10 CORE、01-11/12/13/21/24 MOBILE（层 68、69、75、78、113、122）；300666 为 2025-09-26、2026-01-15 MOBILE（层 318、658）；300085 为 2024-10-09 MOBILE（层 1963）。全范围内其余原候选仍保留，不只选这些成交日。

原 PRIMARY 未出现的日期逐日保存在 `ALL_FIXED_MARKET_DAY_COVERAGE.json`，没有新分可比较位置。江丰 10 日、银之杰 2 日虽原机会有 roles 且无 barrier，但未形成 PRIMARY 正规模 pending；现阶段标 `NO_POSITIVE_PENDING_SIZE_OR_QUOTE_NOT_RESOLVED`，不猜测具体原因。

复核入口：

- `ALL_FIXED_ORIGINAL_PRIMARY_CANDIDATES.json`：85 条原候选与事件 ID、原 H1/PVR 位次、同日全候选规模。
- `ALL_FIXED_ORIGINAL_OPPORTUNITIES.json`、`ALL_FIXED_MARKET_DAY_COVERAGE.json`：370 日的原资格与缺候选证据。
- `ALL_FIXED_ACTUAL_BUYS_ORIGINAL_BOOK.json`、`ALL_FIXED_ORIGINAL_INTENTS.json`：12 笔原买入与原 intent 字段。
- `ORIGINAL_CASE_AUDIT_RECEIPT.json`：母体、完整日期、源 SHA、覆盖与限制。

新 Efast/Eslow 可用性与新排名尚未核对，不能提前声称 85 日全部具有新旧可比位次。未造缺失候选，也未使用未来收益选择日期；0 新评分、0 新模型/账户。
