# 七固定日退市补源与旧 1709 身份核对

239 份原 THS 退市文件完成一次读取，3.05 秒，666,823 行；239 可解析、0 错误，239 个保存 bars SHA 与原生成规则一致。没有无效日期、重复日期或乱序文件，全部保存 `page_budget_exhausted=False`。这些只是格式及数值证据，不是权息、交易日历或执行认证。

退市补源始终单列，**没有加入本轮 canonical 5,517 排名，也没有计算 PVR、新评分、排名或未来收益**。

| 固定日 | 239 中精确有行 | 无精确行 | 当日 OHLC 与正量额数值可用 | 有行样本历史正 close+amount 数（含当日）最少值 |
|---|---:|---:|---:|---:|
| 2022-01-10 | 173 | 66 | 173 | 378 |
| 2022-01-24 | 173 | 66 | 173 | 388 |
| 2024-09-24 | 33 | 206 | 33 | 1,613 |
| 2024-10-08 | 33 | 206 | 33 | 1,618 |
| 2026-01-15 | 6 | 233 | 6 | 1,928 |
| 2026-01-20 | 6 | 233 | 6 | 1,931 |
| 2026-05-15 | 0 | 239 | 0 | NA |

七日共 1,673 条身份/日期记录。当日有行样本中未出现重复日期、字段不可解或价格/量额基本数值不合格。缺行保持缺失，不解释成尚未上市、已经退市、停牌或零收益。first/last 只表示该原文件的观察范围，不能当上市/退市日期。

逐股逐日保存精确原 OHLCVA、排除当日的过去观察数、截至当日的数目，以及反向连续有效**源观察行**数；这些都不是市场交易日连续性、PVR 暖机或买入资格判定。日期统计不使用之后的价格或收益。

源统一声明 `THS id=210`，adjustment 为 `fuquan omitted; raw-price semantics cross-checked on688008, require per-source validation`。没有独立的 volume_unit/amount_unit 字段，不能按同名字段就与 canonical 的价格、量额单位直接合并。抓取时间为 2026 年，并非这些历史日期的 available_at。

## 旧 1709 精确身份

原 `STOCK_MANIFEST.json` 固定 ID 为 1,709，包括 NA 条目，不以 complete 条目替换名单。与 canonical 5,517 精确交集 **1,681**；旧池有 **28** 个 ID 不在 canonical，canonical 有 **3,836** 个 ID 不在旧池。

旧池 SH=919、SZ=784、BJ=6；canonical BJ=313。旧 6 个 BJ 中 5 个精确匹配，920138.BJ 缺失。两边字符串格式均为六位代码加 `.SH/.SZ/.BJ`，未发现格式异常；没有经独立验证的历史旧代码/920xxx 日期身份映射，**不强行作 alias 合并**。28 个缺失 ID、其原 status/mode 和源覆盖字段完整保存，不根据未来赢家、后续表现或名字相似性补映射。

旧池条件证据：`a-share-selection-e0-20261024/PROTOCOL.md:5` 是当前公司市值 >100 亿元、2026-10-22 名册/行业固定；README:9 说明市值实际观察于 10/24，README:38 区分原始 5,576 与合格 1,709。该旧成员标签仅描述旧当前快照筛选，不是历史市值可投资资格。

## 数据版本边界

上轮 **4,552** 只是旧 `current-pool-20261022` prepared 加 tail queue 的日期首尾范围证据，**不是全 workspace 后段行情上限**。后来的 `a-share-selection-e0-20261024` v2 声明原始 5,576 收齐；其 `audit/data-closeout-v2.json` header 实际为 `data_pool_closed`，recorded_at=2026-10-24T23:20:28+08:00，同时明确仍有未知、不是 PIT 或精确券商账认证。

本次只保存该 closeout 的 header 与 SHA，没有扫描 5,576 份 v2 payload，也没有擅自切换排名数据集。本轮按指定 canonical 5,517，239 退市源仍另列；不同版本不能混称一套完整历史全市场。

交付入口：

- `AUDIT_RECEIPT.json`：239 一次读取、七日总数与输入 SHA。
- `ALL239_SEVEN_DATE_OBSERVATIONS.json`：1,673 条精确日原值及过去观察数。
- `ALL239_PAYLOAD_FORMAT_AND_RANGE.json`：原文件范围、来源、时间、哈希、异常与单位限制。
- `CANONICAL5517_EXACT_OLD1709_MEMBERSHIP.csv/json`、`MISSING_OLD1709_IDS.json`、`OLD1709_EXACT_ID_AUDIT.json`：精确身份 join。
- `DATASET_VERSION_SCOPE_NOTE.json`：旧范围边界、v2 closeout header 与 SHA。

原料没有写入或刷新，未联网、上传、跑账户或读取新 top20。审计至此封口。
