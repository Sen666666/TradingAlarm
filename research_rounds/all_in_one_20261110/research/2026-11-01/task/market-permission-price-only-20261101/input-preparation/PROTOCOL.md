# 原市场输入准备合同

仅重建原公式输入，不导入或运行 v2 FSM，不计算其状态、尺度、前沿、许可、历史收益或账户。本目录独立于 v2-frozen，既有源和结果只读，无下载、服务或交易操作。

固定范围为既有五案例：OLD924_RS、OLD924_PVR、BDIAG2022、BDIAG2023、PVR_SLOT1_2026_LOCAL。两个旧924案例共享 OLD407 输入；另三个共享 NATIVE1709 输入。既有37检查点只读取 case/domain/day、原 market/prior_high63/breadth/BREAK，以及原行业分项；NAV、盈利标签和未来赢家不参与准备或窗口选择。

保留既存完整范围：OLD407 原运行 recovery.csv 的全部2013-01-04—2026-10-26；NATIVE1709 原运行 recovery.csv 的全部2013-01-04—2026-06-30。行业指数从其源最早日期到所属域既有截止，不临近924或2023重新初始化。展示年份按冻结合成包已声明的日历窗口，未计算新 FSM，也没有先验状态种子。

旧域复用原 tech-drawdown-regime/diagnostic-v1/traces 的 signed-m 与 log收益，并按 ready 抑制首64观察；同原按行业平均收益构造价格、每行业至少5股的 m>0 比例、全局至少8行业等权广度。重聚合与原运行 CSV 全序列核对，导出的实际价格以原运行 CSV 为准，绝不用单日收益替代价格。其原价格数值实现为 (1+expm1(r.fillna(0))).cumprod()。

新域复用既有生命周期任务所用 STOCK_MANIFEST 与原 TradingAlarm/desk/refresh.py 的 compute_recovery。AST 只扩大最后 return，暴露 z,mom,sector_b,returns,sector_r,r；不改任何计算、窗口、有效性或广度门。price 为原 exp(r.fillna(0)).cumprod()。固定1709身份全保留，仅如原导出在实际原函数传入 roster 中排除截止前没有有效源的身份；缺源清单单列，不当负方向。

实际运行复合 price 与 price_observed 分列。观察真实性来自原 aggregate log-return 是否有效；fillna(0) 的启动占位价格保留为 as-run 数值，但输入可观察标志 False。价格分母（股票、行业）与 m 分母独立列明；真实零收益不当缺失。首次源前的历史未知，后续影子若另获授权须使用完整前缀，不得借原账户恢复直接 ACTIVE。

半导体 URFI881121、电子化学品 URFI881172 的价格采用已声明的真实行业指数 close／segment_id。旧域绑定原旧快照行业信号，新域绑定现存 industry CP1-input 的 close，并与该文件对应的原行业 signal 逐值核同；不使用其 CP1/E0 状态、线、收据或金额。广度是该域固定研究股票池中有效 m 的比例，绝不宣称指数完整成分广度。两域身份、源哈希和分母分别输出；源切换必须由后续消费者按合同显式处理。

输出原运行全局 market/prior_high63/breadth/BREAK、两行业价格与广度、逐日行业分母、股票源片段与缺源清单、37检查点和原组件核对、原输入物理前缀检查及 SHA256。所有原控制对照逐值检查，float 差异和 CSV 回读容差明确记录，BREAK 必须完全一致。对最终冻结包逐文件 SHA 再核，不改其任何文件。
