# 旧根内首次未买续邀：只读事实预检

## 核心结论

唯一新增职责不是行业 active 总门，而是 late 首次目标要求当前仍有效的行业授权确认日晚于本股原 root 出生日。2022 共同 BUY 的纯新增作用是 163/1779（9.16%）；2024 是 31/1083（2.86%）。它改变的是旧根内尚无 PROBE parent 的首次邀请，不能说修复了退出后复用同根新开仓。

2022 共同原 BUY 中总影响210条，47条是当前行业授权本就不可用，163条才是postbirth比较纯新增；2024总影响144条，113条是前者、31条才是纯新增。不能把总数冒充新逻辑贡献。没有计算这些条目的删单收益或任何新账户结果。

## 完整分母及职责

|年/范围/分母|总数|原birth旁路|late无当前有效授权|late有效但不晚于root（纯新增）|late有效且晚于root|身份来源未知|
|---|---:|---:|---:|---:|---:|---:|
|2022/ALL/REGISTERED_ENTRIES|2411|1709|66|229|407|0|
|2022/ALL/ORIGINAL_PROXY_BUYS|2395|1697|65|228|405|0|
|2022/COMMON/REGISTERED_ENTRIES|1780|1288|47|163|282|0|
|2022/COMMON/ORIGINAL_PROXY_BUYS|1779|1288|47|163|281|0|
|2024/ALL/REGISTERED_ENTRIES|1210|554|128|40|488|0|
|2024/ALL/ORIGINAL_PROXY_BUYS|1198|550|128|40|480|0|
|2024/COMMON/REGISTERED_ENTRIES|1091|502|113|31|445|0|
|2024/COMMON/ORIGINAL_PROXY_BUYS|1083|500|113|31|439|0|

市场票另列完整分母：2022全部24733张、共同16963张；2024全部12723张、共同11555张。其内尚无本root代理PROBE parent的late票为9937/6896及5230/4840，包含已经被原持仓、UNKNOWN责任、行业四真、AB优先、尺寸或PVR队列挡住的票，不能称可成交机会数。ORIGINAL_OFFER_FUNNEL_BY_RESPONSIBILITY.csv逐项保留原结果。

## root、初仓与UNKNOWN边界

- 3621个原登记signal CLOSE之前均无本root的代理PROBE parent；3593个发生原buy_core的回合才在次OPEN建立唯一parent。其余28个未买回合不是真实零填单。
- PRICE q0为2022的3条、2024的9条，全部无自身parent/订单/BUY。后来同root新receipt可能首次建立parent，但不会倒推到此前q0时存在。真实零填、部分填、ACK和晚到成交的证据全为UNKNOWN_NOT_PROVIDED。
- 本窗首全策略BUY的late票：2022全/共同461/307，2024为626/564；前次实际全卖后新root内的late首次BUY：237/184和22/19。两类不能混成退出前旧根复用。
- 窗口前root：2022全/共同286/200；2024为162/138。2024原ENTRY_FACTS的prewindow_root列全空，本报告依据固定窗口起点2024-09-02和原root_day另建prewindow_root_fact，不改原表。
- 机制身份/来源UNKNOWN为0只表示此批原票核验完备。旧账经济UNKNOWN仍为2022全353回合（已买340），2024全86（已买83）；共同样本均0。这些总盈亏未知从未填0。

## native行业字段不是M3

ENTRY_FACTS的8个sector_E0/stage/action/receipt/authorization字段3621行全部与INDUSTRY_MANIFEST.refs.state逐字段一致。其路径是原native行业state → momentum_persistence_breadth_v1/SECTOR_DAILY → canonical_mu3的附带字段 → ENTRY_FACTS；M3/PVR3本身没有生成这些stage字段。ENTRY_FACTS缺行业authorization_id和receipt_id，本报告从原state回接，未拿股票PRICE receipt_id代替。

