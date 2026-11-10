# 本地证券身份与补源清单审计

本次有界检查只读现有表、代码、队列 metadata 与三只小样本，没有联网、刷新、回测或上传。可用结论是：本地不止 1,709 只策略股票；既有 canonical 5,517 只、当前 A 股名单 5,576 只及 239 份退市补源可用于后续连接。但这些资料尚不是完整历史时点证券全集，也不是统一质量的行情输入。

## 真实证券表

| 本地表 | 证券数 | 上市日期非空 | 退市日期非空 | 时间含义 |
|---|---:|---:|---:|---|
| my-quant `processed/securities/securities.parquet` | 5,519 | 0 | 0 | 手工代码名称 workbook；run created_at=2026-05-18T06:58:20Z |
| TradingAlarm `results/stock-data-audit/master-crosswalk.csv` | 5,563 | 5,563 | 339 | BaoStock 2026-10-18 采集的当前 master，保留部分已退市身份 |
| money workspace 当前 A 股 `master-input.csv` | 5,576 | 无该字段 | 无该字段 | observed_at=2026-10-22T23:49:26.064622+08:00，snapshot_date=2026-10-22 |

my-quant 表 schema：`symbol, exchange, market, name, list_date, delist_date, source, schema_version, cleaning_version`；symbol 唯一，全部 `market=A_SHARE`、`source=manual_a_share_code_names_xlsx`。SZ=2,892、SH=2,313、BJ=314；没有实际历史板别字段或 available_at。原 workbook 只有序号、代码、完整代码、名称、市场；其 openpyxl 创建时间不是提供商公告时间。

crosswalk schema：`code,code_name,ipoDate,outDate,type,status,symbol,has_local_bars,retired,out_date`。SH=2,467、SZ=3,096，全部 type=1；status=1 有 5,224，status=0 有 339；BJ 不在该表。ipoDate 范围 1990-12-10—2026-10-15，outDate 范围 1999-07-12—2026-10-19。原 `baostock-master.json` 共 9,011 行，含指数等其它类型，不能直接算成 9,011 只 A 股；crosswalk 的 5,563 行代码、名称、IPO/退市日期、type/status 与原 JSON 字段逐项一致。

上述 ipoDate/outDate 是提供商标注的事件生效日期，**不是当时可得时间**。原 JSON 只有 fetched_at=2026-10-18T00:17:32.182603+08:00，没有逐行 historical available_at/公告版本链；其中 601059、601198 的 outDate=2026-10-19 还晚于 fetch 日，不能擅自解释为当时已发生或补造公告时点。该 master 自带限制：不是完整历史上市名册或历史名称/ST 状态证明。

## 生成代码直接证据

- `/Users/bytedance/repos/my-quant/src/my_quant/data/builders/a_share_securities.py:21—25` 定义手工代码 workbook 来源；`95—119` 转换时 **显式将 list_date/delist_date 写为 NaT**；`266—303` 交易所来自完整代码、市场别名或代码推断，并非历史板别台账。
- 同库 `data/schemas.py:27—42` 只有上述证券 schema；`cleaning.py:288—299` 转日期、保留字段，不创造上市退市事实。
- 同库 `data/sources/__init__.py:503—521` 存在 TuShare `stock_basic` 抓取能力，但代码固定 `list_status="L"`。在 raw/meta 相关文件名的有界盘点中未找到 stock_basic 实物，不能将可调用代码当已持有历史 L/D/P 全集。
- 同库 `data/builders/a_share_history/planner.py:302—328` 读取上市/退市字段，但先在 `313—314` 剔除有 delist_date 的证券；即使以后补了退市字段，该“current listed”规划路径也不能自动当历史全范围规划器。
- `/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/fetch_stock_master.py:13—19` 保存 query_stock_basic 原响应与 fetch 时间，明确承认 current snapshot / provider-retained delisted 限制。crosswalk writer 的精确源码未在本次有界搜索中定位，故只认已核原 JSON 字段身份一致，不宣称完整生成链已经认证。
- 同目录 `fetch_ths_retired.py:15—16` 只取 missing-retired 中 outDate≥2015-01-01；`33—37` 以搜索确认退市 native ID 并记录下载状态、观察首尾及 master_out_date。日线 first/last 与 outDate 明确是不同字段。
- `/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-a/prepare_a.py:1—4` 明说名单是当日 current master、历史行情不是历史资格全集；`14—15` 列既有 canonical 与 THS 缓存输入。

未执行以上生成/抓取脚本。TradingAlarm AGENTS 首段及 scope 的 2026-10-22 存续快照是旧研究数据范围事实；本次遵最新要求核历史资料，未把它伪装 PIT。

## 退市覆盖与身份并集

复用 ROOT 已生成的 canonical `BAR_SYMBOL_COVERAGE.csv`，未重复扫描 1,573 万行 OHLC：

