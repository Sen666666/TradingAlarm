本目录执行 ../FROZEN_DESIGN.txt；不是 label_evaluation_contract/ 中旧提案。
只读原CP旗事件索引、原prepared signal、facts/CP_input及既有CSI300日期。0账户/0CP模型/0特征/0阈值搜索。

主接口 LABELS.parquet / LABELS.csv：
键 sid,date；mfe20_log,mae20_log,final20_log；label_valid,label_status,label_end；
phase=DEV/V2024/V2025/V2026H1，dev_fit_eligible，label_within_phase，label_cross_calendar_year；nonoverlap20。
canonical_receipt_id可空但原CP旗事件保留。audit_event_key是源SHA派生审计键，不能称canonical identity。

源与公式：
逐股从STOCK_MANIFEST.source_sha256唯一的prepared*/.../signal.parquet读取完整同尺度close/原价量/原标志至2026-10-22；不拼raw尾。每个信号日close/segment与原facts及CP_input精确核对。原SHA不符直接中止，坐标不符保留该事件并标未知/报告。
未来有效观察必须原observed=true、price_eligible=true、finite positive close/volume、synthetic=false、source_invalid=false、segment已知且在同一连续源段。原observed别名冲突单列审计，不暗选别名；无假定缺标志等于True。
以CP signal close为基点，未来同段前20条有效观察q=ln(C_future/C_signal)。mfe20_log=max(0,q)，mae20_log=min(0,q)，final20_log=q20；另存未含0的max/min及exp(q)-1。正式标签不足20/基点无效/源断段全null，不截短。
LABEL_PATHS.parquet逐一保留完整标签的20个日期/close/logchange；SOURCE_BINDINGS.csv是sid到原prepared/facts/CP_input路径与SHA映射。SOURCE_SHA256.json包含冻结设计/母体/价格源/脚本绑定。

时间与缺失：
actual_days=实际取到的未来有效观察数（完整时20）；future_eligible_available_same_segment是截止源下该段未来可见总数。calendar_span_days和common_session_span是完整标签的自然日/CSI300会话跨度，不能把20个股票观察叫20共同会话。该固定CSI300本地历史仅至2026-10-16；若标签结束更晚则common_session_span=null并明标calendar不完整，而不将部分跨度充作完整。
skipped_source_rows及分原因计数对应信号之后到第20有效观察（不足时到源段末）的已存行。分原因可能重叠，不能相加当互斥计数。missing_common_session_rows是该跨度参考CSI300日期中prepared未存行数，不凭它断言停牌；假日、零量、源缺口不前填。
开发记录只有signal在2022/23且完整label_end<=2023-12-31时dev_fit_eligible=true。验证按signal年；真实完整20可跨年/阶段，另有within-phase标志。不因标签跨期把观察强截年末。

非重叠：
按根明确接口，仅在全体完整标签CP中逐股按时间选择首张，随后只有signal date>上一所选label_end才选。全母体先选再分模型/特征，不看label数值/收益；跨年连续。它是评估去重，不是交易冷却或新CP过滤。

next_session_*只是既有CSI300次会话日期下的原prepared raw OHLC/volume与标志；它不取第一个未来有效日替代实际次会话。next_session_one_price_exact只表示四价精确相同且正，不等于涨停、跌停、停牌或能成交。原limit_up/limit_down/suspend字段没有则null；不按涨幅推断。execution_proven始终false。T+1/排队/费用/滑点/日内时钟未在标签中模拟；signal close基点不是nextOPEN成交价，也不是策略净收益或总回报。

SUMMARY.json及COUNTS_BY_PHASE/MONTH.csv只给标签覆盖/审计计数；不做特征分组或拟合。静态2026-10-22池、PIT历史成员/供应商版本和已有研究看过验证期的限制沿用根冻结设计。
