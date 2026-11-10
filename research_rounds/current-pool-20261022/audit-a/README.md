# 当前股票池离线资料准备与归并

本目录只处理数据原料，不修改冻结趋势算法，不运行账户，不发送网络请求。研究时点固定为 **2026-10-22**，历史目标为 2013-01-01 至 2026-10-22；跨午夜不滚动研究终点。当前成员、100 亿元门槛、南向资格、行业均由本轮 master 固定，不重建历史资格。当前存续池的历史研究带有存续选择，不是历史全市场可投资池。

## 已完成的真实资料核验

- `prepared-current-master-v1/` 固定 A 股 master 的 5,576 行：5,500 只有旧行情，76 只暂无旧行情，归并 11,950,884 行；重叠冲突和拒收均为 0。
- 旧 my-quant 原价源共 15,739,264 行、5,517 只，终点主要为 2026-05-15。其 TuShare `volume` 是手、`amount` 是千元；准备器分别乘 100、1,000。不能把其旧前复权文件拼到原价尾部。
- 正式旧 THS refresh 的 1,580 个 raw JSON 均按标准证券代码匹配，其中一部分旧算法曾隔离，但行情本身重叠验证通过。旧批次 `signal_window_checked=1532` 不是可复用原始行情的数量。
- `pilot-offline-verification.json` 对本轮 A 股 6 只真实采样的请求、响应哈希和重叠行情进行离线核验。USHA、USZA、USHT、USTM 分别有 643–746 个重叠日期支持股/元口径；6 只无重叠冲突，全部可延至 2026-10-22。
- `hk-legacy-seven-v1/` 备份旧 7 只港股的 canonical、checkpoint、全部原始响应及协议，共 75 个原文件。没有使用 ETF 或指数代替股票原料。
- `hk-fusion-smoke-4-v2/` 是真实港股 4 只的小范围离线核验：目标区间 12,945 条原始日期观察、12,668 条合法价格观察、3,094 条缺量观察、277 条非法价格观察；0 重叠冲突。恢复旧解析器跳过的 14 条原始记录，未虚构价格。该目录不是全池结项。

## A 股采集计划

当前可执行的共享 collector 计划是 **`batch-plans-v2/`**。旧 v1 保留但不用。

- `01-tail-and-new-001.json` 至 `056.json`：5,570 只，已排除真实 pilot 成功的 6 只；优先补尾，有价源保留约 20 个交易观察的重叠。无旧行情的 76 只使用有限 5 页全史请求。
- `02-start-boundary-001.json` 至 `034.json`：3,314 只起点确认。首日晚于 2013 不等于缺史，多数可能是之后上市；该队列只确认供应商实际可得起点，不追历史成员。
- 每批最多 100 只，`session_preference=auto`；01 每只请求原始 rights 一次，02 不重复请求 rights。全部剩余 90 批上限 14,758 次请求，不是已发请求数。
- 原生市场取当前 master：USHT 可复用旧 USHA 同一标准 SH 代码缓存；BJ 使用已观察的 USTM，不猜成 USZA。
- 网络由共享 `../code/history_batch.py` 及 root 执行。本目录的计划生成器只离线验证 schema。

## 离线融合调用

解释器使用正式研究环境：

```text
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python
```

在 `/Users/bytedance/Documents/ChatGPT/money` 下运行。全池融合应在输入批次停止写入后进行，输出目录必须尚不存在；不要覆盖旧证据。

```sh
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python -B research_rounds/current-pool-20261022/audit-a/finalize_a.py --prepared research_rounds/current-pool-20261022/audit-a/prepared-current-master-v1 --downloads research_rounds/current-pool-20261022/downloads --out research_rounds/current-pool-20261022/audit-a/a-finalized-v1
```

HK 需传入本轮 resolved 主柜台 master 的实际路径，避免 6 个特殊柜台仍处于原生市场待定状态；以下 `MASTER_PATH` 是命令参数位置说明，执行前替换成真实文件：

```sh
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python -B research_rounds/current-pool-20261022/audit-a/finalize_hk.py --master MASTER_PATH --backup research_rounds/current-pool-20261022/audit-a/hk-legacy-seven-v1 --downloads research_rounds/current-pool-20261022/downloads --out research_rounds/current-pool-20261022/audit-a/hk-finalized-v1
```

A 的 `--limit` 和 HK 的 `--symbols` 仅供小范围技术核验；使用它们时不能声明全池完成。

## 输出与桥接口径

`security-manifest.json` 逐股给出 `bars_path/bars_sha256`、`rights_path/rights_sha256`、起止、源状态与缺口。空数据、暂停候选、源边界、错误均保留证券行。`coverage.csv` 便于扫描，`source-evidence.csv` 记录每个来源，`unresolved.csv` 只列未解决项目而不删除其证券。

标准代码为 `600000.SH`、`000001.SZ`、`920000.BJ`、`00700.HK`，日期为 parquet `trade_date` 时间戳。价格保持原价。每条保留来源路径、源类型和观察时点；无法证明旧缓存真实获取时点时为空，不能补写成历史当日已知。

HK 的 `bars/` 保留所有原始日期记录，包括缺 OHLC、缺量、几何异常；`signal-bars/` 直接复用冻结 `eligible_prices` 的价格观察掩码。**缺量/零量不删除合法价格观察**，使用独立 `price_eligible` 与 `volume_eligible` 标记；不会填 0、按后值补价格、推断停牌或虚构成交。OHLC 几何非法不能进入价格状态。

HK 的量/额维持原始线缆数字，不默认乘每手股数。`unit-crosschecks.csv` 按证券检查成交额/成交量与价格的数量级关系；这是算术一致证据，不是官方单位定义认证。报价币种继承 master，例如 00770.HK 为 USD，不能统一贴成 HKD。

A rights 由原有解析器报告已支持记录与未解析原文；HK rights 仅保留原文，不套用 A 股每十股语法。`received_current` 只表示原响应收齐，不证明没有漏事件或完整支付日账。缺支付日不会被说成原始数据未收到，但任何账户适配仍需单独说明价格、分红及股本事件口径。

短页/空的最终页可证明供应商可得边界，**不等于交易所上市日期**。对截至研究终点请求成功但末条早于终点的证券，标记为 `latest_source_bar_before_end_suspension_or_source_limit`，不把“无新记录”自动解释为停牌。

## 验证与边界

`offline-validation-tests-v2.txt` 记录 22 项技术测试全部通过，覆盖单位转换、缺量价格钟、重复日期、冲突隔离、无重叠桥接缺口、端点/原始响应/导出篡改、起点和尾部认证分离，以及被解析器遗漏的原始观察恢复。测试使用的合成夹具不作为真实行情证据。

所有全池完成标记都由实际覆盖生成。本次只交付准备器、有限技术核验和融合工具，尚未运行 A/H 全池最终归并，更没有运行账户。`data_collection_complete`、算法输入适用、完整行动账及账户可运行是不同状态。
