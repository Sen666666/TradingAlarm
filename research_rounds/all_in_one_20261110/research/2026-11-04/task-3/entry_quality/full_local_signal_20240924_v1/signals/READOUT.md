# 2024-09-24全本地5517股：原stock-only信号

正式入口为 **ALL_SIGNALS.parquet + COMPLETION.json**。5517个唯一ID、单一目标日，5309条exact信号、208条无目标日行情，错误0。原始表及其COMPLETION在落盘后没有被解释层改写；原表SHA256：

`ff5300924759d483e242d8c0b9c43ae2e93c7539b0b579000f4c43d1b50c040b`

## 执行与复用

- 复用72条partial、35条fixed35、6条目标日结果，去重110股；三处重叠的19个原信号字段均精确相同。源文件实际SHA与原收据一致，原代码SHA均核同。
- 冻结16股pilot按前缀长度分位、SH/SZ/BJ和旧池/池外取样，含两只旧结果控制。12worker耗时7.81秒，16条exact、0错误，两只控制的19字段全同，新增唯一结果14股。
- 唯一一次full批次排除上述124股，处理5393股：5185次原模型计算、208条无目标日行情不调用模型。full墙钟1744.85秒（29.08分钟），0错误；未超过40分钟条件。
- 每块约24股、只读必要列一次，物理过滤`sid集合 AND trade_date<=2024-09-24`。每股完成立即写JSONL、flush和fsync。无未来frame指标回填；保存prefix计数和截止日。完成/错误ID均不被自动重算，截断行要求人工检查而不自动删改。全量已完成，无待续算进程。

FREEZE绑定源实际SHA256 `11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`、原代码、driver、5517身份表、16股计划及复用收据。执行前后原代码未变，源大小/mtime未变。225块完整JSONL的路径、SHA和证券见FULL_JOURNAL_INDEX.json。

## 核验与解释层

全部5309条exact close与已冻结同源价格特征逐bit一致；208条missing证券集合与同源目标日观察元数据精确一致。所有记录的prefix_end_day不晚于9/24，exact记录均止于9/24。

原E0/I/G/numeric的19字段原样保留。另存的ALL_SIGNALS_INTERPRETED.parquet只生成知识状态解释，未改正式raw入口：

| 解释口径 | True | False | UNKNOWN |
|---|---:|---:|---:|
| exact且E0 ready后读取I target | 3616 | 1670 | 231 |
| exact且E0/G ready后读取I target且i_buy | 2313 | 2973 | 231 |

5286股为exact且E0/G ready；23股有exact源行但E0未成熟，208股缺当日源行。后两类解释为UNKNOWN，不把原状态机的初始0冒充已知不合格。原i_buy不改，且不等于i_entered、新独立结构或交易许可。正式根合并自行生成三态解释，不必读取独立解释版。

原表为保存provenance而保留部分旧记录附带列；fixed35的稀疏legacy score/榜单列不是本次全5517 PVR结果。合并应白名单选19模型字段及key/status/target/prefix/reuse/source元数据，分数只来自根冻结完整特征。

## 限制

本批只有原stock E0/G1_I；未计算CP、行业/市场资格、H1、历史ST/停牌/可买状态或资金、订单、收益。full_S0_eligibility_q未评估，不能把stock信号称为完整合法交易资格。市值未进入此批模型或全5517筛选；旧池身份只用于pilot分层与来源标签。

5517是现存统一canonical本地母体，不宣称历史全证券PIT范围。源qfq参考日可能晚于目标日；只截价格行不等于认证历史复权因子、available_at或真实可成交。没有外部补数、账户、参数优化或未来收益标签。本轮旧停止批次未被改写或复启，新授权批次使用独立目录、计划和运行收据。