- provider 339 个退市身份与 canonical 5,517 只交集 **15**，324 个不在 canonical。
- `ths-retired-collection.json` 实际 242 条：downloaded **239**，unresolved_identifier **3**（000022、000043、300114）。239/239 对应 raw JSON 文件存在，与 canonical **交集 0**；本次只核文件存在与旧下载记录，未逐股读取/认证数字、权息、单位和执行质量。
- canonical + 239 文件对应身份的并集为 **5,756**。这只是证券身份并集，不代表 5,756 只具有相同期间、价格、单位、PIT 或公司行为质量。
- 当前 A 股 5,576 与 canonical 交集 **5,500**，当前名单另 76 只不在 canonical；canonical 另 17 只不在当前名单。
- canonical ∪ 当前 A ∪ provider 339 退市的身份并集为 **5,917**，**不是行情可用数或完整历史全市场数**。

覆盖例：600193 原 IPO=1999-05-27、outDate=2026-07-06，canonical 观察 2000-06-27—2026-04-27；600421 原 IPO=2004-06-07、outDate=2026-06-26，canonical 到 2026-04-29。它们有一些历史行情，不代表已覆盖退市终局和清算现金。

未覆盖例：600001（邯郸钢铁，outDate=2009-12-29）、600002（齐鲁石化，2006-04-24）既不在 canonical，也不在本次 2015 后补源名单；600005（武钢股份，2017-02-14）、600068（葛洲坝，2021-09-13）不在 canonical，但在 239 下载记录与实际文件中。完整 339 交集及 239 文件清单已保存。

canonical 是 1995-04-06—2026-05-15 的现存观察，不是全证券上市以来全历史。ROOT 另已查到 831 只恰 6,000 行且一些真实观察起点晚于请求起点（例如 000001 请求 1991-04-03、实际从 2000-12-13），本报告不把 first/last 变成 IPO/退市事实。

## 当前全 A 股缓存和 May—June 补源

实际完整工作目录在 `/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/`，repo 内同名目录主要是入口镜像，不能据镜像没有大文件判断行情不存在。

当前 A master 有 SH=2,318、SZ=2,906、BJ=352；旧 `audit-a/prepared-current-master-v1/coverage.csv` 的 5,576 行中，5,500 有 bars、共 11,950,884 条；76 无 cache。旧准备表 last=2026-10-16 的 1,578 只，last=2026-05-15 的 3,913 只，另有早停源。不能称 5,500 都已到 10 月。

`downloads/a-tail-queue-01/queue-summary.json` 终态 **halted**：56 批计划、42 批完整完成，第 43 批失败。对该已存 queue-state 声明目录的小 checkpoint 检查得到 **4,289** 个 unique complete 且 history 文件存在（含失败批已保存 89 个）；**4,264** 个 metadata 首尾包住 2026-05-18—06-30。

旧 prepared 中 **1,580** 只首尾包住上述区间，与队列补源范围并集 **4,552** 只。此数只证明已存 metadata 的**日期范围包含**，不是逐交易日连续、有效量价或可成交认证；不能据此宣称≥5,000 只统一补齐。该 scoped 目录没有完成的全池 finalizer 收据；4,289 份补源需连接与质量复核，不能给其它 workspace 已 merge/未 merge 数作无证断言。

三只实物小例：

- 000001：此 queue 索引未找到完成记录，但旧 `prepared-current-master-v1/bars/000001.SZ.parquet` 实际有 May18—Jun30 **31 行**，两端均存在。
- 300666：`a-tail-queue-01/batches/01-tail-and-new-022/history/USZA300666.json` 实际 750 行，2023-09-05—2026-10-22；May18—Jun30 **31 行**，两端存在。
- 603061：`…/batches/01-tail-and-new-040/history/USHA603061.json` 实际 750 行，2023-09-12—2026-10-22；May18—Jun30 **31 行**，两端存在。它在旧 prepared 表仍只到 May15，说明补源已存在但旧 prepared 不是最新整合清单。

THS 两源自报未复权、wire volume 单位不可全市场推断，`account_ready=False`；不能直接与 canonical 拼接就认一致。此次不刷新、不自动运行 finalizer，也不把 1,709 只旧策略池当本地行情全集。HK 全池与队列另有资料，本审计没有逐项认证其全母体，不把 HK 少数样本或 ETF 混为 A 股数量。

## 交付与边界

`AUDIT_RECEIPT.json`、`MYQUANT_SECURITY_MASTER_CONTENT.json`、`PROVIDER_HISTORICAL_IDENTITY_AND_RETIRED_COVERAGE.json`、`ALL339_PROVIDER_RETIRED_JOIN_CANONICAL.csv`、`ALL239_DOWNLOADED_PAYLOAD_EXISTENCE.json`、`A_TAIL_QUEUE_METADATA_INDEX.json` 和 `THREE_FIXED_ACTUAL_PAYLOAD_EXAMPLES.json` 保留计数、schema、路径和源 SHA。`RAW_MASTER_IDENTITY_CHECK.json` 核 provider 字段一致性；`BOUNDED_RAW_META_INVENTORY.json` 记录有限盘点范围。

尚缺完整历史证券名册/板别变更、历史 available_at/vintage、完整退市身份与后续公司行为/清算，行情覆盖还需独立质量连接。这些缺口不抹去已有原料，也不构成已具备 PIT 的结论。审计至此收口，不继续遍历或补数。
