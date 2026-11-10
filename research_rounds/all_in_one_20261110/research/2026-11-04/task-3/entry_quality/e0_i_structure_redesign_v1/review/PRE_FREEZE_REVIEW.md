# E0/I 本体改造：先核因果时钟与反例

状态：仅原源码独立预审；候选未冻结，六股信号表尚未审。没有调用事件/策略模型，没有运行账户或回测。

## 原事件不是事后极值信号

原调用链是 `current_pool_bridge.py:224–231` → `numeric.event_frame_numeric(..., joint=True,event_exit=False)`；每个 source 段分别调用（374–379）。当前 cache 读取保存的 event/confirmed_pivot_price，重建 base，再调用 G1_I（cache.py:20–34）。不能直接把 numeric 内部 target 当当前 I。

`numeric.py:69–79` 事件钟只推进正且有限的 close/volume 观察。t>=64 后，sigma[t] 用本次前 63 个对数收益 RMS，量 baseline[t] 用此前 21 量 median。`95–114` 先检旧 floor、再按方向更新 developing extreme；只有 t>ext，才用 ext 当时已知 sigma[ext]、baseline[ext]，以及 ext 后至本次已完成观察的均量形成 activity（平方根后裁剪 .5..2）。反转确认达到 1，才在**当前 CLOSE**发布 pivot。

因此一份 pivot 至少需要两个时间：`pivot_date` 是旧极值日，`confirmed_at` 是事件所在行；后一时间才是可用时钟。不得将历史 confirmed_pivot_date 回填成当时已经确认。同方向的新极值会换 ext，尺度和量锚随新 ext 重新冻结；它不是永远在某个 START 日固定。

B5/G1 强度是另一条通道：B4 model.py:122–160 将 sqrt(h)*MAD 尺度、量参考冻结在 candidate，只有新价格 frontier 且方向收益为正才加 volume-weighted credit，x 与 credit 双达阈值才确认（223–255）。numeric E0 没有这种 frontier-credit 账；两者的 sigma、阈值、确认不能互换。

## 冻结前必须回答的状态问题

1. **START 的源事件。** `numeric event=+1`、`base.entered=1`、`i_buy` 是不同变量。旧 base active 时 +event 只抬 floor，通常不再 entered（policy.py:106–114）。新 I 若先停、旧 E0 仍 active，仅等 base.entered 会把恢复锁死。若选每次 +event 可 START，要明确它是新尝试，不偷清旧证据或账户退出单。
2. **相邻低点。** 应比较同一原 source 段内相邻两个已发布 +event 的 closing-pivot；不能以盘中 low、running extreme、未来回看低点或 max-ratchet floor 代替。较低的原 pivot 可能被旧 floor 的 max 丢弃，因此从 floor 反推相邻关系会错。
3. **START 后的新证据。** START 当日继承之前已经确认的 HL/旧高信息，可以是因果规则，但不能称为 START 以后第二次独立确认。若要求后续推进，须明确 confirmed_at 与 START 的先后，而不是 pivot_date 在 START 前后。
4. **收复哪一个高。** 最近已确认高、历史最高高、某次破坏前的高，经济含义不同。历史最高可把强 V 长期锁在外；滚动最近小高可在下降阶梯中一次小反弹即通过。不能先看赢家/失败后选择锚。
5. **同日更新次序。** 先用上一状态中的已知高判断 reclaim，再发布本次新高是最清楚的单步语义。正确 numeric 的新 -event 当日 C 必低于它刚确认的高，所以同日“新确认该高且严格收复该高”应为 false；若同时 true，要查价域或变量更新。新 +event 当日 C 高于该低点是确认本身，不是额外突破证据。
6. **持续验证不是每日 fresh。** CONFIRM 应有明确延续和破坏转移。如果每天都要求新 HL 或 reclaim 事件，无事件日就自动撤销，会把持有尺度缩成事件脉冲。若无事件保持 CONFIRM，也要说明何种已知结构破坏撤销，不能暗加固定天数或以未来结果判失效。
7. **破坏优先。** 原 policy.py:99–114 先检旧 floor，本观察 exited 后禁止同日正 event 重新进入；G1_I 同样先检旧 floor/E0。新卡必须明确同日破坏与确认谁优先，不能先用本日新 low 抬线再倒推本日触线，也不能用新确认擦掉旧破坏。
8. **强反弹和 UNKNOWN。** 先新低后快速 V，尚无第二高低点、又未收复选定旧高，可能一直 START 而不能 CONFIRM；单调急涨无回撤也可能无新 HL。应在六股表保留这类反例，不能为了覆盖临时改锚。source 换段/未知不等于经济失败，也不能自动制造新 START 或延续旧段 pivot。

## 原规则表述校正

当前 G1_I 是 entry-only 暖机会门，`use_x=False`，但不是“永久延续且无退出”：base 不活或 C<=旧 I floor 仍退出（policies_g1.py:8,20–34）。改造目标是持续验证/破坏的定义，不能以旧规则没有价格退出作为理由。

本审查者此前在本根启动的是只读提取、统计关联、源码/哈希核验及隔离单点算术，没有启动账户或回测。没有核查全机进程；此前 OS 拒绝的 ps 不能支持“全机没有进程”的结论。

待冻结后，只审指定六股的逐日事件可用时钟、锚身份和状态转移，不计算资金、候选成交、收益或扩大 EMA/资金参数。
