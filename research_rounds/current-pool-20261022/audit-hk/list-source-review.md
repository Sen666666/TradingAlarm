# 当前港股普通股票名册：已有来源离线审查

基准：用户授权的 2026-10-22 当前存续 A/H 固定快照池。本审查只盘点港股名单来源，不继续历史南向或股本链。网络请求 0 次，不启动应用、不执行采集器、不修改缓存；仅新增本报告。

**结论：已查来源中没有可确认为“2026-10-22 全部存续港股普通股票”的完整名册。** 已找到应用直接市场分类证据，足以隔离多数跨品种污染；但行业成分、搜索结果和应用市场选择器不能分别冒充完整普通股票代码表。

## 来源与实际覆盖

正式仓库基目录：`/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/`。

| 已有来源 | 日期与实际覆盖 | 字段与边界 | 是否完整当前普通股票名册 |
| --- | --- | --- | --- |
| `data/market.json` | `capturedAt=2026-10-16 13:56–14:04`；全部市场 1,143 行，其中 HK 87 行：UHKM 84、UHKI 2、UHKT 1 | `stocks` 含 symbol/code/name/market、行情等；属于应用已捕获证券，夹指数与基金，无完整市场总数/挂牌状态证据 | 否，仅捕获观察 |
| `data/discovered.json` | 157 行，其中 HK 58：UHKM 4、UHKD 15、UHKW 33、UHKI 6；文件无逐行观察日期 | symbol/code/name/market/aliases；搜索命中的扩展集合，明显混债券、窝轮、指数 | 否，仅搜索名称观察 |
| `research/data/ths-index-history-20261018/discovery/search-results.json` | 40 条查询，2026-10-18 20:25:26–20:25:50 +08:00；223 返回行，HK 去重 63：UHKI 58、UHKT 5 | 每次 query 的 pattern/received_at/body_sha256/results；results 含 symbol/code/name/market | 否，定向搜索，主要指数与基金 |
| `research/data/ths-index-history-9603-20261018/discovery/search-a.json` | 28 条查询，2026-10-18 21:10:22–21:10:39 +08:00；214 返回行，HK 去重 65：UHKI 48、UHKT 5、UHKM 8、UHKD 2、UHKW 1、UHKB 1 | 同上，查询命中不是市场枚举 | 否，定向搜索，混多个品种 |
| `research/results/ths-industry-snapshot/memberships.json` 与 `block_hk_industry.ini` | 观察于 2026-10-18T08:56:04.157174+00:00；HK ConfigVer=`20260718.072701\|20260718`；2,765 个唯一原始证券、2,765 条成员边，70 个有成员板块；原始市场 -79 有2,459条，-78有306条 | block_code/block_name/raw_market/raw_code/source_version/observed_at；没有当前存续状态或完整性总数；ConfigVer不是观察日或挂牌有效日 | 否，仅旧版行业成员。不能因数量较多贴全池标签 |
| 应用 `Documents/BlockUpdate/block_hk.ini` | ConfigVer=`20261022.163301\|20261022`；41个命名分组 | 含港股通、恒指成分、行业、ETF等选择性分组。`CA55=香港ETF` 有448条，原始市场-76；`CABE=待上市港股`有3条；`C06C=港股人民币双柜台`有24条 | 否，不是普通股票全市场成员表；待上市与重复柜台尤其不能自动入普通股票池 |
| 应用 `Documents/BlockUpdate/block_other.ini` | ConfigVer=`20260703.172456\|20260703` | “所有港股”是市场选择器 `177,178,`，不是证券代码集合；可用来解释主板/创业板与其他品种编号 | 否，仅分类与选择器 |
| `research/data/hkex-delisted-issuers.html` 及 `research/results/stock-data-audit/hk-universe-source-audit.json` | 既有采集日期2026-10-18；801条、731个唯一代码 | HKEX权益披露的已退市公司名称清单，仅code/name；旧审查亦标明覆盖完整性未建立 | 否，退市名称来源，不能用于当前存续全池 |

workspace 的 `TradingAlarm/data/market.json`、`discovered.json` 与上述正式仓库计数相同，不构成独立完整性证明。

## 市场与品种：已有直接配置证据

应用资源目录：`/Applications/同花顺.app/Contents/Resources/`。

`MarketNumber.plist` 直接提供市场编号到字母代码的映射；`MarketClassMap.plist` 把177–182归入176；`BigMarketNumber.plist` 为 `HK→176`。`MarketPageRelation.plist` 把UHKM/UHKG映射到港股页面，把UHKW/UHKB映射到窝轮牛熊页面。

