# TradingAlarm本地数据盘点

状态：有限本地只读盘点完成。0网络连接、补数、模型、回测或策略改动；未读settings、private/session、凭据、认证抓包或账户数据库。完整目录、实际schema/统计与34个文件SHA见 `INVENTORY.json`；脚本只处理下列已知根与固定manifest，没有全盘搜索。

## 找到的实际数据

| 根/文件 | 已核内容与覆盖 | 执行证据边界 |
|---|---|---|
| 两处 `TradingAlarm/data/market.json` | repo及money副本字节相同；1143标的非空raw numeric quote；17标的、3205分钟价点，**仅2026-10-16**。A股/ETF/指数约179–186点，HK样例216点；09:30至13:58/14:04/14:05 | 不是多年度分钟历史；当日不完整，部分成交量/金额全缺。quote是单时点字段号快照；bid/ask/depth映射**未核，UNKNOWN**，不能断言有或没有真实双边报价 |
| money `TradingAlarm/runtime/market/update-20261104-153015-646272/prepared` | manifest为1709股票+90行业，1799 raw bars；1797最后日至2026-11-04，2至10-30。facts/signals各仅418文件。实际Parquet为trade_date/OHLCV/amount/quality/source列；抽样海能达/盈新2013起、中船特气2023起、行业样例2007起 | 日线，不是盘口/tick；1799 raw不等于1799份当日新facts。当前存续池/分类，不是PIT历史成员；只抽查4份footer/时间列，未重新逐行验全池 |
| `runtime/paper-quotes/*` | 8批、9个symbol；42个history response receipt。history真实schema为date/OHLCV/amount，source为id210、period16384，日期2026-10-12至11-05 | 名字不是频率证据：它取的是日线尾窗/日线OPEN。早盘取到当日bar可能仍在形成，不是整日完成K，更不是连续逐笔quote流 |
| 最新prepared/actions | 1709 JSON、16720事件，effective date 2013-03-04至2026-11-04，全部declared_research_proxy | paid_at与新股可卖时间已知数均0；无逐事件publication/receive字段。能提供部分分派/单位桥，不能证明完整到账/上市时钟 |
| repo `research/data/ths-actions-688008.json` | 蓝旗科技8条历史权益，确有announcement_date/record_date/ex_date | 公告**日期**是有限正面证据，不等于原始公告发布时间；pay_date/new_share_tradable_date仍未知，不能外推全池完整PIT CA |
| repo `research/data/stock-features` | footer10775850行，manifest5204股；schema是均线/ATR/momentum等派生字段，外部source指向my-quant adjusted_daily_bars | 不是原分钟/执行数据；manifest明列幸存、历史ST/limit/CA缺口。未读631MB全表 |
| repo `research/data/baostock-master.json` | 9011行，code/name/ipoDate/outDate/type/status快照 | 没有日度ST/停牌路径；当前名称或status不能回填历史 |

已明确定位的研究原根还有 `money/research_rounds/a-share-selection-e0-20261024/{data-adjudicated-v2,prepared-v2,inputs-v2}`、`pvr-act-comparison-20261027/execution-rules-v2.json`；本轮只复核规则schema与已有源表。现规则是venue/quantity/availability/fee版本，未见真实daily limit、halt、tick、is_st字段；availability是明确研究proxy。repo `research/data` 的日线/rights/指数/forward-observation metadata及docs/catalog已查看；其它研究结果树不作无界遍历。

## 时间戳不能混用

- **找到本地响应接收记录：** `paper-quotes/pages/.../receipt.json.received_at`。真实collector `history_batch.py:202–207`是send→receive_matching→保存raw body→记录now→decode；它能证明该整包在本机采集流程中的观察时刻，不能证明交易所逐bar发布、第一byte到达、钟同步精度或某笔订单可成交。缺receipt恢复时221行明确`received_at=None/recovered_at`，恢复时钟不能冒充接收时钟。本轮不读raw binary验证网络包内容。
- **ingestion：** raw `observed_at`大部分历史为空；抽样海能达3318行中3202空、盈新3326中3313空。`desk/refresh.py:143–148`在规范化tail后写datetime.now，因此非空值是本机处理时钟，不是每bar原始feed receive/publication。
- **本机数据发布：** current.json `published_at=2026-11-04T15:52:41.772227+08:00`是prepared snapshot发布；不是2013—2026每个历史bar的当时发布时间。
- **近似/合成：** app `capturedAt`由build_data.py:13–14、59、63手写批次/默认标签；不能给每个分钟点作真实receive_time。分钟点日期/HH:MM来自provider packed minute标签，没有子秒或委托时序。研究known_at/15:05或calendar OPEN也是模型可知时钟，不能代替以上采集记录。

## 找到／范围内未找到／未检查

**找到：** 小样单日分钟价、单时点raw quote、长历史日线、CA部分日期、日线响应的本地receipt。**本次范围内未找到已核证可用：** 覆盖No60原历史的多年度宽池分钟/tick/双边depth、真实逐笔交易所publication、委托到达/fill/cancel ACK、完整PIT ST/停复牌/limit。**未检查或未核：** raw numeric quote映射、其它未列目录，以及排除的认证抓包/凭据/私有DB；因此不宣称整台机器绝无其它数据。

## 权限证据

README与docs/DATA_SOURCES记有原用户对本人客户端指定行情服务的只读研究授权；本次未使用它连接服务。docs/SECURITY:13明确私有携带不等于公开或商业再分发授权。 inspected README/docs及源manifest未发现赋予这些第三方市场数据一般再分发/商用许可的明确条款。结论为 **第三方数据许可/具体用途合法性UNKNOWN，不作法律保证**；文件存在、来源公开或个人有客户端均不能替代许可。原用户本地只读授权、来源使用许可与当前服务可用性分别记录，不能相互冒充。

本盘点只说明已有能力/缺口，不补数据、不运行统计模型，也不据此给真实交易收益或悲观收益界。
