# 小仓 fast CORE、空仓 CP 与 A/B 接线对照（经济前草案）

## 目的与范围
只检验仅 A/B 消费者遗漏原市场 fast CORE / 空仓 freshCP 职责后，补接这些职责会怎样改变初仓质量及完整逐股回合。不是新 alpha，亦不是复刻原 joint_v3 共享账户。只运行一次冻结的 2022 新邀请生命周期，新邀请截止 2022-12-30，既有持仓及权益支付跟至 2026-06-30。基线为 relative_priority_equity_run_2022_v1 的动态 A_UNION_B，不使用旧固定许可分母。2024/2026 七例仅作接口、资格与次 OPEN 数量核对，不生成跨窗策略收益。

## 原市场资格与事件
- 保留原 Facts.packet('I') / S0 eligibility 的 event.Q 和 continuing.Q 全部字段与 UNKNOWN 原因。continuing 只去掉 i_buy，保留原 common_ready、market buyability、I、行业 E0 与当日观察、H1 可读、市值及身份。PVR 只用于本消费者排队。不得另加 M3、G、涨幅、年龄阈值。
- A/B 原 sealed event、I_qualified、PVR 字段及日期不变。
- fast CORE：自身 FLAT、event.Q=True、该原 I/segment epoch 尚无本臂 I 初仓实际成交。原事件源或完整 lineage 不可知不得猜 epoch。本次候选有235条 event.Q=True 但严格根 lineage 不可判定，会保守阻止 fast CORE 通道；这不是原 counter 的额外 alpha，亦不阻止其独立已知 A/B 或 CP 资格。
- 空仓 CP：自身 FLAT、continuing.Q=True、当天 fresh canonical CP receipt，且该 receipt 未在本臂实际成交消费。CP 无需此前持仓盈利。
- 所有未知、NOFILL、尚未持仓是三种不同状态；只已建立经济路径出现 UNKNOWN 才永久锁证券，市场资格 UNKNOWN 不伪造成已持仓。

## 同证券/同事件去重与跨证券排队
同一证券、同一 close 合并所有来源为一张邀请，保留 source_mask、A/B event_id、CORE epoch、CP receipt_id。
角色顺序：I（A/B 或 fast CORE）优先，随后 CP。I 和 CP 分别按本身保护线做 close 预检；I 已知整手/风险/保护拒绝才尝试 CP，UNKNOWN 不当作已知失败绕过。若 I close 已知可行但 CP close 为 UNKNOWN，只有 I 角色获得邀请，未知 CP 不作为次 OPEN 备用；I 次 OPEN 已知 NOFILL 时仍是已知 I NOFILL，不冒充已经尝试 CP。任何角色 floor 或 CP candidate 缺失/非正/非法都明确 UNKNOWN，不退化为其他保护线。次共同 OPEN 在同一已选邀请内按相同顺序重算；预览已知失败可 fallback，若出现 UNKNOWN 则锁住，不 fallback。此条件 OPEN 模型没有原真实 reserve / execution window，不能把其 fill 当真实成交。
证券去重后，沿用原 PVR 降序、sid 稳定次序；每行业每日最多两个 close 可行邀请。A/B 没有额外优先权。明确记录同日 fast 挤出 A/B、先前 fast 持有阻塞 A/B、UNKNOWN 阻塞、以及递补。每日两邀请不是同时最多两持仓。
原 A/B 独立市场事件不受 fast epoch 邀请锁额外限制；实际 I 角色成交会登记当前 epoch。CP 初仓只消费该 CP receipt，不消费 CORE epoch。CORE 与 CP receipt 不互相替代。全部消费发生在正股数条件 fill 后，pending、获槽、预检或 NOFILL 不消费；昨日未获槽的 CP 不跨日回放。

## 数量、费用、保护与完整回合
固定参考 NAV=1,200,000元，初始含买费名义上限24,000元（2%）、计划风险上限3,000元（0.25%），原单边滑点 SLIP=.0005，即5bp。dated 手数与原买卖费用、此前20有效量均值1%容量不变。次 OPEN 重算数量，不缩放旧利润。
I 初仓使用原 I floor、I 结构关闭后次共同 OPEN退出。CP 初仓使用 max(I floor, CP candidate)；每个 close 先以此前有效 CP floor 判断破线，未破后才抬到 max(旧 floor、当日 I floor、fresh CP candidate)。不得用当日新抬线倒触发当日退出。I 失效优先所有角色退出。
CP 初仓是经济初始层，但不能把它误标为 I 角色。若初始 CP 退出而追加仍存，回合持续直到零库存；初始层独立费用收益按其实际卖出日与自有股息计算，不强借整轮终日。
后续保持原 A/B 消费者限制：最多一次净盈利 freshCP 追加、原行业 M3=1、含费追加至最多4%参考库存和总计划风险0.25%，严格净值>0；不因接空仓 CP 同时放开原完整 joint_v3 的多次 MOBILE 加层。追加亦保留自己的 CP floor 与实际 receipt 消费。
卖出未实际执行仍占状态；T+1逐日逐股数核。明确原 joint_v3 CORE resize最多10%及原CP reserve消费均未照搬，因此本轮是有意小仓/成交消费的研究合同。

## 权益与 UNKNOWN
原436条已准入经济事件、NET80现金假设、原权益身份、真实登记日自有数量、初层数量、应收/到账、退出后支付、跨回合隔离完全继承。未准入 factor/权益变化继续 UNKNOWN。不通过同证券已有一条事件而全股票放行。新路径可能更多或更少UNKNOWN，闭合但财务源不足另单列，不能忽略。
原 raw/事实/CP/market rule 来源哈希不变；全源 lineage 与因子检查不变。输入静态池、历史发布可得性和真实下单可成交性并未被此次接线证明。

## 经济前验收与一次运行
独立审计草案、源语义、七例+九例；实现合成边界、角色缓存隔离、I/CP实际消费、退出先旧线后抬线、fallback UNKNOWN、T+1、权益坐标及归属、原基线无fast回归、物理截断前缀。冻结代码/输入哈希及审核结果后才建立一次运行标记。修复工程 bug 必须留存前版本、差异、原测试失败，不把经济后改协议伪称预冻结。
不扫参数、不见结果改优先级、不追加第二候选经济臂。报告源标签层、实际pending/fill层及可闭收益层分别分母；单独初始层/整轮、所有UNKNOWN、年内已闭与全持有期、右尾贡献、七例及固定旧44尾持有覆盖。不是账户收益、年化或实际胜率保证。