| 数字编号 | MarketNumber | `block_other.ini` 中文分类及原始物理行号 | 当前普通股票候选处理 |
| --- | --- | --- | --- |
| 176 | UHKI | 港股指数，第765行选择器为-80（同文件名称在第32行） | 指数排除 |
| 177 | UHKM | EEEE=港股主板（518行）；EEEE=177,（882行） | 主板股票候选来源；还需当前代码列表和品种/存续核对 |
| 178 | UHKG | EEED=港股创业板（519行）；EEED=178,（883行） | 创业板股票候选来源；不能只取主板漏掉GEM |
| 179 | UHKW | EEEC=港股认股证(窝轮)（520行）；EEEC=179,（884行） | 排除窝轮 |
| 180 | UHKT | EEEB=港股信托基金（672行）；EEEB=180,（1003行）；另有香港ETF分组原始市场-76 | 基金/信托市场不能整体归普通股；ETF排除 |
| 181 | UHKD | EEEA=港股债券（673行）；EEEA=181,（1004行） | 排除债券 |
| 182 | UHKB | EEE9=港股牛熊证（521行）；EEE9=182,（885行） | 排除牛熊证 |
| 183 | UHKP | 本次已查资源无足够中文语义关联 | 保持未知并排除候选自动纳入，不凭字母P猜成普通股或优先股 |

“所有港股”的 `B=所有港股` 在31行，`B=177,178,` 在764行。这是获取股票候选的最短本地路线提示，**不是已有全股票清单**。行业缓存 -79/-78 与177/178按8位有符号整数转换一致；须保留原始编号，不能把“同一算术值”误称逐条证券类型已经验证。

目前没有找到一个能直接证明“普通股”与优先股、临时代码、双柜台、待上市证券等边界的完整逐行类型/上市状态表。仅按名字排除“ETF”“牛”“熊”不可靠；仅按5位数字范围也不可靠。UHKM/UHKG是候选市场，不应把这两个市场名直接改写为已验证普通股属性。

## 本地名称缓存盘点

只读查看了 `/Users/bytedance/Library/Containers/cn.com.10jqka.macstockPro/Data/Documents/stockname/`：现有文件为32、64、128系列的 `_0.ini`、`_0_base.ini`、`_1.ini`，没有176系列港股名称表。解析后的章节只出现32–39、64–70、129–131等市场编号，没有177/178完整名称章节。

这些文件在本次查看时mtime为2026-10-22 23:34左右；部分64系列ConfigVer已写20261023。**mtime、ConfigVer和名单有效日期是不同概念**，不能用文件mtime为股票存续状态背书。本次没有执行任何刷新动作。

已查看应用资源的文本/配置文件名及市场映射；没有扩展到二进制反向工程，也没有读取认证票据。未见已保存HKEX当前普通股票全量文件或完整市场分页回执。这个结论限定于本次所列目录和证据，不能外推为该数据在其他地方不存在。

## 最短实际来源路线与准入条件

1. 复用已经授权的同花顺只读通道，按明确市场177/UHKM及178/UHKG枚举**当前完整代码表**，保留源总数、页码、返回数、去重数、缺页检查和快照时间。当前研究薄补数器应读取已冻结的名册输入；尚无完整名册时不以“已有行情者”构池，也不自动枚举未知网络接口。本审查没有发送此类请求。
2. 若现有通道只能按符号取行情、不能枚举证券，则需取得一个带证券种类及挂牌状态的当前完整名单来源；已保存的行业成分与关键词搜索不能代替。取得前将港股名册标为未就绪，而非缩为旧小池。
3. 以逐行来源字段确认普通股、存续状态、主板/GEM和观察日期；基金/ETF、窝轮、牛熊证、债券、优先股、待上市和未知类型不自动混入。人民币双柜台与临时/旧代码需保留关系，避免同一公司被计成两只独立股票。此处只要求当前快照关系，不恢复历史南向或股本链。

## 关键证据哈希

| 文件 | SHA-256 |
| --- | --- |
| 应用资源 `MarketNumber.plist` | `59128db839b9fbc2eb3ab27ad4b69097d0dc873411b2d69d79e0eb0bf4de63e6` |
| 应用资源 `MarketClassMap.plist` | `3bf4ed99a77bed3e651e300094f948cfc84cfc3f9b2b31d0413a23f53f263edf` |
| 应用资源 `BigMarketNumber.plist` | `b48ac4077f9e9c044a12b7d7d16ad9168f89485ba60dca89a7b1b39d0c6e0f6c` |
| 应用资源 `MarketPageRelation.plist` | `773a2333c6a52e02ab430d0b409f4784a7967589cc289d8905890fd8749a4ab3` |
| 应用 `BlockUpdate/block_other.ini` | `d27ede6f618bfea4180bf7c5f4171c8300f14da46332319e906552161f991663` |
| 应用 `BlockUpdate/block_hk.ini` | `ced192cc67a8936f7c9e6394f6f942876ca5a9623ce9d74e4c5172a3ee1084c1` |
| 已保存及应用 `block_hk_industry.ini` | `3c65c6845d0fe0afbad152c0dbc03a23dc4ddb1cff2341b58e7fad761ffa15fa` |
| 定向搜索 `search-results.json` | `992d04d0a57ca96909d099f424f3fab3509454473e2a8943316c770d5cb07253` |
| 定向搜索 `search-a.json` | `1cd08941f98d7f6120ab13b92850e16a051ae8bf989ad026b40f0edc8f20243f` |
