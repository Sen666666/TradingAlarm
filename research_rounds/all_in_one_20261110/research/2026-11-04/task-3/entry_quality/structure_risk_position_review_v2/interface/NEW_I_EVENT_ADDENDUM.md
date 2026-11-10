# 新 I 买入事件：可补足 CP，但不能重复授权

本件只读源码；未运行信号模型、proof、runner、账户或合成路径。原 READOUT 不改。

**结论：`i_buy`是当日新证据门，不是持续暖态；但它也不是仅 I 从0变1的入场脉冲。** 已持有且 I_target始终为1，仍可能出现新的 i_buy。它可作为“CP以外的新增许可”候选；持续I_target、持续grade≥2以及仅有I floor更新都不能代替这个新事件。同一底层推进同时满足I与CP时，不能拿两份额度。

## 真实定义与资格边界

`policies_g1.py:16–34`中，G1_I的 opportunity 为：基础结构仍有效、G1已ready且grade≥2、并且 **base.entered或fresh_up**。先执行旧I线/基础结构退出，然后 `buy_event = active and opportunity`；cache.py:28–32直接保存为 `i_buy`。

`grade.py:24–29`的fresh_up来自以下任一当日新事实：

| 原 reason | 能确认什么 | 不得扩张的解释 |
|---|---|---|
| new_E0_price_volume_up_event | 原native event==+1；可与原事件的canonical confirmed pivot及确认观察绑定 | 不等于所有I事件都新增pivot或抬高I floor |
| new_S21_up_confirmation / new_S63_up_confirmation | 原相应尺度有新的up confirmation | 不能冒称同一E0 pivot ID；现compact输出没有统一canonical I receiptID |
| new_price_frontier_in_confirmed_up_structure | 当前及此前S21均为up，当前running extreme严格超过原prior extreme（含原浮点容差） | 不是grade升级；也不自动等于超过整个持仓campaign的历史最高点 |

因此grade不变也能有i_buy；连续几天各有新frontier时i_buy可以连续True。仅“暖态延续、没有新事实”不会让i_buy连续True。fresh_up布尔可同时包含多个reason，不能将一行拆成多笔资金权利。

`engine.py:31–47`的packet先保留原市场buy_allowed，再AND **exact当日facts存在且i_buy=True**，以 `source_id='original_I_daily_event'`装入Security.buy_allowed。`sector_stock_admission.py:185–220`的S0资格再AND原common/市值/stock I趋势/issuer/sector及行业当日趋势与rank可得等条件；unknown不视作合格。

`J.planning:218`的 `event[sid].q`使用此未替换事件门的Security；`opportunities.core_Q`在250仅记录这个q，故eventQ/core_Q本身 **不包含not-held、core_epoch或资金池**。实际新增CORE角色在244才后置检查flat及epoch锁。已有仓时core_Q仍可以True，不能以roles无core倒推没有新I事件。

相反，`continuing[sid]`在218把buy_allowed替换回market buyable；mobile_Q是CP路径的持续资格，**没有I当日event门**。它不能被当作“新的I买入事件”。

## 现有身份字段与明确缺口

直接可用的原facts字段：canonical sid、source segment、当日index、i_buy/i_target/i_floor、g_ready/g_grade/g_fresh_up、close/factor/raw_close。现cache COLS未保留up_reasons或i_entered，不能仅凭i_buy推断是哪一种reason。

如需保留证据来源，可只读关联现有原IX signals（`prepare_ix.py:27–32`已保存segment、e0_entered、grade、fresh_up、up_reasons等）和prepared-v2原states/events（manifest提供路径和SHA）。E0正event分支可关联原确认观察、confirmed pivot价格及源中可用的pivot日期；source canonical series/segment/确认日与原文件SHA都可绑定。对S21/S63/新frontier分支，可保留原reason、对应观察时钟和源身份；**不能为所有分支虚构一个既有canonical pivot或provider eventID**。

现有engine Fact的source_id是通用 `original_I_daily_event`，不是逐事件receiptID；原I cache没有与CP相同的canonical receipt/消费账。若主设计要将新I事件用于已有仓扩张，必须明确独立的派生事件身份（例如canonical sid、segment、确认观察及原source语义/哈希），标明它是派生ID，并保存一次授权/订单绑定；不要伪造CP token、借用core epoch充当每次I事件ID，或通过改pool绕过准入。CLOSE确认时钟来自原研究合同，不应声称已知真实live发布时间。

## 与 CP 的最小去重合同

同股同一确认观察若同时满足I和CP，只形成一个总目标差额合同，记录两种来源，不能两次分配或两次占rank slot。CP trace已有new_advance_price_event_ids；I的E0正event也可能就是其中某一观察，跨日I/CP可能共享一段底层价格推进。原系统未提供现成的跨I/CP统一消费账，不能声称已自动排除该重叠；在身份/去重未明确前，只能称“新增许可候选”，不能证明是独立新风险预算。

新增I许可仍须服从原持有线已通过、ACT/行业有效、同股buy/exit pending屏障、真实现金/资本/风险与whole-lot/GAP/T+1/ACK。eventQ合格不改变资金池stage，不自动解core_epoch锁；如果新增来源要进现role='mobile'的request，该接口目前要求真实fresh CP，必须显式增加I来源合同，不能把它包装成伪CP。

本件没有计算事件数量、与CP重叠覆盖、赢家损失或收益；仅确认“新I事件”在源码中确实存在，并给出可读取的身份字段和未有的消费合同。
