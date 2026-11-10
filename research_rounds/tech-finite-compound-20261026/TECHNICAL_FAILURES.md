# 经济前技术失败，全部保留

- tail/与fetch-tail.log：迁移仓库没有ths_readonly模块，第一次仅模块导入失败、没有行情请求。tail-v2定位原项目只读采集器后，沙箱网络限制使连接失败且请求计数0。tail-v3在已授权只读端点完成科技池补尾；reference-tail只补原RS参照最近12条与权益，不扩大交易池。
- merge-core.log：Path接口误传字符串，首次合并首文件即失败，data/core空目录保留；wrapper修正后首次合并为data/core-v2。
- raw-graphs.log：试图将旧机械行业正例鼎泰放入核心科技新数据图，因它不在固定407池明确失败，没有把它加进候选池。新图改用已在核心科技的腾景；旧鼎泰图和结果保持参照。
- synthetic.log：合成夹具边预约边执行，第二次预约时钟倒退，被原账本拒绝；改夹具为先全部预约、再全部执行。synthetic-v2.log的15项实际账本边界通过，未改变金融规则。
- 最重要的适配失败：data/core-v2合并给旧行业记录引入空的observed_bar列，改变原“缺列默认真实观察”的含义。prepared/初次行业事实仅保留两条新观察，旧索引交集核验过弱，未发现整段缺失。technical/old-controls-SEMI的首日预约与旧账不一致，控制拒绝；technical/short为无效技术路径，新增经济仍0。
- 修复为在concat前显式保留旧布尔列默认值，并强制原完整历史索引相等，再逐值比较；有效新数据为data/core-v3、prepared-v2。旧v2数据、prepared/、失败控制和short全部保留，不作为经济证据。该修复没有改变价格/量/金额、E0/I/IX条件或仓位参数。
- 初始run.py多一个右括号由语法检查发现并修复，无执行资金。图形缓存写入改到临时目录，无经济影响。

本文件记录技术修复，不据结果改策略。正式资金运行前必须另有准入收据；技术通过不等于策略盈利。

## 完整经济阶段的末端覆盖失败

首轮在2026-10-23发现原费用代理区间右端为该日，不能生成合法退出报价而终止。accounts/与account-freeze.json保留；只延原费率的覆盖日期，新增run_v2.py/analyze_v2.py和execution-rules-v2.json，同参重跑为accounts-v2。全部21路径直到2026-10-22的14238日账/6017成交/38101账务行精确一致，故修复没有改变早期资金路径。交易/费率参数不变，经济重跑1次。详见EXECUTION_BOUNDARY_REPAIR.md。

## 结果展示序列化

report.log在生成全部表格与图后，因BH没有闭合交易、胜率为NaN而严格JSON序列化拒绝。失败的post-result-summary.json保留；finish_report.py只将缺值表达为null，写有效post-result-summary-v2.json并完成index.html，不重跑交易，也不覆盖失败JSON。