refs.receipts JSON只覆盖2025-07至2026-06，不能据它认定2022/24没有票。本次仅抽取原trace和Stage定义，使用90行业既存CP缓存重建25227张全史receipt，90行业state所有字段逐位exact，没有重算numeric CP。每张receipt核formation两端和全区间的source_kind/path/segment；原截止2026-06-30内真实切源0、trace_unknown0。不能外推未来跨source自动安全。

trace原E0 episode哈希与Stage episode哈希约定不同，已按原receipt/确认日的唯一state行建立对应关系；当前授权同时核当前attempt和Stage episode。当前失效授权不缓存；same-observation ignored票不算accepted。

## 固定例（完整身份在FINAL CSV）

- 浪潮1/5与同方1/4：当前计算机行业授权确认2021-12-30、formation从12-24，分别晚于原root10-26/12-17，late条件通过。没有因浪潮旧亏损改式。
- 游族11/8：root11/2，当前有效行业授权11/7、formation11/1起；确认晚于root但形成起点早于root，按冻结式通过，不追加formation门。
- 永和7/15、巨轮6/13、歌尔9/30、银轮12/25：原root生日旁路，原行业四真、AB优先和PVR队列仍适用；不禁止洗出后真新root首探。
- 电气风电9/25和海能达9/25：均为late且当天无有效行业授权，不通过的是active部分，不是本轮postbirth纯新增。电气此前8/16因mobile_line撤权，后首accepted票9/27；海能达此前7/4因E0_invalid撤权，后首accepted票9/26。后日期只描述潜在市场资格，不代表同股新票、选中或OPEN成交。
- 海能达9/20原born保留，但原行业false仍挡；9/23原AB优先事实不变；9/24和25均无当期行业授权。新机制不能把早先未成交的票补成成交。
- 华电辽能10/28：root9/27，当前当天accepted授权10/28、formation10/22起，late条件通过。
- 江丰12/15与17现有FIXED_DAILY明确receipt=true，root12/15、前者born/PROBE，后者continuing/首次CONFIRMED。12/15保持birth原资格；12/17当前行业授权仍12/12，假设无parent时late条件不通过。实际执行parent从未提供，因此不能推断真正初仓或续余量。1/5和15已有信号源且行业当前授权确认分别1/5和1/7，假设无parent时late条件通过；1/5票formation始12/12早于stockbirth亦不另加门。1/30、2/2、2/5股票市场源缺失仍UNKNOWN。

## 运行与文件

CONTRACT.md在本轮新公式全量核值前保存；不是盲测，之前的案例和旧经济结果已知。未运行经济/consumer、参数搜索、filtered PnL、第二式或同日AND比较，原账/源码/授权/锁未改。原固定输入hash复核不变。

- REGISTERED_ENTRY_BASE_FACTS.csv / MARKET_RECEIPT_BASE_FACTS.csv：未应用新式的完整原事实。
- REGISTERED_ENTRY_PREFLIGHT.csv / MARKET_RECEIPT_PREFLIGHT.csv：同一唯一式逐条注释。
- RESPONSIBILITY_FOUR_GROUP_COUNTS.csv及RESPONSIBILITY_FACT_CROSSES.csv：纯新增职责、rolling20High/首次重入/窗前根完整交叉，只有计数。
- ORIGINAL_LABEL_DESCRIPTIVE_TABLES.csv：仅按原入场标签描述已冻旧路径金额。不同投影不可相加，不是新门收益。
- ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv：全史原票及形成/确认时钟、source、accepted身份。
- FIXED_CASE_PREFLIGHT_FINAL.csv：最终固定案例；覆盖临时FIXED_CASE_PREFLIGHT.csv的江丰摘要缺源标记，源修复见FIXED_CASE_SOURCE_CORRECTION.json。
- HYTERA_WIND_STAGE_TRANSITIONS.csv：两例原stage撤权及后续首accepted。
- BASE/TRACE_PREFLIGHT/FINAL的QA与SOURCE_HASHES、OUTPUT_HASHES：完整复核。

研究限制：固定1709股票与行业映射NON-PIT；两窗独立FLAT，不是连续共享账户；条件next-common OPEN全填代理不证明可成交；不由静态票身份推断动态替代机会或新收益。
