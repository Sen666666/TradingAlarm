# G/S R4首次真实历史金融绑定：两个两日技术前缀

状态：两条已授权主路径与技术核验完成，供独立审计；没有扩展日期、换政策或启动实盘。

严格上游绑定：R4 adapter `1649a09c…669665`；loader R2 `7c1f0e66…676cbbf`；输入包 `1fbcf3cf…788d82b`；F1 bootstrap `693bcafe…a34bcc9`；合同 `a26b1959…05bcc50`。`FULL_PREFIX_AUTHORIZATION.json`在首个金融事件之前写入，记录全部执行源SHA。原R4、loader、输入、F1、旧SC/PVR及生产文件未改。

## 实际路径与逐日行为

两窗各从原1m新账起步，继承完整市场F1 State/Source/ordinal/proof，账户K/持股/试仓事实/订单/消费/损耗/应收均从0开始。首开没有起点前意图。没有导入SC/PVR金融检查点。

| 主路径时点 | 行为 | 实际账户 |
|---|---|---|
| 2022-01-04 OPEN | 空账，0旧意图、0预留、0fill | 现金/NAV均1m |
| 2022-01-04 CLOSE | 300只真实前置候选形成计划 | 当日无买入 |
| 2022-01-05 OPEN | 32预留、32买入fill | 32股；现金180575.91610470275 |
| 2022-01-05 CLOSE | 136项后续计划，未进入1/6 | NAV993722.91610470275；无待卖 |
| 2025-07-01 OPEN/CLOSE | 首开空账；收盘319只前置候选形成计划 | 当日无买入 |
| 2025-07-02 OPEN | 21预留、20买入fill、1零成交 | 20股；尚冻结1张未成交单 |
| 2025-07-02 CLOSE | 原单到期同步cancel/ACK；245项后续计划；3项退出义务等待7/3 | 现金207224.0342408694；NAV990254.0342408694 |

这只是技术前缀的实际账，不是收益检验。未据这些负浮动调整任何规则。

2022实际层：29 mobile/confirmed，3 core/probe；买入费用279.71639529725。2025实际层：20 mobile/confirmed；费用247.8997591306。2025的21个mobile凭据在预留时消费，其中20成交，不能说21成交。605389.SH预留1800股，原日线H/L禁交易代理下high=low=42.46、buy_allowed=False，零fill；7/2收盘原deadline取消ACK，未转赠receipt。136/245末日新计划均标`pending_after_authorized_terminal`，不是失败成交。

每笔实际计划的优先键、资格、canonical ID、实际预留及所有原始路由拒因：`analysis/PLAN_FUNNEL.jsonl.gz`。每只股票的源头资格/信号缺失理由与完整候选域：各CLOSE JSON的`mapping`。重复S/G/T拒因不是独立机会；末日计划未尝试下一日执行。

## 绑定改动与未改部分

`native_capital.py.diff`、`funding_coverage.py.diff`列出相对冻结R4的改动：只读真实providers、独立HistoricalReceipt类型与真实payload/source守卫、证券日期级数量/费用、原ordinal、真实H1/PVR元数据及日期型F1→收盘clock转换。Policy源码完全复用。没有改变合同数值、F1、I/CP1、PVR公式、用途路由或R4资金逻辑。

真实receipt保留完整原canonical payload、原scale_id/episode/source_segment/形成与确认身份；runtime合同scale=21另列。guard核payload哈希、当前canonical registry身份、确认时点、结构与intent对齐；不伪装fixture source。注册表是冻结输入缓存，仅用当日receipt ID查询，不能作为提前证据或已消费事实。`policy.consumed`只由原子真实预留更新。

原F1 State.scope别名不改，policy_scope另映射。F1内部仍使用原日期字符串；与原生aware clock比较时显式映射研究收盘15:10+08。ACT cutoff、confirmed、known都用原`date.toordinal()`，不用synthetic从1起计数。

PVR_SLOT1只在CLOSE对本次R4前置计划的唯一股票域冻结一次；NA留原H1槽，PVR同分沿原H1/code，core/mobile共用股票槽。OPEN、费用、gap、partial后不重排。用途/角色顺序沿R4，不运行two-pass、D1、C1或其他政策。

原`FrozenMarket`负责marks/quote/window/quantity/fees/lag，原Decimal ledger负责预留、费用、fill、T+1、结算和库存。bounded provider注入从原文件逐值冻结的原始行（含过去21个正量观察，覆盖原20观察容量公式）；不重置原source origin，不另造成交账。历史入口强制真实窗口，禁止`T.window`生成成交回退。原日线最终H/L/C/volume代理仍存在，不认证真实开盘可执行。

## 权息与桥

9项原权息事件均记录原source_id、实际cursor和原条款；688608.SH的7/2送转1.40通过原生split callback，现金1.20/旧股和未知支付日保留。所有事件发生时旧股数量均0，因此现金应收/到账为0，不给除权后新买补领旧红利。价格factor=1.4148775831565499与share ratio=1.40分离，旧保护线按因子换到raw域。没有猜支付日。

全部10个主路径事件快照的现金、NAV、费用、层现金贡献桥为0差；另从实际FillReceipt股数独立加总核同原生库存lots。原生lot↔经济层映射由R4继续强断言。实际3项7/2退出仅request、0实卖，execution locks及持仓保留，未提前释放现金或风险。

本历史前缀没有除权前持仓、正额红利支付、实际卖出或实际partial；这些不能冒称本次历史验证已覆盖，继续复用已独审R4合成证据及显式unsupported拦截。一般零股/不支持的事件不绕过。未知支付保留应收、不融资。

## 物理前缀、恢复与失败记录

主路径使用已审实体两日输入；`full-input-fixtures/`从同一原数值缓存补读真实下一会话输入行（1/6、7/3），仅作物理截断对照，金融days仍是原两日。没有执行这些后续日。四个OPEN/CLOSE完整经济、决策、F1状态和所有流水逐项一致；不同输入范围的原始cache/provenance不冒称同一文件。

每条主路径首日CLOSE后在新进程只接续第二日。`export-recovery/state-audit/VERIFICATION.json`额外对10个主检查点：原始owned pickle完整可变状态与另进程受源/身份守卫的restore逐项类型化哈希核同，包含账户所有字段（仅market/facts另列）、动态lot ID、ACT、锁、receipt/core epoch、funding、全部流水、市场运行字段、facts线和输入绑定。该审计没有新金融事件。错R4 source的检查点实际拒绝。

首轮1/4 CLOSE已完成且正确checkpoint/JSON已保存，随后旧报告哈希误用只读JSON编码，对HistoricalReceipt报错。原错误、BEFORE与FAILED working state保留在`runs/2022/primary/`和`runs/failure/`。没有重跑1/4；`export-recovery/2022-validated-export-import`证据在`completion/`中，校验旧checkpoint source和完整JSON后接续。独立`export-recovery/driver.py`仅复用原生dataclass/date/Decimal编码修出口；交易源码整个期间未改，后续checkpoint另存实际driver SHA，不给旧checkpoint回填身份。旧`run_prefixes.py`保留错误稿，不再作为重跑入口。

最初启动：`runs/STARTED.json`；完成：`export-recovery/completion/DONE.json`。当前独审入口为本文件、`SOURCE_FREEZE.json`、`INPUT_OUTPUT_SHA256.json`、`analysis/VERIFICATION.json`及上述10检查点证据。下一经济日期尚未获准，不自动接续。
