# 完整半导体126股：运行前覆盖

名单在新FSM批量运行前固定。来自既有冻结当前metadata的industry=半导体，共126股，全部与原STOCK_MANIFEST1709相交；不是历史PIT行业成分，也不按是否买入、未来收益、CP是否成功筛选。

窗口2025-01-01—2026-06-30；每股仍从原完整前缀准备，展示窗口不重置状态。本阶段没有运行新FSM/指标/账户、数量或收益。

数据可得性另核：2,901个raw CP锚中2,587个有第20后续真实观察、314不足20（其中34连下一观察也无）；有2个恰好到第20、因此最多2,585个具有20后观察。此为上界，尚未扣入口报价无效、两保护规则自身提前退出等，不能当策略存续或20后风险最终分母。文件FOLLOWUP20_AVAILABILITY_SUMMARY/RAW_CP_FOLLOWUP20_AVAILABILITY只计现有观察数，没有模拟保护线。

|原覆盖|数量|
|---|---:|
|当前metadata固定名单|126股|
|complete本地源|120股|
|截至窗口末无本地观察|6股|
|窗口内原OHLC/CP观察|39,802行|
|原raw CP总锚|2,901个|
|其中2025|1,681个|
|其中2026H1|1,220个|

6个无观察为托伦斯301583、粤芯半导-U301660、超纯应材301717、燧原科技-U688801、长鑫科技688825、杰理科技920138。沿原manifest为not_applicable_no_local_observation_by_end，不当失败或阴性。不能仅凭源空断言尚未IPO。

13股本地首次观察落在窗口内，明细见COVERAGE126_SUMMARY；它们的首次观察日不是经官方核验的IPO日。大普微-UW301666、臻宝科技688797、盛合晶微688820、中科仪920186原CP锚为0；仍保留在完整名单，不当CP失败。当前metadata没有可核历史上市/行业时点。

拓荆科技688072在窗口内末个原观察为2026-06-26，不能填造6/29—30或假定停牌。全warm prefix中9股共12个早年bar有24处price_eligible/source_invalid未知flag；展示窗口内这两类未知为0。共享FSM须严格按未知处理/断暖，不能bool(NaN)当真。

## 版本与执行缺口

120个物理CP文件末日都到2026-10-27，但canonical CP1_input/cache_through均为2026-06-30。固定截止前CP/input索引精确匹配，价格共同close逐值相同；不能直接对物理全长assert相等，也不能把H2物理CP拿作同版本完整输入。此次运行所有来源必须统一clip至6/30，不联网补未来。

窗口39,802行均为可核真实HLC；仍无显式停牌/limit/ST状态、盘口、逐笔或receive时钟，原缺失session也无独立交易日历证明。日线next OPEN仅报价参考，不证明成交。复权坐标同源，但非PIT企业行动公告审计。

## 待共享引擎稳定后运行

SYMBOLS126.json保完整固定母体，SYMBOLS120_COMPLETE.json为适用源列表；6股状态必须留在最终覆盖。COVERAGE126_INPUT_INDEX绑定每股源路径/SHA、真实起止日、CP锚、晚起与缺口。ORIGINAL25_IDENTITY_ANNOTATIONS_ONLY仅旧25实际层旁注，不驱动母体或新持仓。未运行未稳定代码，等待cost_stress_adapter的runner API与immutable SHA。
